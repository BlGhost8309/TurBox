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
        lines.append(
            f"{o.hotel_name} "
            f"(город вылета - {o.departure_city}, страна - {o.arrival_country})"
        )
        lines.append(f"{o.price} — {o.book_url} — {o.details}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def _safe_filename(text: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]+', "_", text).strip()
    return safe or "Неизвестно"


def get_unique_result_path(city: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    base = _safe_filename(city)
    candidate = RESULTS_DIR / f"result_{base}.txt"

    if not candidate.exists():
        return candidate

    idx = 2
    while True:
        candidate = RESULTS_DIR / f"result_{base}_{idx}.txt"
        if not candidate.exists():
            return candidate
        idx += 1
