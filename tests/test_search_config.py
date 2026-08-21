import tempfile
import unittest
from pathlib import Path

from turbox.search_config import (
    build_filtered_url,
    parse_config_links,
    parse_config_parameters,
    parse_extra_filters,
    read_sections,
    smart_split,
)


class SearchConfigTests(unittest.TestCase):
    def test_smart_split_keeps_meal_group_together(self):
        line = "Москва|Турция|питание:(Всё включено|Ультра всё включено)|сортировка:цена"
        self.assertEqual(
            smart_split(line),
            [
                "Москва",
                "Турция",
                "питание:(Всё включено|Ультра всё включено)",
                "сортировка:цена",
            ],
        )

    def test_parse_extra_filters_preserves_current_ids(self):
        filters = parse_extra_filters(
            "цена:40000-120000|рейтинг:5|питание:(Всё включено|Ультра всё включено)|сортировка:цена"
        )
        self.assertEqual(filters["price_min"], 40000)
        self.assertEqual(filters["price_max"], 120000)
        self.assertEqual(filters["rating"], 5)
        self.assertEqual(filters["meal_ids"], ["739", "740"])
        self.assertEqual(filters["sort"], "price")

    def test_parse_full_request(self):
        content = """ПАРАМЕТРЫ
searchMinPriceData=true

ЗАПРОСЫ
Москва|Турция|27.08.2026|ночей:7-8|взрослых:2|цена:40000-120000|рейтинг:5|питание:(Всё включено|Ультра всё включено)|сортировка:цена
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.txt"
            path.write_text(content, encoding="utf-8")
            sections = read_sections(path)

        self.assertEqual(parse_config_parameters(sections), {"search_min_price_data": True})
        requests = parse_config_links(sections)
        self.assertEqual(len(requests), 1)
        city, country, start, end, nights_min, nights_max, adults, filters = requests[0]
        self.assertEqual((city, country), ("Москва", "Турция"))
        self.assertEqual(start.strftime("%d.%m.%Y"), "27.08.2026")
        self.assertEqual(end, start)
        self.assertEqual((nights_min, nights_max, adults), (7, 8, 2))
        self.assertEqual(filters["meal_ids"], ["739", "740"])

    def test_build_filtered_url_replaces_meal_filter(self):
        base = "https://www.onlinetours.ru/tours/test?ticket_strategy=include&meal_type%5B%5D=730"
        filters = {
            "price_min": 40000,
            "price_max": 120000,
            "rating": 5,
            "meal_ids": ["739", "740"],
            "sort": "price",
        }
        result = build_filtered_url(base, filters)
        self.assertEqual(
            result,
            "https://www.onlinetours.ru/tours/test?ticket_strategy=include&sort=price&price_from=40000&price_to=120000&rating=5&meal_type[]=739&meal_type[]=740",
        )


if __name__ == "__main__":
    unittest.main()
