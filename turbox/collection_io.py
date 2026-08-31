"""I/O helpers for the collection pipeline that do not depend on Selenium."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

from turbox.affiliate_formatting import parse_collection_line

logger = logging.getLogger(__name__)

CollectionItem = Tuple[int, str, str, str, str, str, int, str, str]
NON_CONVERTIBLE_STATUSES = {"NO_RESULTS", "PRICE_PARSE_ERROR", "REQUEST_ERROR"}


def read_collection_urls_file(file_path: Path) -> List[CollectionItem]:
    """Read the legacy two-line collection format used between pipeline stages."""
    if not file_path.exists():
        raise FileNotFoundError(f"Файл {file_path} не найден")

    items: List[CollectionItem] = []
    lines = [line.rstrip() for line in file_path.read_text(encoding="utf-8").splitlines()]

    i = 0
    while i < len(lines):
        desc_line = lines[i]
        if not desc_line:
            i += 1
            continue

        # Необрабатываемые статусы записываются отдельным двухстрочным блоком.
        # Конвертер пропускает его целиком и не пытается принять статус за URL.
        if i + 1 < len(lines) and lines[i + 1].strip() in NON_CONVERTIBLE_STATUSES:
            status = lines[i + 1].strip()
            logger.info("Пропускаем %s: %s", status, desc_line)
            i += 2
            continue

        parsed = parse_collection_line(desc_line)
        if not parsed:
            logger.warning("Пропускаем строку: %s", desc_line)
            i += 1
            continue

        index, city, country, nights, adults, new_date_range, price, meal = parsed

        if i + 1 >= len(lines):
            logger.warning("Нет URL для индекса %s", index)
            break

        url = lines[i + 1]
        if not url.startswith("http"):
            logger.warning("Строка не похожа на URL: %s", url)
            i += 1
            continue

        items.append(
            (index, city, country, nights, adults, new_date_range, price, meal, url)
        )
        i += 2

    return items
