import unittest

from crawler import parse_listings


SAMPLE_HTML = """
<html>
  <body>
    <div class=\"re__card\">
      <a href=\"/ban-nha-rieng-duong-a-b/can-ban-gia-tot-pr12345678\">NHÀ ĐẸP TRUNG TÂM</a>
      <div>12,5 tỷ · 80 m² · 156,25 tr/m² · Hà Nội · 08/03/2026 · 0917 636 ***</div>
    </div>
  </body>
</html>
"""


class TestParserSmoke(unittest.TestCase):
    def test_parse_basic_listing(self):
        items = parse_listings(SAMPLE_HTML, "https://example.com")
        self.assertEqual(len(items), 1)

        item = items[0]
        self.assertEqual(item.title, "NHÀ ĐẸP TRUNG TÂM")
        self.assertIn("-pr12345678", item.url)
        self.assertEqual(item.price, "12,5 tỷ")
        self.assertEqual(item.area_m2, "80 m²")
        self.assertEqual(item.price_per_m2, "156,25 tr/m²")
        self.assertEqual(item.location, "Hà Nội")
        self.assertEqual(item.posted_date, "08/03/2026")
        self.assertEqual(item.contact_masked, "0917 636 ***")


if __name__ == "__main__":
    unittest.main()
