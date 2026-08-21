"""Parsing of the human-readable collection search configuration.

This module deliberately contains no Selenium code. It can be unit-tested
without opening a browser or touching OnlineTours.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qsl, urlparse, urlunparse

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "search_min_price_data": False,
}


def smart_split(line: str, delimiter: str = "|") -> List[str]:
    """Split by delimiter while ignoring delimiters inside parentheses."""
    result: List[str] = []
    current: List[str] = []
    depth = 0
    for char in line:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == delimiter and depth == 0:
            result.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        result.append("".join(current))
    return result


def split_filters_aware(filter_str: str) -> List[str]:
    """Split filter text by | while preserving | inside parentheses."""
    return smart_split(filter_str, "|")


def read_sections(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Не найден {path}")

    sections: Dict[str, List[str]] = {}
    current = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper() in ("ПАРАМЕТРЫ", "ЗАПРОСЫ"):
            current = line.upper()
            sections[current] = []
            continue
        if current:
            sections[current].append(line)

    return sections


def parse_config_parameters(sections: Dict[str, List[str]]) -> Dict[str, Any]:
    params = sections.get("ПАРАМЕТРЫ", [])
    config = DEFAULT_CONFIG.copy()

    for line in params:
        if line.startswith("searchMinPriceData="):
            val = line.split("=", 1)[1].strip().lower()
            config["search_min_price_data"] = val == "true"

    return config


def parse_extra_filters(filter_str: str) -> Dict[str, Any]:
    """Parse price, rating, meal and sorting filters from the legacy text DSL."""
    result: Dict[str, Any] = {
        "price_min": None,
        "price_max": None,
        "rating": None,
        "meal_ids": [],
        "sort": "popularity",
    }

    if not filter_str:
        return result

    meal_map = {
        "Всё включено": "739",
        "Ультра всё включено": "740",
        "3-разовое": "3",
        "2-разовое": "731",
        "Завтраки": "730",
    }

    for part in split_filters_aware(filter_str):
        part = part.strip()
        if part.startswith("цена:"):
            price_part = part[5:].strip()
            if "-" in price_part:
                min_str, max_str = price_part.split("-", 1)
                if min_str:
                    result["price_min"] = int(min_str)
                if max_str:
                    result["price_max"] = int(max_str)
            elif price_part:
                result["price_min"] = int(price_part)
        elif part.startswith("рейтинг:"):
            rating_val = int(part[8:].strip())
            if 5 <= rating_val <= 9:
                result["rating"] = rating_val
        elif part.startswith("сортировка:"):
            sort_val = part[11:].strip().lower()
            if sort_val == "цена":
                result["sort"] = "price"
            elif sort_val == "популярность":
                result["sort"] = "popularity"
        elif part.startswith("питание:"):
            meal_part = part[8:].strip()
            if meal_part.startswith("(") and meal_part.endswith(")"):
                meal_part = meal_part[1:-1]
                for meal in meal_part.split("|"):
                    meal = meal.strip()
                    if meal in meal_map:
                        result["meal_ids"].append(meal_map[meal])

    return result


def parse_config_links(sections: Dict[str, List[str]]) -> List[Tuple]:
    """Parse all entries from the ЗАПРОСЫ section preserving legacy tuple shape."""
    links = sections.get("ЗАПРОСЫ", [])
    requests: List[Tuple] = []

    for line in links:
        line = line.strip()
        if not line:
            continue

        extra_filters: Dict[str, Any] = {}
        parts = smart_split(line)

        filter_indices = [
            i
            for i, part in enumerate(parts)
            if part.startswith(("цена:", "рейтинг:", "сортировка:", "питание:"))
        ]

        if filter_indices:
            filter_parts = parts[filter_indices[0] :]
            filter_str = "|".join(filter_parts)
            extra_filters = parse_extra_filters(filter_str)
            parts = parts[: filter_indices[0]]

        if len(parts) < 5:
            logger.warning("Неверный формат строки, пропускаем: %s", line)
            continue

        city = parts[0]
        country = parts[1]
        date_range_str = parts[2]
        nights_part = parts[3]
        adults_part = parts[4]

        if "-" in date_range_str:
            start_str, end_str = date_range_str.split("-", 1)
            start_date = datetime.strptime(start_str.strip(), "%d.%m.%Y")
            end_date = datetime.strptime(end_str.strip(), "%d.%m.%Y")
        else:
            start_date = datetime.strptime(date_range_str.strip(), "%d.%m.%Y")
            end_date = start_date

        nights_match = re.search(r"ночей:(\d+)(?:-(\d+))?", nights_part, re.IGNORECASE)
        if not nights_match:
            logger.warning("Не удалось извлечь ночи из: %s", line)
            continue
        nights_min = int(nights_match.group(1))
        nights_max = int(nights_match.group(2)) if nights_match.group(2) else nights_min

        adults_match = re.search(r"взрослых:(\d+)", adults_part, re.IGNORECASE)
        if not adults_match:
            logger.warning("Не удалось извлечь взрослых из: %s", line)
            continue
        adults = int(adults_match.group(1))

        requests.append(
            (city, country, start_date, end_date, nights_min, nights_max, adults, extra_filters)
        )

    return requests


def build_filtered_url(base_url: str, filters: Dict[str, Any]) -> str:
    """Apply OnlineTours filter query parameters without browser interaction."""
    parsed = urlparse(base_url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))

    if filters.get("sort"):
        query_params["sort"] = filters["sort"]
    if filters.get("price_min") is not None:
        query_params["price_from"] = str(filters["price_min"])
    if filters.get("price_max") is not None:
        query_params["price_to"] = str(filters["price_max"])
    if filters.get("rating"):
        query_params["rating"] = str(filters["rating"])

    for key in list(query_params.keys()):
        if key.startswith("meal_type"):
            del query_params[key]

    meal_ids = filters.get("meal_ids", [])
    if meal_ids:
        query_params["meal_type[]"] = meal_ids

    new_query_parts: List[str] = []
    for key, value in query_params.items():
        if isinstance(value, list):
            for item in value:
                new_query_parts.append(f"{key}={item}")
        else:
            new_query_parts.append(f"{key}={value}")

    return urlunparse(parsed._replace(query="&".join(new_query_parts)))
