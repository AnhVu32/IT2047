import unittest

from src.search.graph_repository import Neo4jGraphRepository
from src.search.query_parser import RuleBasedQueryParser
from src.search.ranker import WEIGHTS, rank_candidates
from src.search.repository import SearchRepository


class GraphSearchTests(unittest.TestCase):
    def setUp(self):
        self.parser = RuleBasedQueryParser()

    def test_graph_query_uses_amenity_traversal_and_parameters(self):
        parsed = self.parser.parse(
            "Căn hộ 2PN dưới 5 tỷ, cách metro không quá 3 km, phải có ban công"
        )
        query, params = Neo4jGraphRepository._query(parsed)
        self.assertIn("NEAR_AMENITY", query)
        self.assertNotIn("coalesce(l.balcony, false) = true", query)
        self.assertEqual(params["amenity_categories"], ["metro"])
        self.assertNotIn("amenity_distance_0", params)
        self.assertIn("khong qua", parsed.protected_constraints)

    def test_near_feature_is_backed_by_graph_category(self):
        parsed = self.parser.parse("Ưu tiên căn hộ gần metro")
        candidate = Neo4jGraphRepository._score_record(
            {
                "listing_id": "123",
                "matched_features": [],
                "amenities": [{"category": "metro", "name": "Ga A"}],
                "wards": [],
            },
            parsed,
        )
        self.assertIn("near_metro", candidate["graph_evidence"]["matched_features"])
        self.assertEqual(candidate["graph_score"], 1.0)

    def test_former_area_filter_uses_v2_relationship(self):
        parsed = self.parser.parse("tôi muốn mua nhà", explicit_filters={"district": "Quận 2"})
        parsed.hard_filters.former_admin_areas = parsed.hard_filters.districts
        parsed.hard_filters.districts = []
        query, params = Neo4jGraphRepository._query(parsed)
        self.assertIn("IN_FORMER_AREA", query)
        self.assertIn("FormerAdminArea", query)
        self.assertIn("quận 2", params["location_terms"])
        self.assertIn("any(alias IN", query)

    def test_graph_validated_location_does_not_get_filtered_again_in_postgres(self):
        parsed = self.parser.parse("mua nhà", explicit_filters={"district": "Xã Hóc Môn"})
        where, params = SearchRepository()._where(parsed, graph_validated=True)
        self.assertNotIn("district_values", params)
        self.assertNotIn("former_admin_area_values", params)
        self.assertFalse(any("former_admin_area" in clause for clause in where))

    def test_current_ward_search_includes_prefix_free_normalized_alias(self):
        parsed = self.parser.parse("mua nhà", explicit_filters={"district": "Phường An Khánh"})
        query, params = Neo4jGraphRepository._query(parsed)
        self.assertIn("IN_WARD", query)
        self.assertIn("phuong an khanh", params["location_terms"])
        self.assertIn("an khanh", params["location_terms"])

    def test_natural_language_location_and_price_do_not_enter_where_clause(self):
        parsed = self.parser.parse("căn hộ khoảng 5 tỷ ở phường an khánh")
        where, params = SearchRepository()._where(parsed)
        self.assertNotIn("price_min", params)
        self.assertNotIn("price_max", params)
        self.assertNotIn("district_values", params)
        self.assertFalse(any("p.district" in clause for clause in where))

    def test_explicit_filter_location_and_price_remain_strict(self):
        parsed = self.parser.parse(
            "tìm căn hộ",
            explicit_filters={"max_price": 5, "district": "Phường An Khánh"},
        )
        where, params = SearchRepository()._where(parsed)
        self.assertEqual(params["price_max"], 5)
        self.assertEqual(params["district_values"], ["phường an khánh"])
        self.assertTrue(any("p.price_range <=" in clause for clause in where))
        self.assertTrue(any("p.district" in clause for clause in where))

    def test_listing_subgraph_query_is_parameterized(self):
        query = Neo4jGraphRepository._subgraph_query()
        self.assertIn("$listing_id", query)
        self.assertIn("NEAR_AMENITY", query)
        self.assertIn("IN_FORMER_AREA", query)
        self.assertNotIn("MATCH (l:Listing {listing_id:", query)

    def test_listing_subgraph_projection_is_whitelisted_and_deduplicated(self):
        response = Neo4jGraphRepository._subgraph_from_record(
            {
                "listing_node": {
                    "id": "listing-node-1",
                    "properties": {
                        "listing_id": "123",
                        "title": "Căn hộ mẫu",
                        "secret": "must not leak",
                    },
                },
                "connections": [
                    {
                        "relationship_type": "NEAR_AMENITY",
                        "target_id": "amenity-far",
                        "target_type": "Amenity",
                        "target_label": "Ga xa",
                        "target_properties": {"name": "Ga xa", "category": "metro", "secret": "x"},
                        "relationship_properties": {
                            "is_nearest": False,
                            "driving_distance_km": 2.0,
                            "rank": 1,
                            "internal": "x",
                        },
                    },
                    {
                        "relationship_type": "NEAR_AMENITY",
                        "target_id": "amenity-near",
                        "target_type": "Amenity",
                        "target_label": "Ga gan",
                        "target_properties": {"name": "Ga gan", "category": "metro"},
                        "relationship_properties": {
                            "is_nearest": True,
                            "driving_distance_km": 1.0,
                            "driving_duration_min": 2.4,
                            "rank": 2,
                        },
                    },
                    {
                        "relationship_type": "IN_WARD",
                        "target_id": "ward-1",
                        "target_type": "Ward",
                        "target_label": "Phường Mẫu",
                        "target_properties": {"name": "Phường Mẫu", "city_province": "Hồ Chí Minh"},
                        "relationship_properties": {},
                    },
                ],
            }
        )
        self.assertEqual(response.state, "ready")
        self.assertEqual(len(response.nodes), 3)
        self.assertEqual(len(response.edges), 2)
        self.assertEqual(response.amenity_categories, ["metro"])
        self.assertEqual(response.nodes[0]["id"], "listing:listing-node-1")
        self.assertNotIn("secret", response.nodes[0]["properties"])
        self.assertEqual(response.nodes[1]["label"], "Phường Mẫu")
        self.assertEqual(response.nodes[2]["label"], "Ga gan")
        self.assertEqual(response.edges[-1]["label"], "1.0 km · 2.4 phút")
        self.assertNotIn("internal", response.edges[-1]["properties"])
        self.assertNotIn("rank", response.edges[-1]["properties"])

    def test_listing_subgraph_disabled_is_graceful(self):
        repository = Neo4jGraphRepository()
        repository.enabled = False
        response = repository.subgraph("123")
        self.assertEqual(response.state, "unavailable")

    def test_unrelated_amenities_do_not_change_requested_score(self):
        parsed = self.parser.parse("Cách metro không quá 3 km")
        items = [
            {
                "listing_id": 1,
                "semantic_score": 0,
                "amenity_evidence": [
                    {"category": "metro", "driving_distance_km": 1.0},
                    {"category": "hospital", "driving_distance_km": 100.0},
                ],
            }
        ]
        ranked = rank_candidates(items, parsed)
        self.assertAlmostEqual(ranked[0]["score_breakdown"]["amenity"], 2 / 3, places=4)

    def test_ranking_profiles_remain_normalized(self):
        for weights in WEIGHTS.values():
            self.assertAlmostEqual(sum(weights.values()), 1.0)


if __name__ == "__main__":
    unittest.main()
