#!/usr/bin/env python3
"""Generate configs/url_generation_config.txt from a compact JSON file."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from turbox.paths import CONFIG_DIR
from turbox.query_generation import update_search_config


DEFAULT_JSON_CONFIG = CONFIG_DIR / "query_generator_config.json"
DEFAULT_OUTPUT = CONFIG_DIR / "url_generation_config.txt"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Создать декартово произведение городов и направлений для TurBox"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_JSON_CONFIG,
        help="JSON-конфиг шаблонов",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Рабочий url_generation_config.txt",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger("query_generator")

    try:
        count = update_search_config(args.config.resolve(), args.output.resolve())
    except (OSError, ValueError) as error:
        logger.error("Не удалось сформировать запросы: %s", error)
        return 1

    logger.info("Сформировано запросов: %s", count)
    logger.info("Обновлён файл: %s", args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
