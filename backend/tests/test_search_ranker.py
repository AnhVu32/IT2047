import unittest

from src.search.query_parser import RuleBasedQueryParser
from src.search.ranker import diversify, rank_candidates


class RankerTests(unittest.TestCase):
    def test_semantic_and_target_fit_rank_first(self):
        parsed = RuleBasedQueryParser().parse("Căn hộ khoảng 5 tỷ, yên tĩnh")
        items = [
            {"listing_id": 1, "price_range": 5, "area": 70, "semantic_score": .9, "posted_date": "2026-01-01"},
            {"listing_id": 2, "price_range": 10, "area": 70, "semantic_score": .2, "posted_date": "2026-01-01"},
        ]
        ranked = rank_candidates(items, parsed)
        self.assertEqual(ranked[0]["listing_id"], 1)
        self.assertIn("semantic", ranked[0]["score_breakdown"])

    def test_diversity_caps_cluster(self):
        items = [{"listing_id": i, "geo_cluster_150m": "same", "final_score": 1 - i / 10} for i in range(5)]
        items.append({"listing_id": 99, "geo_cluster_150m": "other", "final_score": .1})
        result = diversify(items, limit=10, max_per_cluster=3)
        self.assertEqual(len([x for x in result if x["geo_cluster_150m"] == "same"]), 3)
        self.assertIn(99, [x["listing_id"] for x in result])

    def test_location_is_a_ranking_signal_not_an_exclusion(self):
        parsed = RuleBasedQueryParser().parse("căn hộ ở Phường An Khánh")
        items = [
            {"listing_id": 1, "district": "Phường Thới An", "semantic_score": .8},
            {"listing_id": 2, "district": "Phường An Khánh", "semantic_score": .8},
        ]
        ranked = rank_candidates(items, parsed)
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["listing_id"], 2)
        self.assertEqual(ranked[0]["score_breakdown"]["location"], 1.0)
        self.assertEqual(ranked[1]["score_breakdown"]["location"], 0.0)

    def test_price_is_a_ranking_signal_not_an_exclusion(self):
        parsed = RuleBasedQueryParser().parse("căn hộ khoảng 5 tỷ")
        items = [
            {"listing_id": 1, "price_range": 9, "semantic_score": .8},
            {"listing_id": 2, "price_range": 5, "semantic_score": .8},
        ]
        ranked = rank_candidates(items, parsed)
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0]["listing_id"], 2)
        self.assertGreater(
            ranked[0]["score_breakdown"]["target"],
            ranked[1]["score_breakdown"]["target"],
        )

    def test_no_profile_leaves_ranking_unchanged(self):
        parsed = RuleBasedQueryParser().parse("Căn hộ khoảng 5 tỷ")
        items = [{"listing_id": 1, "price_range": 5, "area": 70, "semantic_score": .9, "district": "Q7"}]
        without = rank_candidates(items, parsed)
        with_none = rank_candidates(items, parsed, None)
        self.assertEqual(without[0]["final_score"], with_none[0]["final_score"])
        self.assertNotIn("personalization", without[0]["score_breakdown"])

    def test_profile_adds_personalization_term_and_can_reorder(self):
        parsed = RuleBasedQueryParser().parse("Căn hộ khoảng 5 tỷ")
        items = [
            {"listing_id": 1, "price_range": 5, "area": 70, "semantic_score": .55, "district": "Q1"},
            {"listing_id": 2, "price_range": 5, "area": 70, "semantic_score": .50, "district": "Q7"},
        ]
        # Without a profile, listing 1 (higher semantic) ranks first.
        self.assertEqual(rank_candidates(items, parsed)[0]["listing_id"], 1)
        # A strong preference for Q7 promotes listing 2 and records the term.
        profile = {"districts": {"Q7": 1.0}, "property_types": {}, "price_center": None, "saved_listing_ids": set()}
        ranked = rank_candidates(items, parsed, profile)
        self.assertIn("personalization", ranked[0]["score_breakdown"])
        self.assertEqual(ranked[0]["listing_id"], 2)


if __name__ == "__main__":
    unittest.main()
