"""Pipeline nạp dữ liệu (task 1.4) — IDEMPOTENT.

Kiến trúc:
  * Dữ liệu quan hệ (property / behavior / criteria) -> SQLite (mặc định, zero-config;
    đổi sang Postgres chỉ cần thay connection).
  * Đồ thị tri thức -> NetworkX, lưu pickle (Neo4j: đã có data/kg/import.cypher do
    build_kg.py sinh — data engineer nạp node/edge).

Idempotent: chạy lại KHÔNG nhân đôi dữ liệu.
  - Bảng chính: PRIMARY KEY + `INSERT OR REPLACE` (upsert).
  - Bảng liên kết: khoá tổ hợp + `INSERT OR IGNORE`.
  - Similarity: chuẩn hoá thứ tự cặp (a<=b) nên (a,b) và (b,a) không tạo 2 dòng.
  - Graph: dựng lại từ đầu mỗi lần (tất định) rồi ghi đè pickle.

    cd gen_user_data && python load_all.py            # -> data/warehouse.sqlite + data/graph/kg_networkx.pkl
    python load_all.py --db data/warehouse.sqlite --graph-out data/graph/kg_networkx.pkl

Cấu trúc:
    load_all.py
    ├── load_properties()    # + tính derived cơ bản
    ├── load_behavior()      # sau khi validate (referential integrity)
    ├── load_similarity()    # thành edges Attribute↔Attribute
    └── build_graph_stub()   # node User/Property/Attribute + edges
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sqlite3
from typing import Dict, List, Tuple

from schemas import Interaction, Listing, UserProfile

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
KG_DIR = os.path.join(DATA_DIR, "kg")
DEFAULT_DB = os.path.join(DATA_DIR, "warehouse.sqlite")
DEFAULT_GRAPH = os.path.join(DATA_DIR, "graph", "kg_networkx.pkl")

POSITIVE_ACTIONS = {"save", "share", "contact"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_json(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def _load_models(name, model):
    return [model(**row) for row in _read_json(name)]


def _canon(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a <= b else (b, a)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS properties (
            listing_id      INTEGER PRIMARY KEY,
            title           TEXT,
            property_type   TEXT,
            district        TEXT,
            price_billion   REAL,
            area_sqm        REAL,
            bedrooms        INTEGER,
            bathrooms       INTEGER,
            budget_group    TEXT,
            price_tier_area TEXT,
            description     TEXT,
            -- derived
            price_per_sqm_mil REAL,
            amenity_count     INTEGER,
            family_suitable   INTEGER
        );

        CREATE TABLE IF NOT EXISTS property_amenity (
            listing_id INTEGER,
            amenity    TEXT,
            PRIMARY KEY (listing_id, amenity)
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id        TEXT PRIMARY KEY,
            segment        TEXT,
            primary_intent TEXT,
            age_group      TEXT,
            marital_status TEXT,
            children       INTEGER,
            income_level   TEXT,
            budget_min     REAL,
            budget_max     REAL,
            min_bedrooms   INTEGER,
            persona        TEXT
        );

        CREATE TABLE IF NOT EXISTS user_pref_district (
            user_id  TEXT, district TEXT,
            PRIMARY KEY (user_id, district)
        );
        CREATE TABLE IF NOT EXISTS user_liked_amenity (
            user_id TEXT, amenity TEXT,
            PRIMARY KEY (user_id, amenity)
        );

        CREATE TABLE IF NOT EXISTS behavior (
            interaction_id     TEXT PRIMARY KEY,
            user_id            TEXT,
            session_id         TEXT,
            listing_id         INTEGER,
            action_type        TEXT,
            timestamp          TEXT,
            dwell_time_seconds INTEGER,
            source             TEXT,
            raw_query          TEXT,
            inferred_intent    TEXT,
            budget_group       TEXT,
            implicit_score     REAL,
            is_bounce          INTEGER,
            is_positive        INTEGER
        );

        CREATE TABLE IF NOT EXISTS attribute_similarity (
            attr_a TEXT,
            attr_b TEXT,
            grp    TEXT,          -- amenity | criteria | location
            weight REAL,
            source TEXT,
            PRIMARY KEY (attr_a, attr_b, grp)
        );

        CREATE INDEX IF NOT EXISTS ix_behavior_user ON behavior(user_id);
        CREATE INDEX IF NOT EXISTS ix_behavior_listing ON behavior(listing_id);
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# load_properties
# ---------------------------------------------------------------------------
def load_properties(conn: sqlite3.Connection) -> int:
    listings = _load_models("listings.json", Listing)
    prop_rows, amen_rows = [], []
    for l in listings:
        amenities = [f for f, v in l.features.items() if v]
        price_per_sqm = round(l.price_billion * 1000.0 / l.area_sqm, 3) if l.area_sqm else None
        family = int(l.bedrooms >= 2 and any(
            a in amenities for a in ("near_school", "kids_playground", "park")))
        prop_rows.append((l.listing_id, l.title, l.property_type, l.district,
                          l.price_billion, l.area_sqm, l.bedrooms, l.bathrooms,
                          l.budget_group, l.price_tier_area, l.description,
                          price_per_sqm, len(amenities), family))
        for a in amenities:
            amen_rows.append((l.listing_id, a))

    # Full-refresh: bảng MIRROR file nguồn -> idempotent + xử lý cả khi data co lại
    # (vd đổi từ 300 user xuống 5 user, các row cũ phải biến mất).
    conn.execute("DELETE FROM properties")
    conn.execute("DELETE FROM property_amenity")
    conn.executemany(
        "INSERT OR REPLACE INTO properties VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", prop_rows)
    conn.executemany("INSERT OR IGNORE INTO property_amenity VALUES (?,?)", amen_rows)
    conn.commit()
    return len(prop_rows)


# ---------------------------------------------------------------------------
# load_behavior (sau khi validate)
# ---------------------------------------------------------------------------
def load_behavior(conn: sqlite3.Connection) -> Dict[str, int]:
    interactions = _load_models("interactions.json", Interaction)
    valid_users = {r[0] for r in conn.execute("SELECT user_id FROM users")}
    valid_listings = {r[0] for r in conn.execute("SELECT listing_id FROM properties")}

    rows, skipped = [], 0
    for it in interactions:
        # VALIDATE referential integrity: user & listing phải tồn tại.
        if it.user_id not in valid_users or it.listing_id not in valid_listings:
            skipped += 1
            continue
        rows.append((it.interaction_id, it.user_id, it.session_id, it.listing_id,
                     it.action_type, it.timestamp, it.dwell_time_seconds, it.source,
                     it.context.raw_query, it.context.inferred_intent,
                     it.context.budget_group, it.implicit_score, int(it.is_bounce),
                     int(it.action_type in POSITIVE_ACTIONS)))
    conn.execute("DELETE FROM behavior")   # full-refresh
    conn.executemany(
        "INSERT OR REPLACE INTO behavior VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    return {"loaded": len(rows), "skipped_invalid": skipped}


# ---------------------------------------------------------------------------
# load_users (cần cho behavior validation + graph)
# ---------------------------------------------------------------------------
def load_users(conn: sqlite3.Connection) -> int:
    users = _load_models("users.json", UserProfile)
    rows, pref_d, liked_a = [], [], []
    for u in users:
        p = u.explicit_preferences
        rows.append((u.user_id, u.segment, u.primary_intent,
                     u.demographics.age_group, u.demographics.marital_status,
                     u.demographics.children, u.demographics.income_level,
                     p.budget_range[0], p.budget_range[1], p.min_bedrooms, u.persona))
        pref_d += [(u.user_id, d) for d in p.preferred_districts]
        liked_a += [(u.user_id, a) for a in p.liked_amenities]
    conn.execute("DELETE FROM users")            # full-refresh (xử lý cả khi data co lại)
    conn.execute("DELETE FROM user_pref_district")
    conn.execute("DELETE FROM user_liked_amenity")
    conn.executemany(
        "INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.executemany("INSERT OR IGNORE INTO user_pref_district VALUES (?,?)", pref_d)
    conn.executemany("INSERT OR IGNORE INTO user_liked_amenity VALUES (?,?)", liked_a)
    conn.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# load_similarity -> edges Attribute↔Attribute
# ---------------------------------------------------------------------------
def load_similarity(conn: sqlite3.Connection) -> int:
    rows = []
    for fname in ("similarity_edges.json", "location_similarity_edges.json"):
        path = os.path.join(KG_DIR, fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for e in json.load(f):
                a, b = _canon(e["attr_a"], e["attr_b"])  # chuẩn hoá thứ tự -> idempotent
                rows.append((a, b, e["group"], float(e["weight"]), e["source"]))
    conn.execute("DELETE FROM attribute_similarity")   # full-refresh
    conn.executemany(
        "INSERT OR REPLACE INTO attribute_similarity VALUES (?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# build_graph_stub -> NetworkX (User / Property / Attribute)
# ---------------------------------------------------------------------------
def build_graph_stub(conn: sqlite3.Connection, out_path: str):
    import networkx as nx

    G = nx.MultiDiGraph()

    def attr_node(kind: str, name: str) -> str:
        nid = f"Attr:{kind}:{name}"
        if nid not in G:
            G.add_node(nid, ntype="Attribute", kind=kind, name=name)
        return nid

    # Property nodes
    for r in conn.execute("SELECT listing_id, district, price_billion, budget_group, "
                          "price_tier_area, bedrooms FROM properties"):
        pid = f"Property:{r[0]}"
        G.add_node(pid, ntype="Property", district=r[1], price=r[2],
                   budget_group=r[3], price_tier_area=r[4], bedrooms=r[5])
        loc = attr_node("location", r[1])
        G.add_edge(pid, loc, etype="LOCATED_IN")
    for r in conn.execute("SELECT listing_id, amenity FROM property_amenity"):
        G.add_edge(f"Property:{r[0]}", attr_node("amenity", r[1]), etype="HAS_ATTRIBUTE")

    # User nodes + preferences
    for r in conn.execute("SELECT user_id, segment, primary_intent FROM users"):
        uid = f"User:{r[0]}"
        G.add_node(uid, ntype="User", segment=r[1], intent=r[2])
        G.add_edge(uid, attr_node("intent", r[2]), etype="HAS_INTENT")
    for r in conn.execute("SELECT user_id, district FROM user_pref_district"):
        G.add_edge(f"User:{r[0]}", attr_node("location", r[1]), etype="PREFERS")
    for r in conn.execute("SELECT user_id, amenity FROM user_liked_amenity"):
        G.add_edge(f"User:{r[0]}", attr_node("amenity", r[1]), etype="LIKES")

    # Behavior edges User -> Property
    for r in conn.execute("SELECT user_id, listing_id, action_type, implicit_score, "
                          "timestamp FROM behavior"):
        G.add_edge(f"User:{r[0]}", f"Property:{r[1]}", etype=r[2].upper(),
                   score=r[3], timestamp=r[4])

    # Attribute similarity edges
    for r in conn.execute("SELECT attr_a, attr_b, grp, weight FROM attribute_similarity"):
        kind = {"amenity": "amenity", "criteria": "criteria", "location": "location"}[r[2]]
        a = attr_node(kind, r[0])
        b = attr_node(kind, r[1])
        G.add_edge(a, b, etype="SIMILAR_TO", weight=r[3], grp=r[2])

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        pickle.dump(G, f)  # nx.write_gpickle bị bỏ ở networkx 3.x -> dùng pickle

    from collections import Counter
    ntypes = Counter(d["ntype"] for _, d in G.nodes(data=True))
    etypes = Counter(d["etype"] for _, _, d in G.edges(data=True))
    return G, dict(ntypes), dict(etypes)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def run(db_path: str, graph_out: str) -> dict:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        init_schema(conn)
        n_users = load_users(conn)
        n_props = load_properties(conn)
        beh = load_behavior(conn)
        n_sim = load_similarity(conn)
        G, ntypes, etypes = build_graph_stub(conn, graph_out)
        return {
            "db": db_path, "graph": graph_out,
            "users": n_users, "properties": n_props,
            "behavior": beh, "similarity_edges": n_sim,
            "graph_nodes": G.number_of_nodes(), "graph_edges": G.number_of_edges(),
            "graph_node_types": ntypes, "graph_edge_types": etypes,
        }
    finally:
        conn.close()


def table_counts(db_path: str) -> Dict[str, int]:
    conn = sqlite3.connect(db_path)
    tables = ["properties", "property_amenity", "users", "user_pref_district",
              "user_liked_amenity", "behavior", "attribute_similarity"]
    out = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    conn.close()
    return out


def main():
    ap = argparse.ArgumentParser(description="Idempotent data loader (task 1.4)")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--graph-out", default=DEFAULT_GRAPH)
    ap.add_argument("--verify-idempotent", action="store_true",
                    help="chạy 2 lần, khẳng định số dòng không đổi")
    args = ap.parse_args()

    res = run(args.db, args.graph_out)
    print("== load_all: HOÀN TẤT ==")
    print(f"  SQLite : {res['db']}")
    print(f"  Graph  : {res['graph']} ({res['graph_nodes']} nodes / {res['graph_edges']} edges)")
    print(f"  users={res['users']} properties={res['properties']} "
          f"behavior={res['behavior']} similarity_edges={res['similarity_edges']}")
    print(f"  graph node types: {res['graph_node_types']}")
    print(f"  graph edge types: {res['graph_edge_types']}")

    if args.verify_idempotent:
        before = table_counts(args.db)
        run(args.db, args.graph_out)  # chạy lại
        after = table_counts(args.db)
        same = before == after
        print(f"\n[idempotent] counts trước/sau chạy lại: {'GIỐNG NHAU ✅' if same else 'KHÁC ❌'}")
        print(f"  {before}")
        if not same:
            print(f"  after: {after}")


if __name__ == "__main__":
    main()
