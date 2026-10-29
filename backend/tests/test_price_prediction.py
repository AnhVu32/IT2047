import unittest

from src.services.inference.price_prediction import (
    PricePredictionService,
    normalize_legal_status,
)

LISTING = {
    "property_type": "Căn hộ chung cư",
    "district": "Phường Tân Hưng",
    "area": 70.0,
    "bedrooms": 2,
    "price_range": 4.0,
    "legal_status": "Sổ đỏ/ Sổ hồng.",
    "latitude_longitude": "q=10.745,106.705",
}


class LegalStatusTests(unittest.TestCase):
    def test_maps_raw_labels(self):
        cases = {
            "Sổ đỏ/ Sổ hồng.": "Sổ hồng riêng",
            "Sổ đỏ/ Sổ hồng ( sử dụng chung)": "Sổ chung",
            "HĐMB.": "Hợp đồng mua bán",
            "Đang chờ sổ, HĐMB": "Đang chờ sổ",
            None: "Không rõ",
        }
        for raw, expected in cases.items():
            self.assertEqual(normalize_legal_status(raw), expected, raw)


class EstimateListingTests(unittest.TestCase):
    def setUp(self):
        self.service = PricePredictionService()

    def test_scores_listing_and_classifies_verdict(self):
        result = self.service.estimate_listing(LISTING)
        self.assertEqual(result["property_type"], "Căn hộ")
        self.assertEqual(result["asking_price"], 4.0)
        self.assertIn(result["verdict"], {"below", "within", "above"})
        cheap = self.service.estimate_listing({**LISTING, "price_range": 1.5})
        dear = self.service.estimate_listing({**LISTING, "price_range": 12.0})
        self.assertEqual((cheap["verdict"], dear["verdict"]), ("below", "above"))

    def test_rejects_listing_outside_training_domain(self):
        for patch in (
            {"latitude_longitude": None},
            {"latitude_longitude": "q=21.0,105.8"},
            {"area": 900.0},
            {"bedrooms": 9},
            {"price_range": 32.1},
            {"district": "Phường Không Tồn Tại"},
        ):
            with self.assertRaises(ValueError, msg=patch) as ctx:
                self.service.estimate_listing({**LISTING, **patch})
            self.assertTrue(str(ctx.exception), patch)


if __name__ == "__main__":
    unittest.main()
