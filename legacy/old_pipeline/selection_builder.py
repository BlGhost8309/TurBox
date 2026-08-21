#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для построения подборок туров из result_*.json (onlinetours) и кэша hotel_cache.json.
Работает полностью офлайн, без сетевых запросов.
"""

import json
import logging
import glob
import argparse
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Union
import re

# Настройка логгера: вывод в консоль и в файл selection_builder.log
logger = logging.getLogger("selection_builder")
logger.setLevel(logging.INFO)

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler("selection_builder.log", encoding="utf-8", mode="a")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

CACHE_FILE = Path("data/hotel_cache.json")
DEFAULT_SELECTIONS_DIR = Path("selections")

OUTPUT_FIELDS = [
    "hotel_name",
    "arrival_country",
    "departure_city",
    "price",
    "nights",
    "adults",
    "meal_type",
    "departure_date",
    "return_date",
    "book_url",
    "hotel_url",
    "stars",
    "rating",
    "top_hotel_rating",
    "hotel_url_on_top_hotels",
    "price_per_night",
    "price_per_night_per_person"
]


def normalize(s: str) -> str:
    s = s.strip().lower()
    return re.sub(r'\s+', ' ', s)


def parse_departure_date(date_str: str) -> Optional[date]:
    months_ru = {
        'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
        'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
    }
    match = re.match(r'(\d{1,2})\s+([а-я]+)', date_str)
    if not match:
        return None
    day = int(match.group(1))
    month_name = match.group(2)[:3]
    month = months_ru.get(month_name)
    if not month:
        return None
    today = date.today()
    year = today.year
    if month < today.month:
        year += 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


def load_config(config_path: Union[str, Path]) -> Dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {path}")
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    if "selections" not in config:
        raise ValueError("Конфигурация должна содержать поле 'selections'")
    return config


def find_and_load_tours(source_masks: Union[str, List[str]]) -> List[Dict[str, Any]]:
    if isinstance(source_masks, str):
        source_masks = [source_masks]

    tours = []
    for mask in source_masks:
        files = glob.glob(mask, recursive=False)
        if not files:
            logger.warning(f"По маске {mask} не найдено файлов")
        for file_path in files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    tours.extend(data)
                    logger.info(f"Загружено {len(data)} туров из {file_path}")
                else:
                    logger.warning(f"Файл {file_path} содержит не список, пропускаем")
            except Exception as e:
                logger.warning(f"Ошибка чтения {file_path}: {e}")
    if not tours:
        raise ValueError("Не найдено ни одного тура по указанным маскам")
    return tours


def load_hotel_cache() -> Dict[str, Any]:
    if not CACHE_FILE.exists():
        logger.warning(f"Файл кэша {CACHE_FILE} не найден. Обогащение рейтингами не будет выполнено.")
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        logger.info(f"Загружено {len(cache)} записей из кэша")
        return cache
    except Exception as e:
        logger.warning(f"Ошибка загрузки кэша: {e}")
        return {}


def enrich_tours_with_cache(tours: List[Dict], cache: Dict[str, Any]) -> List[Dict]:
    enriched = []
    for tour in tours:
        hotel_name = tour.get("hotel_name", "")
        arrival_country = tour.get("arrival_country", "")
        if hotel_name and arrival_country:
            key = f"{normalize(hotel_name)}|{normalize(arrival_country)}"
            cached = cache.get(key)
            if cached and cached.get("found", False):
                tour["top_hotel_rating"] = cached.get("top_hotel_rating")
                tour["hotel_url_on_top_hotels"] = cached.get("hotel_url_on_top_hotels")
            else:
                tour["top_hotel_rating"] = None
                tour["hotel_url_on_top_hotels"] = None
        else:
            tour["top_hotel_rating"] = None
            tour["hotel_url_on_top_hotels"] = None

        nights = tour.get("nights", 0)
        price = tour.get("price", 0)
        adults = tour.get("adults", 1)
        tour["price_per_night"] = round(price / nights, 2) if nights > 0 else 0
        tour["price_per_night_per_person"] = round(price / nights / adults, 2) if nights > 0 and adults > 0 else 0

        enriched.append(tour)
    return enriched


def apply_filters(tours: List[Dict], filters: Dict[str, Any], logger) -> List[Dict]:
    """Применяет фильтры, логирует причины отсева."""
    if not filters:
        return tours

    filtered = []
    stats = {
        "arrival_country": 0,
        "departure_cities": 0,
        "price": 0,
        "nights": 0,
        "meal_type": 0,
        "top_hotel_rating": 0,
        "onlinetours_rating": 0,
        "stars": 0,
    }

    for tour in tours:
        ok = True
        reason = None

        # arrival_country
        if "arrival_country" in filters:
            val = filters["arrival_country"]
            if isinstance(val, str):
                if tour.get("arrival_country") != val:
                    ok = False
                    reason = f"arrival_country != {val}"
                    stats["arrival_country"] += 1
            elif isinstance(val, list):
                if tour.get("arrival_country") not in val:
                    ok = False
                    reason = f"arrival_country not in {val}"
                    stats["arrival_country"] += 1

        # departure_cities
        if ok and "departure_cities" in filters:
            if tour.get("departure_city") not in filters["departure_cities"]:
                ok = False
                reason = f"departure_city not in {filters['departure_cities']}"
                stats["departure_cities"] += 1

        # price_min / price_max
        if ok and "price_min" in filters:
            if tour.get("price", 0) < filters["price_min"]:
                ok = False
                reason = f"price < {filters['price_min']}"
                stats["price"] += 1
        if ok and "price_max" in filters:
            if tour.get("price", 0) > filters["price_max"]:
                ok = False
                reason = f"price > {filters['price_max']}"
                stats["price"] += 1

        # nights_min / nights_max
        if ok and "nights_min" in filters:
            if tour.get("nights", 0) < filters["nights_min"]:
                ok = False
                reason = f"nights < {filters['nights_min']}"
                stats["nights"] += 1
        if ok and "nights_max" in filters:
            if tour.get("nights", 0) > filters["nights_max"]:
                ok = False
                reason = f"nights > {filters['nights_max']}"
                stats["nights"] += 1

        # meal_type
        if ok and "meal_type" in filters:
            if tour.get("meal_type", "") not in filters["meal_type"]:
                ok = False
                reason = f"meal_type '{tour.get('meal_type')}' not in {filters['meal_type']}"
                stats["meal_type"] += 1

        # top_hotel_rating (с учётом allow_null)
        if ok and "min_top_hotel_rating" in filters:
            rating = tour.get("top_hotel_rating")
            min_val = filters["min_top_hotel_rating"]
            allow_null = filters.get("allow_null_top_hotel_rating", False)
            if rating is None:
                if not allow_null:
                    ok = False
                    reason = f"top_hotel_rating is None (null not allowed)"
                    stats["top_hotel_rating"] += 1
                # если allow_null, то пропускаем
            elif rating < min_val:
                ok = False
                reason = f"top_hotel_rating {rating} < {min_val}"
                stats["top_hotel_rating"] += 1

        # rating (onlinetours)
        if ok and "min_rating" in filters:
            if tour.get("rating", 0.0) < filters["min_rating"]:
                ok = False
                reason = f"rating {tour.get('rating')} < {filters['min_rating']}"
                stats["onlinetours_rating"] += 1

        # stars
        if ok and "stars" in filters:
            if tour.get("stars", 0) not in filters["stars"]:
                ok = False
                reason = f"stars {tour.get('stars')} not in {filters['stars']}"
                stats["stars"] += 1

        if ok:
            filtered.append(tour)
        else:
            logger.debug(f"Отсеян тур '{tour.get('hotel_name')}': {reason}")

    # Логируем статистику отсевов
    total_initial = len(tours)
    total_filtered = len(filtered)
    logger.info(f"Отсеяно фильтрами: {total_initial - total_filtered}")
    for filter_name, count in stats.items():
        if count > 0:
            logger.info(f"  - {filter_name}: отсечено {count}")
    return filtered

def sort_tours(tours: List[Dict], sort_config: Optional[Dict[str, str]]) -> List[Dict]:
    if not sort_config:
        return tours

    field = sort_config.get("field")
    order = sort_config.get("order", "asc")
    if not field:
        return tours

    if field == "departure_date":
        def key_func(t):
            dt = parse_departure_date(t.get("departure_date", ""))
            return dt if dt else date.max
        reverse = (order == "desc")
        return sorted(tours, key=key_func, reverse=reverse)
    elif field in ("price", "nights", "price_per_night", "price_per_night_per_person",
                   "top_hotel_rating", "rating", "stars"):
        reverse = (order == "desc")
        return sorted(tours, key=lambda t: t.get(field, 0) if t.get(field) is not None else 0, reverse=reverse)
    else:
        logger.warning(f"Поле сортировки '{field}' не поддерживается")
        return tours


def _filter_tour_fields(tour: Dict[str, Any]) -> Dict[str, Any]:
    filtered = {}
    for field in OUTPUT_FIELDS:
        if field in tour:
            filtered[field] = tour[field]
    return filtered


def save_selection(tours: List[Dict], selection_config: Dict[str, Any],
                   output_path: Path, csv_flag: bool) -> None:
    cleaned_tours = [_filter_tour_fields(t) for t in tours]

    result = {
        "selection_name": selection_config.get("name"),
        "config": selection_config,
        "generated": datetime.now().isoformat(),
        "tours": cleaned_tours
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"Сохранён JSON: {output_path}")

    if csv_flag:
        csv_path = output_path.with_suffix(".csv")
        import csv
        fieldnames = [
            "hotel_name", "departure_city", "arrival_country", "price", "nights",
            "meal_type", "top_hotel_rating", "rating", "stars", "book_url",
            "departure_date", "return_date", "price_per_night", "price_per_night_per_person"
        ]
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
            writer.writeheader()
            for tour in cleaned_tours:
                row = {k: tour.get(k, "") for k in fieldnames}
                writer.writerow(row)
        logger.info(f"Сохранён CSV: {csv_path}")


def build_selection(selection_cfg: Dict[str, Any], csv_flag: bool = False) -> None:
    name = selection_cfg.get("name", "unnamed")
    logger.info(f"Обработка подборки: {name}")

    source_mask = selection_cfg.get("source_mask")
    if not source_mask:
        raise ValueError(f"В подборке {name} отсутствует source_mask")

    tours = find_and_load_tours(source_mask)
    total_loaded = len(tours)
    logger.info(f"Прочитано туров из исходных файлов: {total_loaded}")

    cache = load_hotel_cache()
    tours = enrich_tours_with_cache(tours, cache)

    filters = selection_cfg.get("filters", {})
    before_filter = len(tours)
    tours = apply_filters(tours, filters, logger)
    after_filter = len(tours)
    filtered_out = before_filter - after_filter
    logger.info(f"Отсеяно фильтрами: {filtered_out}")
    logger.info(f"После фильтрации осталось: {after_filter}")

    sort_cfg = selection_cfg.get("sort")
    tours = sort_tours(tours, sort_cfg)

    limit = selection_cfg.get("limit")
    if limit and isinstance(limit, int) and limit > 0:
        before_limit = len(tours)
        tours = tours[:limit]
        after_limit = len(tours)
        logger.info(f"Лимит: {limit}, отсечено {before_limit - after_limit}, оставлено {after_limit}")
    else:
        after_limit = len(tours)

    output_file = selection_cfg.get("output_file")
    if output_file:
        out_path = Path(output_file)
    else:
        out_path = DEFAULT_SELECTIONS_DIR / f"{name}.json"

    save_selection(tours, selection_cfg, out_path, csv_flag)
    logger.info(f"Подборка {name} завершена, сохранено туров: {after_limit}")
    logger.info(f"Выходной файл: {out_path}\n")


def main():
    parser = argparse.ArgumentParser(description="Построение подборок туров из result_*.json и кэша")
    parser.add_argument("--config", default="/configs/selection_config.json",
                        help="Путь к конфигурационному файлу (по умолчанию selection_config.json)")
    parser.add_argument("--csv", action="store_true",
                        help="Дополнительно сохранять CSV-файлы для каждой подборки")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        selections = config.get("selections", [])
        if not selections:
            logger.error("В конфигурации нет ни одной подборки (selections: [])")
            return

        processed = 0
        for sel in selections:
            try:
                build_selection(sel, csv_flag=args.csv)
                processed += 1
            except Exception as e:
                logger.error(f"Ошибка при построении подборки {sel.get('name', '?')}: {e}", exc_info=True)

        logger.info(f"Обработано {processed} подборок, результаты в папке {DEFAULT_SELECTIONS_DIR}/")

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)


if __name__ == "__main__":
    main()
