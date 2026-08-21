import json
import re
import logging
from pathlib import Path
from typing import List, Tuple
from models import ParsedOffer

RESULTS_DIR = Path("results")
PARAMS_FILE = Path("configs/collection_params.txt")
URLS_FILE = Path("configs/collection_urls.txt")


def read_collection_params(path: Path = PARAMS_FILE) -> Tuple[int, int, bool, int]:
    """
    Читает параметры фильтрации из файла.
    Формат: ключ=значение, возможны пробелы вокруг '='.
    Возвращает (min_price, max_price, search_min_price_data, hotel_num)
    """
    default = (0, 10**18, False, 0)

    if not path.exists():
        logging.getLogger(__name__).warning(f"Файл параметров не найден: {path}, используются значения по умолчанию")
        return default

    params = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, val = line.split('=', 1)
            key = key.strip().lower()
            val = val.strip()
            params[key] = val

    min_price = int(params.get("min_price", default[0]))
    max_price = int(params.get("max_price", default[1]))
    search_min_price_data = params.get("searchminpricedata", str(default[2])).lower() == "true"
    hotel_num = int(params.get("hotelnum", default[3]))

    return min_price, max_price, search_min_price_data, hotel_num


def read_collection_urls(path: Path = URLS_FILE) -> List[str]:
    """
    Читает список URL подборок из файла (по одному на строку).
    Игнорирует пустые строки и строки, начинающиеся с '#'.
    Если файл не найден, возвращает пустой список и логирует предупреждение.
    """
    if not path.exists():
        logging.getLogger(__name__).warning(f"Файл со ссылками не найден: {path}")
        return []

    urls = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith("http://") or line.startswith("https://"):
                urls.append(line)
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
    if path.suffix.lower() == '.txt':
        path = path.with_suffix('.json')
    path.parent.mkdir(parents=True, exist_ok=True)

    data = []
    for o in offers:
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
