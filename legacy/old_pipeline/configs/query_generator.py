#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# === КОНФИГУРАЦИЯ ===
CONFIG_FILE = Path("query_generator_config.json")
OUTPUT_DIR = Path("generated_queries")
DEFAULT_OUTPUT_PREFIX = "queries"

# ВАЖНО (безопасность): этот скрипт генерирует входные данные для collection_url_generator.
# Ничего чувствительного здесь нет, но если будешь хранить реальные email/password в соседних файлах — будь осторожен.

# === ЛОГИРОВАНИЕ ===
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("query_generator")

def load_config(config_path: Path) -> Dict[str, Any]:
    """Загружает JSON-конфигурацию"""
    if not config_path.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    if "templates" not in config:
        raise ValueError("Конфигурация должна содержать поле 'templates'")

    return config

def generate_queries(template: Dict[str, Any]) -> List[str]:
    """
    Генерирует запросы для одного шаблона (декартово произведение городов и стран)
    """
    cities = template.get("cities", [])
    countries = template.get("countries", [])
    date_range = template.get("date_range", "")
    nights = template.get("nights", "")
    adults = template.get("adults", "")
    filters = template.get("filters", "")

    if not cities or not countries:
        logger.warning("Пропущен шаблон: нет городов или стран")
        return []

    queries = []
    for city in cities:
        for country in countries:
            query = f"{city}|{country}|{date_range}|ночей:{nights}|взрослых:{adults}"
            if filters:
                query += f"|{filters}"
            queries.append(query)

    logger.info(f"Сгенерировано {len(queries)} запросов (городов: {len(cities)}, стран: {len(countries)})")
    return queries

def save_queries(all_queries_groups: List[List[str]], output_path: Path, mode: str = "w") -> None:
    """Сохраняет запросы в файл, разделяя группы пустой строкой"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    with open(output_path, mode, encoding="utf-8") as f:
        for idx, queries_group in enumerate(all_queries_groups):
            for query in queries_group:
                f.write(query + "\n")
                total += 1
            # После каждой группы, кроме последней, добавляем пустую строку
            if idx < len(all_queries_groups) - 1:
                f.write("\n")

    logger.info(f"Сохранено {total} запросов в {output_path}")

def generate_output_filename(prefix: str = DEFAULT_OUTPUT_PREFIX) -> str:
    """Генерирует имя файла с датой и временем"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{prefix}_{timestamp}.txt"

def main():
    parser = argparse.ArgumentParser(description="Генератор запросов для url_generation_config.txt")
    parser.add_argument("--config", "-c", help="Путь к JSON-конфигу (по умолчанию query_generator_config.json)")
    parser.add_argument("--output", "-o", help="Путь к выходному файлу (если не указан, создаётся в папке generated_queries с датой)")
    parser.add_argument("--append", "-a", action="store_true", help="Дописать в конец существующего файла (вместо перезаписи)")
    parser.add_argument("--prefix", "-p", default=DEFAULT_OUTPUT_PREFIX, help="Префикс для имени файла (по умолчанию 'queries')")
    args = parser.parse_args()

    # Определяем путь к конфигу
    config_path = Path(args.config) if args.config else CONFIG_FILE

    try:
        # Загружаем конфиг
        config = load_config(config_path)
        templates = config.get("templates", [])

        if not templates:
            logger.error("Нет ни одного шаблона в конфигурации")
            input("\nНажмите Enter для выхода...")
            return

        logger.info(f"Загружено шаблонов: {len(templates)}")

        # Генерируем запросы для всех шаблонов (каждая группа отдельно)
        all_queries_groups = []
        for idx, template in enumerate(templates, 1):
            logger.info(f"\nОбработка шаблона #{idx}")
            queries = generate_queries(template)
            if queries:
                all_queries_groups.append(queries)

        if not all_queries_groups:
            logger.error("Не сгенерировано ни одного запроса")
            input("\nНажмите Enter для выхода...")
            return

        # Определяем выходной файл
        if args.output:
            output_path = Path(args.output)
        else:
            filename = generate_output_filename(args.prefix)
            output_path = OUTPUT_DIR / filename

        # Сохраняем результат
        mode = "a" if args.append else "w"
        save_queries(all_queries_groups, output_path, mode)

        total_queries = sum(len(g) for g in all_queries_groups)
        logger.info(f"\n{'='*60}")
        logger.info(f"Готово! Сгенерировано запросов: {total_queries} в {len(all_queries_groups)} группах")
        logger.info(f"Файл сохранён: {output_path}")
        logger.info(f"{'='*60}")

    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)

    input("\nНажмите Enter для выхода...")

if __name__ == "__main__":
    main()
