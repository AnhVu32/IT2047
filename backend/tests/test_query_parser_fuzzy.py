import unittest

from src.search.query_parser import RuleBasedQueryParser
from src.search.schemas import DEFAULT_NUMERIC_TOLERANCE, numeric_bounds


class FuzzyPriceParsingTests(unittest.TestCase):
    def setUp(self):
        self.parser = RuleBasedQueryParser()

    def _price(self, query):
        return self.parser.parse(query).preference_filters.price

    def _area(self, query):
        return self.parser.parse(query).preference_filters.area

    def test_bare_price_becomes_target(self):
        price = self._price("Căn hộ 5 tỷ ở quận 7")
        self.assertEqual(price.target, 5)
        self.assertIsNone(price.min)
        self.assertIsNone(price.max)

    def test_price_range_sets_both_bounds(self):
        price = self._price("Căn hộ 2-3 tỷ")
        self.assertEqual(price.min, 2)
        self.assertEqual(price.max, 3)
        self.assertIsNone(price.target)

    def test_price_range_with_words(self):
        price = self._price("Nhà từ 2 đến 3 tỷ")
        self.assertEqual(price.min, 2)
        self.assertEqual(price.max, 3)

    def test_explicit_prefix_still_wins_over_bare(self):
        # "dưới 3 tỷ" must remain a max bound, not a bare target.
        price = self._price("Căn hộ dưới 3 tỷ")
        self.assertEqual(price.max, 3)
        self.assertIsNone(price.target)

    def test_khoang_still_target(self):
        price = self._price("Căn hộ khoảng 5 tỷ")
        self.assertEqual(price.target, 5)

    def test_trieu_unit_bare(self):
        price = self._price("Nhà 5000 triệu")
        self.assertAlmostEqual(price.target, 5.0, places=4)

    def test_bare_area_becomes_target(self):
        area = self._area("Căn hộ 70m2")
        self.assertEqual(area.target, 70)

    def test_area_range(self):
        area = self._area("Căn hộ 60-80 m2")
        self.assertEqual(area.min, 60)
        self.assertEqual(area.max, 80)


class BandTranslationTests(unittest.TestCase):
    def _price(self, query):
        return RuleBasedQueryParser().parse(query).preference_filters.price

    def test_target_expands_to_band(self):
        lower, upper = numeric_bounds(self._price("Căn hộ 5 tỷ"), DEFAULT_NUMERIC_TOLERANCE)
        self.assertAlmostEqual(lower, 5 * (1 - DEFAULT_NUMERIC_TOLERANCE), places=4)
        self.assertAlmostEqual(upper, 5 * (1 + DEFAULT_NUMERIC_TOLERANCE), places=4)

    def test_none_tolerance_drops_target_filter(self):
        lower, upper = numeric_bounds(self._price("Căn hộ 5 tỷ"), None)
        self.assertIsNone(lower)
        self.assertIsNone(upper)

    def test_explicit_bounds_are_not_widened(self):
        lower, upper = numeric_bounds(self._price("Căn hộ dưới 3 tỷ"), DEFAULT_NUMERIC_TOLERANCE)
        self.assertIsNone(lower)
        self.assertEqual(upper, 3)


if __name__ == "__main__":
    unittest.main()
