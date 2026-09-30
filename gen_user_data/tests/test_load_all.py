"""Test cho load_all.py (data loader) — dùng fixture nhỏ + DB tạm, độc lập data thật.

Chạy: cd gen_user_data && python tests/test_load_all.py
Hoặc:  python -m pytest tests/test_load_all.py -q

Bao phủ:
  * schema + load_properties (derived: price_per_sqm/amenity_count/family_suitable)
  * load_behavior VALIDATE referential integrity (bỏ interaction trỏ user/listing lạ)
  * load_similarity chuẩn hoá (a,b) — (garage,parking) và (parking,garage) -> 1 dòng
  * build_graph_stub node types = User/Property/Attribute
  * IDEMPOTENT: chạy 2 lần -> số dòng giống hệt
  * FULL-REFRESH: data co lại (2 user -> 1 user) -> row cũ biến mất
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import load_all  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures nhỏ
# ---------------------------------------------------------------------------
def _listing(lid, price, area, beds, feats, district="Quận 1"):
    base = {f: False for f in [
        "balcony", "garden", "garage", "terrace", "pool", "gym", "park", "bbq",
        "kids_playground", "sports_court", "security_24h", "reception", "elevator",
        "parking", "near_metro", "near_bus", "near_highway", "near_school",
        "near_hospital", "near_mall", "near_market", "near_park",
        "river_view", "park_view", "city_view"]}
    base.update({f: True for f in feats})
    return {"listing_id": lid, "title": f"L{lid}", "property_type": "Căn hộ",
            "district": district, "price_billion": price, "area_sqm": area,
            "bedrooms": beds, "bathrooms": 2, "budget_group": "mid_range",
            "price_tier_area": "mid", "features": base, "description": None}


def _user(uid, districts, likes):
    return {"user_id": uid, "segment": "mid_range", "primary_intent": "buy_for_living",
            "demographics": {"age_group": "30-40", "marital_status": "married",
                             "children": 2, "income_level": "medium"},
            "explicit_preferences": {"preferred_districts": districts, "min_bedrooms": 2,
                                     "budget_range": [3.0, 5.0], "property_type": ["Căn hộ"],
                                     "liked_amenities": likes},
            "persona": None}


def _inter(iid, uid, lid, action="contact", score=5.0):
    return {"interaction_id": iid, "user_id": uid, "session_id": "s1", "listing_id": lid,
            "action_type": action, "timestamp": "2026-01-01T00:00:00Z",
            "dwell_time_seconds": 120, "source": "search_bar",
            "context": {"raw_query": "q", "filters_applied": {}, "inferred_intent": "buy_for_living",
                        "budget_group": "mid_range"},
            "implicit_score": score, "is_bounce": False}


def _write_fixture(data_dir, users, listings, interactions, sim_edges):
    os.makedirs(os.path.join(data_dir, "kg"), exist_ok=True)
    json.dump(users, open(os.path.join(data_dir, "users.json"), "w", encoding="utf-8"))
    json.dump(listings, open(os.path.join(data_dir, "listings.json"), "w", encoding="utf-8"))
    json.dump(interactions, open(os.path.join(data_dir, "interactions.json"), "w", encoding="utf-8"))
    json.dump(sim_edges, open(os.path.join(data_dir, "kg", "similarity_edges.json"), "w", encoding="utf-8"))


class _Env:
    """Trỏ load_all vào thư mục tạm + DB/graph tạm; tự khôi phục khi xong."""
    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="test_loadall_")
        self.data_dir = os.path.join(self.tmp, "data")
        self.kg_dir = os.path.join(self.data_dir, "kg")
        self.db = os.path.join(self.tmp, "wh.sqlite")
        self.graph = os.path.join(self.tmp, "g.pkl")
        self._saved = (load_all.DATA_DIR, load_all.KG_DIR)

    def __enter__(self):
        os.makedirs(self.kg_dir, exist_ok=True)
        load_all.DATA_DIR, load_all.KG_DIR = self.data_dir, self.kg_dir
        return self

    def __exit__(self, *a):
        load_all.DATA_DIR, load_all.KG_DIR = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run(self):
        return load_all.run(self.db, self.graph)

    def counts(self):
        return load_all.table_counts(self.db)


def _standard_fixture(env, n_users=2):
    listings = [
        _listing(101, price=3.0, area=60.0, beds=2, feats=["near_school", "pool", "gym"]),
        _listing(102, price=5.0, area=100.0, beds=3, feats=["parking"]),
        _listing(103, price=2.0, area=40.0, beds=1, feats=[]),
    ]
    users = [_user("u1", ["Quận 1"], ["pool", "near_school"])]
    if n_users >= 2:
        users.append(_user("u2", ["Quận 1", "Quận 7"], ["gym"]))
    interactions = [
        _inter("e1", "u1", 101, "contact", 5.0),
        _inter("e2", "u1", 102, "save", 3.0),
        _inter("e3", "u2", 103, "view", 1.0),      # thuộc u2 -> bị loại khi chỉ còn u1
        _inter("e4", "u1", 999, "view", 1.0),      # listing lạ -> BỎ
        _inter("e5", "ghost", 101, "view", 1.0),   # user lạ  -> BỎ
    ]
    sim_edges = [
        {"attr_a": "garage", "attr_b": "parking", "weight": 0.85, "group": "amenity", "source": "t"},
        {"attr_a": "parking", "attr_b": "garage", "weight": 0.85, "group": "amenity", "source": "t"},  # đảo -> dedup
        {"attr_a": "gym", "attr_b": "pool", "weight": 0.35, "group": "amenity", "source": "t"},
    ]
    _write_fixture(env.data_dir, users, listings, interactions, sim_edges)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_properties_and_derived():
    with _Env() as env:
        _standard_fixture(env)
        env.run()
        conn = sqlite3.connect(env.db)
        row = conn.execute("SELECT price_per_sqm_mil, amenity_count, family_suitable "
                           "FROM properties WHERE listing_id=101").fetchone()
        conn.close()
        # 3.0 tỷ / 60 m2 = 50 triệu/m2 ; 3 tiện ích ; beds=2 + near_school -> family=1
        assert abs(row[0] - 50.0) < 1e-6, row
        assert row[1] == 3, row
        assert row[2] == 1, row
    print("  PASS test_properties_and_derived")


def test_behavior_referential_validation():
    with _Env() as env:
        _standard_fixture(env)
        res = env.run()
        # 5 interaction: 3 hợp lệ, 2 bỏ (listing lạ 999 + user lạ ghost)
        assert res["behavior"] == {"loaded": 3, "skipped_invalid": 2}, res["behavior"]
        assert env.counts()["behavior"] == 3
    print("  PASS test_behavior_referential_validation")


def test_similarity_canonical_dedup():
    with _Env() as env:
        _standard_fixture(env)
        env.run()
        # (garage,parking) và (parking,garage) -> 1 dòng ; + (gym,pool) = 2 dòng
        assert env.counts()["attribute_similarity"] == 2, env.counts()
    print("  PASS test_similarity_canonical_dedup")


def test_graph_stub_node_types():
    with _Env() as env:
        _standard_fixture(env)
        res = env.run()
        nt = res["graph_node_types"]
        assert set(nt) == {"User", "Property", "Attribute"}, nt
        assert nt["User"] == 2 and nt["Property"] == 3, nt
    print("  PASS test_graph_stub_node_types")


def test_idempotent():
    with _Env() as env:
        _standard_fixture(env)
        env.run()
        before = env.counts()
        env.run()  # chạy lại
        after = env.counts()
        assert before == after, (before, after)
    print("  PASS test_idempotent")


def test_full_refresh_on_shrink():
    with _Env() as env:
        _standard_fixture(env, n_users=2)
        env.run()
        assert env.counts()["users"] == 2
        # data co lại còn 1 user -> nạp lại
        _standard_fixture(env, n_users=1)
        env.run()
        c = env.counts()
        assert c["users"] == 1, c            # row user cũ phải biến mất
        # interaction của u2 (e3) cũng phải mất; còn e1,e2 (u1) hợp lệ
        assert c["behavior"] == 2, c
    print("  PASS test_full_refresh_on_shrink")


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
    print(f"\n{len(fns)}/{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
