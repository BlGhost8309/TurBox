import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from models import ParsedOffer

RESULTS_DIR = Path("results")


def _read_sections(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Не найден {path}")

    sections: Dict[str, List[str]] = {}
    current = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper() in ("ПАРАМЕТРЫ", "ССЫЛКИ"):
            current = line.upper()
            sections[current] = []
            continue
        if current:
            sections[current].append(line)
    return sections


def parse_config_parameters(path: Path) -> Tuple[int, int, bool]:
    sections = _read_sections(path)
    params = sections.get("ПАРАМЕТРЫ", [])

    min_price = 0
    max_price = 10**18
    search_min_price_data = False

    for line in params:
        if line.startswith("min_price="):
            val = line.split("=", 1)[1].strip()
            min_price = int(val) if val else min_price
        elif line.startswith("max_price="):
            val = line.split("=", 1)[1].strip()
            max_price = int(val) if val else max_price
        elif line.startswith("searchMinPriceData="):
            val = line.split("=", 1)[1].strip().lower()
            search_min_price_data = val == "true"

    return min_price, max_price, search_min_price_data


def parse_config_urls(path: Path) -> List[str]:
    sections = _read_sections(path)
    urls = []
    for line in sections.get("ССЫЛКИ", []):
        if line.startswith("http://") or line.startswith("https://"):
            urls.append(line)
    if not urls:
        raise ValueError("В секции ССЫЛКИ не найдено ни одной ссылки")
    return urls


def write_results(path: Path, offers: List[ParsedOffer]) -> None:
    offers = sorted(offers, key=lambda x: x.price)

    lines = []
    for o in offers:
        parts = []
        if o.stars > 0:
            parts.append(f"{o.stars}★")
        if o.rating > 0:
            parts.append(f"Рейтинг {o.rating:.1f}")
        parts.append(f"Город вылета - {o.departure_city}")
        parts.append(f"Страна - {o.arrival_country}")

        hotel_line = o.hotel_name
        if parts:
            hotel_line += ". " + " | ".join(parts)

        lines.append(hotel_line)
        lines.append(f"{o.price} — {o.book_url} — {o.details}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_json_results(path: Path, offers: List[ParsedOffer]) -> None:
    """
    Сохраняет список предложений в JSON-файл.
    path должен быть с расширением .json (или будет заменено).
    """
    # Если передан путь с .txt, заменим на .json (на случай вызова с txt-путём)
    if path.suffix.lower() == '.txt':
        path = path.with_suffix('.json')
    # Убедимся, что родительская директория существует
    path.parent.mkdir(parents=True, exist_ok=True)

    data = []
    for o in offers:
        # Преобразуем dataclass в словарь
        item = {
            "source_url": o.source_url,
            "hotel_url": o.hotel_url,
            "hotel_name": o.hotel_name,
            "departure_city": o.departure_city,
            "arrival_country": o.arrival_country,
            "price": o.price,
            "book_url": o.book_url,
            "details": o.details,
            "rating": o.rating,
            "stars": o.stars,
            "nights": o.nights,
            "meal_type": o.meal_type,
            "adults": o.adults,
            "departure_date": o.departure_date,
            "return_date": o.return_date,
        }
        data.append(item)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logging.getLogger(__name__).info(f"JSON сохранён: {path}")


def _safe_filename(text: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]+', "_", text).strip()
    return safe or "Неизвестно"


def get_unique_result_path(departure_city: str, arrival_country: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    base = f"{_safe_filename(departure_city)}-{_safe_filename(arrival_country)}"
    candidate = RESULTS_DIR / f"result_{base}.txt"

    if not candidate.exists():
        return candidate

    idx = 2
    while True:
        candidate = RESULTS_DIR / f"result_{base}_{idx}.txt"
        if not candidate.exists():
            return candidate
        idx += 1
