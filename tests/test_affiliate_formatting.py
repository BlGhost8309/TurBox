import unittest
from datetime import date

from turbox.affiliate_formatting import (
    extract_hotel_name_from_file,
    format_output_line,
    generate_sub_id_for_collection,
    parse_collection_line,
    parse_hotel_city_line,
    parse_russian_date,
    transliterate,
)


class AffiliateFormattingTests(unittest.TestCase):
    def test_collection_line_from_real_august_2026_format(self):
        line = (
            "1. Москва, Турция, 07.08.2026, ночей:7-8, взрослых:2 "
            "(Новая дата 5 - 13 авг | от 82748 | всё включено)"
        )
        self.assertEqual(
            parse_collection_line(line),
            (1, "Москва", "Турция", "7-8", "2", "5 - 13 авг", 82748, "всё включено"),
        )

    def test_format_output_line_matches_existing_output(self):
        self.assertEqual(
            format_output_line(1, "Москва", "Турция", "7-8", "2", "5 - 13 авг", 82748, "всё включено"),
            "1. Москва, Турция, ночей:7-8, взрослых:2, 5 - 13 авг, от 82748, всё включено",
        )

    def test_transliteration_keeps_custom_city_aliases(self):
        self.assertEqual(transliterate("Санкт-Петербург"), "spb")
        self.assertEqual(transliterate("Нижний Новгород"), "n_novgorod")

    def test_sub_id_is_deterministic_for_fixed_reference_date(self):
        reference = date(2026, 8, 21)
        self.assertEqual(
            parse_russian_date("5 - 13 авг", today=reference),
            "5-13_08_2026",
        )
        self.assertEqual(
            generate_sub_id_for_collection(
                "Москва", "Турция", "5 - 13 авг", 82748, today=reference
            ),
            "moskva_turkey_5_13_08_2026_pr_82748",
        )

    def test_hotel_city_line(self):
        self.assertEqual(
            parse_hotel_city_line(
                "1. Москва - от 108 446 р | https://www.onlinetours.ru/oteli/turkey/test"
            ),
            (1, "Москва", 108446, "https://www.onlinetours.ru/oteli/turkey/test"),
        )
        self.assertEqual(parse_hotel_city_line("2. Казань - NO_RESULTS"), (2, "Казань", 0, ""))

    def test_hotel_name_prefers_explicit_hotel_line(self):
        lines = [
            "Турция | 27.08.2026 | ночей: 7 | взрослых: 2 | Всё включено | Header Name",
            "Отель 1: Semt Luna Beach Hotel",
        ]
        self.assertEqual(extract_hotel_name_from_file(lines), "Semt Luna Beach Hotel")


if __name__ == "__main__":
    unittest.main()
