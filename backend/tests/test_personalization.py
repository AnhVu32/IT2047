import sys
import types
import unittest
from unittest.mock import patch

from src.search.personalization import score_item


class ScoreItemTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "districts": {"Q7": 1.0},
            "property_types": {"Can ho": 0.8},
            "price_center": 5.0,
            "saved_listing_ids": {123},
        }

    def test_full_match_scores_high(self):
        score = score_item(
            {"district": "Q7", "property_type": "Can ho", "price_range": 5.0, "listing_id": 123},
            self.profile,
        )
        self.assertGreaterEqual(score, 0.9)

    def test_no_match_scores_zero(self):
        score = score_item(
            {"district": "X", "property_type": "Y", "price_range": 50.0, "listing_id": 999},
            self.profile,
        )
        self.assertEqual(score, 0.0)

    def test_saved_listing_contributes(self):
        base = score_item({"district": "X", "property_type": "Y", "price_range": 50.0, "listing_id": 999}, self.profile)
        saved = score_item({"district": "X", "property_type": "Y", "price_range": 50.0, "listing_id": 123}, self.profile)
        self.assertGreater(saved, base)


class BuildUserProfileTests(unittest.TestCase):
    SAMPLE = [
        {"listing_id": 1, "action_type": "save", "implicit_score": 0.7, "district": "Q7", "property_type": "Can ho", "price_range": 5.0},
        {"listing_id": 2, "action_type": "contact", "implicit_score": 0.9, "district": "Q7", "property_type": "Can ho", "price_range": 5.5},
        {"listing_id": 3, "action_type": "view", "implicit_score": 0.2, "district": "Q1", "property_type": "Nha pho", "price_range": 12.0},
    ]

    def _with_repo(self, rows):
        fake = types.ModuleType("src.services.feedback.repository")
        fake.get_recent_interactions = lambda user_id, limit=200: rows
        return patch.dict(sys.modules, {"src.services.feedback.repository": fake})

    def test_profile_aggregates_and_normalizes(self):
        from src.search.personalization import build_user_profile

        with self._with_repo(self.SAMPLE):
            profile = build_user_profile(1)

        self.assertIsNotNone(profile)
        self.assertEqual(profile["districts"]["Q7"], 1.0)  # top district normalized to 1
        self.assertLess(profile["districts"]["Q1"], 1.0)
        self.assertEqual(profile["saved_listing_ids"], {1, 2})  # save + contact
        self.assertAlmostEqual(profile["price_center"], 6.03, places=1)

    def test_no_interactions_returns_none(self):
        from src.search.personalization import build_user_profile

        with self._with_repo([]):
            self.assertIsNone(build_user_profile(1))


if __name__ == "__main__":
    unittest.main()
