import re
from pathlib import Path
from typing import List
from models import ParsedOffer

RESULTS_DIR = Path("results")


def parse_config_urls(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Не найден {path}")

    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            urls.append(line)

    if not urls:
        raise ValueError("В config.txt не найдено ни одной ссылки")

    return urls


def write_results(path: Path, offers: List[ParsedOffer]) -> None:
    offers = sorted(offers, key=lambda x: x.price)

    lines = []
    for o in offers:
        lines.append(f"{o.hotel_name} (город вылета - {o.departure_city})")
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
