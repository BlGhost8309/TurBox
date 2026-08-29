import json
import tempfile
import unittest
from pathlib import Path

from turbox.query_generation import (
    generate_query_groups,
    load_query_templates,
    render_search_config,
    update_search_config,
)
from turbox.search_config import parse_config_links, parse_config_parameters, read_sections


class QueryGenerationTests(unittest.TestCase):
    def test_generates_cartesian_product_per_template(self):
        groups = generate_query_groups(
            [
                {
                    "cities": ["Москва", "Казань"],
                    "countries": ["Турция", "Египет"],
                    "date_range": "01.09.2026",
                    "nights": "7-8",
                    "adults": "2",
                    "filters": "цена:40000-120000",
                }
            ]
        )

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 4)
        self.assertEqual(
            groups[0][0],
            "Москва|Турция|01.09.2026|ночей:7-8|взрослых:2|цена:40000-120000",
        )
        self.assertEqual(
            groups[0][-1],
            "Казань|Египет|01.09.2026|ночей:7-8|взрослых:2|цена:40000-120000",
        )

    def test_render_preserves_parameters_and_replaces_old_requests(self):
        existing = """ПАРАМЕТРЫ
searchMinPriceData=false
# пользовательский комментарий

ЗАПРОСЫ
Старый|Запрос|01.01.2026|ночей:7|взрослых:2
"""
        rendered = render_search_config(
            existing,
            [["Москва|Турция|01.09.2026|ночей:7|взрослых:2"]],
        )

        self.assertIn("searchMinPriceData=false", rendered)
        self.assertIn("# пользовательский комментарий", rendered)
        self.assertNotIn("Старый|Запрос", rendered)
        self.assertIn("Москва|Турция", rendered)

    def test_update_produces_config_accepted_by_search_parser(self):
        data = {
            "templates": [
                {
                    "cities": ["Москва", "Казань"],
                    "countries": ["Турция"],
                    "date_range": "01.09.2026",
                    "nights": "7-8",
                    "adults": "2",
                    "filters": "цена:40000-120000|сортировка:цена",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            json_path = temp_path / "queries.json"
            output_path = temp_path / "url_generation_config.txt"
            json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            output_path.write_text(
                "ПАРАМЕТРЫ\nsearchMinPriceData=true\n\nЗАПРОСЫ\n",
                encoding="utf-8",
            )

            count = update_search_config(json_path, output_path)
            sections = read_sections(output_path)
            requests = parse_config_links(sections)

        self.assertEqual(count, 2)
        self.assertEqual(parse_config_parameters(sections), {"search_min_price_data": True})
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0][0:2], ("Москва", "Турция"))
        self.assertEqual(requests[1][0:2], ("Казань", "Турция"))

    def test_rejects_empty_city_list(self):
        data = {
            "templates": [
                {
                    "cities": [],
                    "countries": ["Турция"],
                    "date_range": "01.09.2026",
                    "nights": "7",
                    "adults": "2",
                }
            ]
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "queries.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cities"):
                load_query_templates(path)


if __name__ == "__main__":
    unittest.main()
