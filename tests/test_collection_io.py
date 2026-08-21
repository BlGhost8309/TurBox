import tempfile
import unittest
from pathlib import Path

from turbox.collection_io import read_collection_urls_file


class CollectionIoTests(unittest.TestCase):
    def test_reads_two_line_items_and_skips_blank_lines(self):
        content = """
1. Москва, Турция, 07.08.2026, ночей:7-8, взрослых:2 (Новая дата 5 - 13 авг | от 82748 | всё включено)
https://www.onlinetours.ru/tours/test1

2. Казань, Египет, 26.08.2026, ночей:7, взрослых:2 (Новая дата 27 авг | от 118508)
https://www.onlinetours.ru/tours/test2
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "collection_urls.txt"
            path.write_text(content, encoding="utf-8")
            items = read_collection_urls_file(path)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0][0:3], (1, "Москва", "Турция"))
        self.assertEqual(items[0][6], 82748)
        self.assertEqual(items[1][0:3], (2, "Казань", "Египет"))
        self.assertEqual(items[1][-1], "https://www.onlinetours.ru/tours/test2")

    def test_skips_no_results_as_one_block(self):
        content = """
1. Пермь, Кисловодск, 27.09.2026, ночей:7, взрослых:2
NO_RESULTS
2. Москва, Турция, 07.08.2026, ночей:7-8, взрослых:2 (Новая дата 5 - 13 авг | от 82748)
https://www.onlinetours.ru/tours/test
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "collection_urls.txt"
            path.write_text(content, encoding="utf-8")
            items = read_collection_urls_file(path)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0][0], 2)


if __name__ == "__main__":
    unittest.main()
