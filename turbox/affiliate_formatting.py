"""Deterministic formatting and SubID helpers for affiliate conversion.

No Selenium or Travelpayouts UI calls live here. This boundary is intentional:
a future API-based affiliate client can replace the browser adapter without
changing these functions or their tests.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import List, Optional, Tuple

TRANSLIT_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    " ": "_", "-": "_", "’": "", "'": "",
}

CUSTOM_TRANSLIT = {
    "москва": "moskva",
    "санкт-петербург": "spb",
    "екатеринбург": "ekb",
    "казань": "kazan",
    "нижний новгород": "n_novgorod",
    "египет": "egipet",
    "турция": "turkey",
    "таиланд": "tailand",
    "шарм-эль-шейх": "sharm",
    "хургада": "hurgada",
    "оаэ": "oae",
    "индия": "indiya",
    "мальдивы": "maldivy",
}

logger = logging.getLogger(__name__)

MONTHS_RU = {
    "янв": "01", "фев": "02", "мар": "03", "апр": "04",
    "май": "05", "июн": "06", "июл": "07", "авг": "08",
    "сен": "09", "окт": "10", "ноя": "11", "дек": "12",
}


def transliterate(text: str) -> str:
    text = text.lower()
    for ru, en in CUSTOM_TRANSLIT.items():
        text = re.sub(r"\b" + ru + r"\b", en, text)
    result = [TRANSLIT_MAP.get(ch, ch if ch.isalnum() else "_") for ch in text]
    return re.sub(r"_+", "_", "".join(result)).strip("_")


def parse_russian_date(date_str: str, today: Optional[date] = None) -> str:
    """Convert short Russian date text to the legacy SubID date representation."""
    reference_date = today or date.today()

    def convert_single(value: str) -> str:
        value = value.strip()
        match = re.match(r"(\d{1,2})\s+([а-я]+)", value)
        if not match:
            return value.replace(" ", "_")
        day = int(match.group(1))
        month_name = match.group(2)[:3]
        month = MONTHS_RU.get(month_name)
        if not month:
            return value.replace(" ", "_")
        year = reference_date.year
        if int(month) < reference_date.month:
            year += 1
        return f"{day}_{month}_{year}"

    if " - " in date_str:
        start, end = date_str.split(" - ", 1)
        return f"{convert_single(start)}-{convert_single(end)}"
    return convert_single(date_str)


def parse_collection_line(line: str) -> Optional[Tuple[int, str, str, str, str, str, int, str]]:
    match = re.match(
        r"^(\d+)\.\s+([^,]+),\s+([^,]+),\s+(?:\d+\.\d+\.\d+(?:-\d+\.\d+\.\d+)?),\s+ночей:(\d+(?:-\d+)?),\s+взрослых:(\d+)\s+\(Новая дата\s+(.+?)(?:\s+\|\s+от\s+(\d+))?(?:\s+\|\s+([^)]+))?\)$",
        line,
    )
    if not match:
        logger.warning("Не удалось распарсить строку: %s", line)
        return None

    return (
        int(match.group(1)),
        match.group(2).strip(),
        match.group(3).strip(),
        match.group(4).strip(),
        match.group(5).strip(),
        match.group(6).strip(),
        int(match.group(7)) if match.group(7) else 0,
        match.group(8).strip() if match.group(8) else "",
    )


def format_output_line(
    index: int,
    city: str,
    country: str,
    nights: str,
    adults: str,
    new_date_range: str,
    price: int,
    meal: str = "",
) -> str:
    base = f"{index}. {city}, {country}, ночей:{nights}, взрослых:{adults}, {new_date_range}"
    base += f", от {price}" if price > 0 else ", ЦЕНА НЕ УКАЗАНА"
    if meal:
        base += f", {meal}"
    return base


def generate_sub_id_for_collection(
    city: str,
    country: str,
    new_date_range: str,
    price: int,
    today: Optional[date] = None,
) -> str:
    city_lat = transliterate(city)
    country_lat = transliterate(country)
    date_part = parse_russian_date(new_date_range, today=today)
    sub_id = f"{city_lat}_{country_lat}_{date_part}"
    if price > 0:
        sub_id += f"_pr_{price}"
    sub_id = re.sub(r"[^a-z0-9_]", "_", sub_id)
    return re.sub(r"_+", "_", sub_id).strip("_")


def generate_sub_id_fallback(city: str, country: str, price: int) -> str:
    city_lat = transliterate(city)
    country_lat = transliterate(country)
    if price > 0:
        return f"{city_lat}_{country_lat}_date_unknown_pr_{price}"
    return f"{city_lat}_{country_lat}_date_unknown"


def parse_hotel_city_line(line: str) -> Optional[Tuple[int, str, int, str]]:
    match = re.match(
        r"^(\d+)\.\s+(.*?)\s*-\s*(от\s+[\d\s\xa0]+р|NO_RESULTS)(?:\s*\|\s*(https?://.*))?$",
        line.strip(),
    )
    if not match:
        return None

    idx = int(match.group(1))
    city = match.group(2).strip()
    price_str = match.group(3).strip()
    url = match.group(4).strip() if match.group(4) else ""

    if price_str == "NO_RESULTS" or not url:
        return idx, city, 0, ""

    price_match = re.search(r"(\d+)", price_str.replace(" ", "").replace("\xa0", ""))
    price = int(price_match.group(1)) if price_match else 0
    return idx, city, price, url


def extract_hotel_name_from_file(lines: List[str]) -> str:
    for line in lines:
        if line.startswith("Отель "):
            match = re.search(r"Отель\s+\d+:\s*(.+)", line)
            if match:
                return match.group(1).strip()

    for line in lines:
        if "|" in line and not line.startswith("Отель"):
            parts = line.split("|")
            if len(parts) > 1:
                return parts[-1].strip()

    return "unknown_hotel"
