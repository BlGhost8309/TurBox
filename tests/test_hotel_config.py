import tempfile
import unittest
from pathlib import Path

from turbox.hotel_config import (
    parse_hotel_params_from_url,
    read_departure_cities,
    read_hotel_urls_config,
)


class HotelConfigTests(unittest.TestCase):
    def test_parse_hotel_url(self):
        url = (
            "https://www.onlinetours.ru/oteli/turkey/istanbul/example?"
            "adults=2&duration_from=7&duration_to=8&kids=0&"
            "start_from=2026-08-27&start_to=2026-08-28"
        )
        result = parse_hotel_params_from_url(url)
        self.assertEqual(result["country"], "Турция")
        self.assertEqual(result["adults"], 2)
        self.assertEqual(result["nights"], "7-8")
        self.assertEqual(result["dates"], "27.08.2026 - 28.08.2026")
        self.assertEqual(result["kids_info"], "")

    def test_read_hotel_urls_ignores_comments(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "hotels.txt"
            path.write_text("# comment\nhttps://example.test/hotel\n\n", encoding="utf-8")
            self.assertEqual(read_hotel_urls_config(path), ["https://example.test/hotel"])

    def test_read_departure_cities_preserves_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cities.txt"
            path.write_text("Москва\n# note\nКазань\n", encoding="utf-8")
            self.assertEqual(read_departure_cities(path), ["Москва", "Казань"])


if __name__ == "__main__":
    unittest.main()
