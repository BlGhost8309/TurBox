"""Fast local Stage 1 validation that does not open Chrome."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT_BOOTSTRAP = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_BOOTSTRAP))

from turbox.collection_io import read_collection_urls_file
from turbox.hotel_config import read_departure_cities, read_hotel_urls_config
from turbox.paths import CONFIG_DIR, PROJECT_ROOT
from turbox.search_config import parse_config_links, parse_config_parameters, read_sections


def validate_configs() -> None:
    sections = read_sections(CONFIG_DIR / "url_generation_config.txt")
    params = parse_config_parameters(sections)
    requests = parse_config_links(sections)
    hotels = read_hotel_urls_config(CONFIG_DIR / "hotel_urls.txt")
    cities = read_departure_cities(CONFIG_DIR / "departure_cities.txt")
    collection_file = CONFIG_DIR / "collection_urls.txt"
    collection_items = read_collection_urls_file(collection_file) if collection_file.exists() else []

    if not requests:
        raise RuntimeError("В url_generation_config.txt нет валидных запросов")
    if not hotels:
        raise RuntimeError("В hotel_urls.txt нет валидных URL")
    if not cities:
        raise RuntimeError("В departure_cities.txt нет городов")

    print(f"[OK] PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"[OK] searchMinPriceData: {params['search_min_price_data']}")
    print(f"[OK] Валидных запросов: {len(requests)}")
    print(f"[OK] URL отелей: {len(hotels)}")
    print(f"[OK] Городов hotel-mode: {len(cities)}")
    if collection_items:
        print(f"[OK] Текущий collection_urls.txt разбирается: {len(collection_items)} записей")
    duplicates = sorted({city for city in cities if cities.count(city) > 1})
    if duplicates:
        print(f"[WARN] Повторяющиеся города: {', '.join(duplicates)}")


def run_tests() -> bool:
    suite = unittest.defaultTestLoader.discover(str(PROJECT_ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


def main() -> int:
    print("=== TurBox Stage 1: быстрая проверка без браузера ===")
    try:
        validate_configs()
    except Exception as exc:
        print(f"[FAIL] Ошибка конфигурации: {exc}")
        return 2

    print("\n=== Unit tests ===")
    if not run_tests():
        return 3

    print("\n[OK] Stage 1 локальные проверки пройдены.")
    print("Следующий уровень — живой smoke-test OnlineTours/Travelpayouts по TEST_PLAN.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
