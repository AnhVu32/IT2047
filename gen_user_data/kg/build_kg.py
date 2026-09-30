"""Map users.json + listings.json + interactions.json -> Knowledge Graph.

Xuất ra 3 dạng để import linh hoạt:
  * data/kg/nodes.csv, data/kg/edges.csv   (import bằng bất kỳ Graph DB / DGL nào)
  * data/kg/import.cypher                   (chạy trực tiếp trên Neo4j)

Nodes:  User, Listing, Location(District), Amenity, Intent, Query
Edges:
  (User)-[VIEWED|SAVED|SHARED|CONTACTED {score, dwell_time, timestamp}]->(Listing)
  (User)-[SEARCHED]->(Query)
  (User)-[PREFERS_DISTRICT]->(Location)
  (User)-[LIKES_AMENITY]->(Amenity)
  (User)-[HAS_INTENT]->(Intent)
  (Listing)-[LOCATED_IN]->(Location)
  (Listing)-[HAS_AMENITY]->(Amenity)
"""
from __future__ import annotations

import csv
import json
import os
import sys
from typing import Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from schemas import Interaction, Listing, UserProfile  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")
KG_DIR = os.path.join(DATA_DIR, "kg")

ACTION_EDGE = {"view": "VIEWED", "save": "SAVED", "share": "SHARED", "contact": "CONTACTED"}


def _load(name, model):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return [model(**row) for row in json.load(f)]


def build(users: List[UserProfile], listings: List[Listing],
          interactions: List[Interaction]):
    nodes: List[Dict] = []
    edges: List[Dict] = []
    seen_nodes = set()

    def add_node(node_id, label, **props):
        key = (label, node_id)
        if key in seen_nodes:
            return
        seen_nodes.add(key)
        nodes.append({"id": f"{label}:{node_id}", "label": label,
                      "name": str(node_id), **props})

    def add_edge(src_label, src, rel, dst_label, dst, **props):
        edges.append({"src": f"{src_label}:{src}", "rel": rel,
                      "dst": f"{dst_label}:{dst}", **props})

    # --- Listing + Location + Amenity nodes ---
    for l in listings:
        add_node(l.listing_id, "Listing", price=l.price_billion,
                 area=l.area_sqm, bedrooms=l.bedrooms, ptype=l.property_type,
                 budget_group=l.budget_group)
        add_node(l.district, "Location")
        add_edge("Listing", l.listing_id, "LOCATED_IN", "Location", l.district)
        for feat, val in l.features.items():
            if val:
                add_node(feat, "Amenity")
                add_edge("Listing", l.listing_id, "HAS_AMENITY", "Amenity", feat)

    # --- User nodes + preference edges ---
    for u in users:
        add_node(u.user_id, "User", segment=u.segment,
                 age_group=u.demographics.age_group,
                 income=u.demographics.income_level)
        add_node(u.primary_intent, "Intent")
        add_edge("User", u.user_id, "HAS_INTENT", "Intent", u.primary_intent)
        for d in u.explicit_preferences.preferred_districts:
            add_node(d, "Location")
            add_edge("User", u.user_id, "PREFERS_DISTRICT", "Location", d)
        for a in u.explicit_preferences.liked_amenities:
            add_node(a, "Amenity")
            add_edge("User", u.user_id, "LIKES_AMENITY", "Amenity", a)

    # --- Interaction edges (trọng số = implicit_score) ---
    for it in interactions:
        rel = ACTION_EDGE[it.action_type]
        add_edge("User", it.user_id, rel, "Listing", it.listing_id,
                 score=it.implicit_score, dwell_time=it.dwell_time_seconds,
                 timestamp=it.timestamp, source=it.source)
        qid = it.interaction_id
        add_node(qid, "Query", text=it.context.raw_query,
                 intent=it.context.inferred_intent)
        add_edge("User", it.user_id, "SEARCHED", "Query", qid)

    # --- Similarity edges (task 1.3): nạp nếu đã chạy similarity_kg.py ---
    _add_similarity_edges(add_node, add_edge)

    return nodes, edges


def _add_similarity_edges(add_node, add_edge):
    """Thêm cạnh tương đồng vào KG (nếu file đã sinh bởi similarity_kg.py):
      * Amenity -[SIMILAR_TO {weight}]- Amenity      (declared, knowledge.py)
      * Criterion -[SIMILAR_TO {weight}]- Criterion  (declared, ngữ nghĩa)
      * Location -[SIMILAR_LOCATION {weight}]- Location (từ hành vi)
    """
    sim_path = os.path.join(KG_DIR, "similarity_edges.json")
    loc_path = os.path.join(KG_DIR, "location_similarity_edges.json")
    if os.path.exists(sim_path):
        with open(sim_path, encoding="utf-8") as f:
            for e in json.load(f):
                label = "Amenity" if e["group"] == "amenity" else "Criterion"
                add_node(e["attr_a"], label)
                add_node(e["attr_b"], label)
                add_edge(label, e["attr_a"], "SIMILAR_TO", label, e["attr_b"],
                         weight=e["weight"], source=e["source"])
    if os.path.exists(loc_path):
        with open(loc_path, encoding="utf-8") as f:
            for e in json.load(f):
                add_node(e["attr_a"], "Location")
                add_node(e["attr_b"], "Location")
                add_edge("Location", e["attr_a"], "SIMILAR_LOCATION", "Location",
                         e["attr_b"], weight=e["weight"], source=e["source"])


def _write_csv(nodes, edges):
    os.makedirs(KG_DIR, exist_ok=True)
    # union of keys để header ổn định
    node_keys = sorted({k for n in nodes for k in n})
    with open(os.path.join(KG_DIR, "nodes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=node_keys)
        w.writeheader()
        w.writerows(nodes)
    edge_keys = sorted({k for e in edges for k in e})
    with open(os.path.join(KG_DIR, "edges.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=edge_keys)
        w.writeheader()
        w.writerows(edges)


def _esc(v):
    if isinstance(v, str):
        return '"' + v.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return str(v)


def _write_cypher(nodes, edges):
    lines = ["// Auto-generated KG import script for Neo4j",
             "// Chạy: cat import.cypher | cypher-shell",
             ""]
    # Constraints
    for label in sorted({n["label"] for n in nodes}):
        lines.append(
            f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
            f"REQUIRE n.node_id IS UNIQUE;")
    lines.append("")
    for n in nodes:
        props = ", ".join(f"{k}: {_esc(v)}" for k, v in n.items() if k != "label")
        props = props.replace("id:", "node_id:", 1)
        lines.append(f"MERGE (:{n['label']} {{{props}}});")
    lines.append("")
    for e in edges:
        rprops = ", ".join(f"{k}: {_esc(v)}" for k, v in e.items()
                           if k not in ("src", "rel", "dst"))
        rprops = f" {{{rprops}}}" if rprops else ""
        lines.append(
            f"MATCH (a {{node_id: {_esc(e['src'])}}}), (b {{node_id: {_esc(e['dst'])}}}) "
            f"MERGE (a)-[:{e['rel']}{rprops}]->(b);")
    with open(os.path.join(KG_DIR, "import.cypher"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    users = _load("users.json", UserProfile)
    listings = _load("listings.json", Listing)
    interactions = _load("interactions.json", Interaction)
    nodes, edges = build(users, listings, interactions)
    _write_csv(nodes, edges)
    _write_cypher(nodes, edges)
    from collections import Counter
    nlabels = Counter(n["label"] for n in nodes)
    elabels = Counter(e["rel"] for e in edges)
    print(f"[kg] {len(nodes)} nodes, {len(edges)} edges -> {os.path.abspath(KG_DIR)}")
    print("[kg] node labels:", dict(nlabels))
    print("[kg] edge types :", dict(elabels))
