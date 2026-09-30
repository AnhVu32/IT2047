import unittest

from src.services.feedback.scoring import ACTION_BASE_SCORE, VALID_ACTIONS, implicit_score


class FeedbackScoringTests(unittest.TestCase):
    def test_action_ordering(self):
        # Stronger intent must score higher: view < share < save < contact.
        self.assertLess(implicit_score("view", None), implicit_score("share", None))
        self.assertLess(implicit_score("share", None), implicit_score("save", None))
        self.assertLess(implicit_score("save", None), implicit_score("contact", None))

    def test_dwell_bonus_capped(self):
        self.assertEqual(implicit_score("view", None), ACTION_BASE_SCORE["view"])
        # A ~60s dwell adds the full +0.2 bonus and no more.
        self.assertAlmostEqual(implicit_score("view", 60), 0.40, places=4)
        self.assertAlmostEqual(implicit_score("view", 600), 0.40, places=4)
        # Dwell only applies to views, not to save/contact.
        self.assertEqual(implicit_score("save", 120), ACTION_BASE_SCORE["save"])

    def test_thumbs_are_signed(self):
        self.assertEqual(implicit_score("thumbs_up", None), 1.0)
        self.assertEqual(implicit_score("thumbs_down", None), -1.0)

    def test_unknown_action_scores_zero(self):
        self.assertEqual(implicit_score("bogus", None), 0.0)
        self.assertNotIn("bogus", VALID_ACTIONS)


if __name__ == "__main__":
    unittest.main()
