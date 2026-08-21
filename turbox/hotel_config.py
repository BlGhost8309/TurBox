"""Site-independent helpers for hotel-by-city mode."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List
from urllib.parse import parse_qs, urlparse

from turbox.paths import CONFIG_DIR


def read_hotel_urls_config(path: Path = CONFIG_DIR / "hotel_urls.txt") -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Не найден {path}")

    urls: List[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("http"):
            urls.append(line)

    if not urls:
        raise ValueError("В hotel_urls.txt не найдено ни одной ссылки на отель")
    return urls


def read_departure_cities(path: Path = CONFIG_DIR / "departure_cities.txt") -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Не найден {path}")
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def parse_hotel_params_from_url(url: str) -> Dict[str, object]:
    """Extract country, dates, nights and tourists from an OnlineTours hotel URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    path_parts = parsed.path.strip("/").split("/")
    country_slug = path_parts[1] if len(path_parts) > 1 else "unknown"
    country_map = {
        "turkey": "Турция",
        "egipet": "Египет",
        "tailand": "Таиланд",
        "oae": "ОАЭ",
        "indiya": "Индия",
        "maldivy": "Мальдивы",
        "russia": "Россия",
        "abkhazia": "Абхазия",
    }
    country = country_map.get(country_slug, country_slug.capitalize())

    adults = int(params.get("adults", ["2"])[0])

    duration_from = params.get("duration_from", [None])[0]
    duration_to = params.get("duration_to", [None])[0]
    if duration_from and duration_to:
        nights = f"{duration_from}-{duration_to}" if duration_from != duration_to else duration_from
    else:
        nights = "N/A"

    start_from = params.get("start_from", [None])[0]
    start_to = params.get("start_to", [None])[0]
    if start_from:
        try:
            d_from = datetime.strptime(start_from, "%Y-%m-%d").strftime("%d.%m.%Y")
            d_to = (
                datetime.strptime(start_to, "%Y-%m-%d").strftime("%d.%m.%Y")
                if start_to
                else d_from
            )
            dates = f"{d_from} - {d_to}" if d_from != d_to else d_from
        except ValueError:
            dates = f"{start_from} - {start_to}" if start_to else start_from
    else:
        dates = "Даты не указаны"

    kids_count = int(params.get("kids", ["0"])[0])
    kids_info = f"детей: {kids_count}" if kids_count > 0 else ""

    return {
        "country": country,
        "adults": adults,
        "nights": nights,
        "dates": dates,
        "kids_info": kids_info,
    }
