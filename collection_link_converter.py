#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import time
import random
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple, List
import argparse

import browser
from browser import init_selenium
from link_converter import login, get_partner_link, save_debug_pack  # Selenium adapter (Stage 1: intentionally preserved)
from turbox.affiliate_formatting import (
    extract_hotel_name_from_file,
    format_output_line,
    generate_sub_id_fallback,
    generate_sub_id_for_collection,
    parse_collection_line,
    parse_hotel_city_line,
    parse_russian_date,
    transliterate,
)
from turbox.paths import CONFIG_DIR, DEBUG_DIR, POSTS_COLLECTIONS_DIR
from turbox.collection_io import read_collection_urls_file

# === КОНФИГУРАЦИЯ ===
INPUT_FILE = CONFIG_DIR / "collection_urls.txt"
OUTPUT_DIR = POSTS_COLLECTIONS_DIR
DEBUG_MODE = False  # ВАЖНО: False для продакшена. Включи только при отладке.

# === БЕЗОПАСНОСТЬ (для тебя) ===
# Этот скрипт использует логин в Travelpayouts (через login() из link_converter).
# Учётные данные сейчас берутся из configs/travelpayoutsSetup.txt (Email / Password).
# Это чувствительно! Не давай доступ к этой папке посторонним.
# DEBUG_MODE=False — дебаг-паки не должны сохранять куки.
# Если будешь отлаживать — временно поставь True, но потом верни обратно.

DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# === ЛОГИРОВАНИЕ ===
log_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_fmt)
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler(DEBUG_DIR / "debug_collection_converter.log", mode="w", encoding="utf-8")
file_handler.setFormatter(log_fmt)
file_handler.setLevel(logging.DEBUG)

logger = logging.getLogger("collection_link_converter")
logger.setLevel(logging.DEBUG)
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Форматирование и SubID вынесены в turbox.affiliate_formatting.


def convert_collection_urls(driver, items: List[Tuple], cache: Dict) -> List[Tuple[int, str, str]]:
    """
    Конвертирует URL в партнёрские ссылки.
    Возвращает список (index, formatted_line, partner_url or "ЦЕНА НЕ УКАЗАНА")
    """
    results = []
    for idx, (index, city, country, nights, adults, new_date_range, price, meal, original_url) in enumerate(items, 1):
        logger.info(f"\n[{idx}/{len(items)}] Обработка подборки #{index}")
        logger.info(f"Город: {city}, Страна: {country}")
        logger.info(f"Новая дата: {new_date_range}, Цена: {price if price > 0 else 'НЕ УКАЗАНА'}, Питание: {meal or 'не указано'}")
        logger.info(f"URL: {original_url}")

        formatted_line = format_output_line(index, city, country, nights, adults, new_date_range, price, meal)
        logger.info(f"Форматированная строка: {formatted_line}")

        if price == 0:
            logger.warning(f"Цена не указана, пропускаем конвертацию ссылки")
            results.append((index, formatted_line, "ЦЕНА НЕ УКАЗАНА"))
        else:
            try:
                sub_id = generate_sub_id_for_collection(city, country, new_date_range, price)
            except Exception as e:
                logger.warning(f"Ошибка генерации sub_id: {e}, используем fallback")
                sub_id = generate_sub_id_fallback(city, country, price)

            logger.info(f"Сгенерирован sub_id: {sub_id}")
            partner_url = get_partner_link(driver, original_url, sub_id, cache)

            if partner_url:
                results.append((index, formatted_line, partner_url))
                logger.info(f"✓ Получена партнёрская ссылка: {partner_url[:80]}...")
            else:
                logger.error(f"✗ Не удалось получить партнёрскую ссылку для {original_url}")
                results.append((index, formatted_line, original_url))

        if idx < len(items):
            # Небольшая пауза между подборками, чтобы не долбить сервис
            time.sleep(random.uniform(1.0, 2.5))

    return results

def save_results(results: List[Tuple[int, str, str]], output_dir: Path) -> Path:
    """Сохраняет результаты в файл"""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = output_dir / f"collection_{timestamp}.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        for index, formatted_line, url in results:
            f.write(f"{formatted_line}\n")
            f.write(f"{url}\n")

    logger.info(f"Сохранено {len(results)} подборок в {output_file}")
    return output_file

# ============================================================
# НОВЫЕ ФУНКЦИИ ДЛЯ РЕЖИМА HOTEL CITIES
# ============================================================



def run_hotel_city_converter_mode(input_file: Path, driver, cache: Dict) -> Path:
    """Обрабатывает файл hotel_cities_*.txt и заменяет ссылки на партнёрские."""
    logger.info(f"Обработка файла отелей: {input_file}")

    with open(input_file, "r", encoding="utf-8") as f:
        lines = [line.rstrip('\n') for line in f.readlines()]

    hotel_name = extract_hotel_name_from_file(lines)
    # Ограничиваем длину названия отеля в sub_id, чтобы не превысить лимиты
    hotel_name_lat = transliterate(hotel_name)[:30]

    output_lines = []
    processed_count = 0

    for line in lines:
        parsed = parse_hotel_city_line(line)
        if parsed:
            idx, city, price, url = parsed
            if price > 0 and url:
                city_lat = transliterate(city)
                # Формат sub_id: город_отель_цена (например: moskva_semt_luna_beach_108446)
                sub_id = f"{city_lat}_{hotel_name_lat}_{price}"
                sub_id = re.sub(r'[^a-z0-9_]', '_', sub_id)
                sub_id = re.sub(r'_+', '_', sub_id).strip('_')

                logger.info(f"[{idx}] Конвертация: {city} | Цена: {price} | sub_id: {sub_id}")
                partner_url = get_partner_link(driver, url, sub_id, cache)

                if partner_url:
                    new_line = f"{idx}. {city} - от {price} р | {partner_url}"
                    output_lines.append(new_line)
                    processed_count += 1
                    logger.info(f"✓ Получена партнёрская ссылка")
                    time.sleep(random.uniform(1.0, 2.0))  # Защита от частых запросов
                else:
                    logger.error(f"✗ Не удалось получить ссылку для {url}")
                    output_lines.append(line)  # Оставляем оригинал при ошибке
            else:
                output_lines.append(line)  # NO_RESULTS или нет URL
        else:
            output_lines.append(line)  # Заголовки и пустые строки оставляем как есть

    # Сохранение результата
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = OUTPUT_DIR / f"hotel_cities_PARTNERS_{timestamp}.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))

    logger.info(f"Сохранено {processed_count} партнёрских ссылок в {output_file}")
    return output_file

# ============================================================
# КОНЕЦ НОВЫХ ФУНКЦИЙ
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Конвертация ссылок из collection_urls2.txt в партнёрские")
    parser.add_argument("--force-login", action="store_true", help="Принудительный вход (игнорировать куки)")
    parser.add_argument("--input", "-i", help="Путь к файлу (по умолчанию configs/collection_urls2.txt или последний hotel_cities_*.txt)")
    parser.add_argument("--hotel-mode", action="store_true", help="Режим конвертации файлов hotel_cities_*.txt")
    args = parser.parse_args()

    # Простое предупреждение по безопасности (без .env, как ты просил)
    logger.warning("=== ВНИМАНИЕ БЕЗОПАСНОСТЬ ===")
    logger.warning("Скрипт будет логиниться в Travelpayouts используя данные из configs/travelpayoutsSetup.txt")
    logger.warning("Не давай доступ к этой папке другим людям и не коммить этот файл в git.")
    logger.warning("DEBUG_MODE сейчас False — куки в дебаг не сохраняemos.")

    try:
        if args.hotel_mode:
            # === НОВЫЙ РЕЖИМ: HOTEL CITIES ===
            if args.input:
                input_file = Path(args.input)
            else:
                # Автоматический поиск последнего необработанного файла hotel_cities_*.txt
                files = sorted(OUTPUT_DIR.glob("hotel_cities_*.txt"))
                files = [f for f in files if "PARTNERS" not in f.name]
                if not files:
                    logger.error("Не найдено файлов hotel_cities_*.txt для обработки")
                    return
                input_file = files[-1]
                logger.info(f"Автоматически выбран последний файл: {input_file}")

            init_selenium()
            driver = browser.build_driver(eager=True)
            try:
                login(driver, force_login=args.force_login)
                cache = {}
                output_file = run_hotel_city_converter_mode(input_file, driver, cache)
                logger.info(f"\n{'='*60}")
                logger.info(f"Готово! Результат сохранён: {output_file}")
                logger.info(f"{'='*60}")
            except Exception as e:
                logger.error(f"Ошибка в процессе конвертации отелей: {e}", exc_info=True)
                if DEBUG_MODE:
                    save_debug_pack(driver, "critical_hotel")
            finally:
                driver.quit()

        else:
            # === СТАРЫЙ РЕЖИМ: COLLECTION (НЕ ТРОНУТ) ===
            input_file = Path(args.input) if args.input else INPUT_FILE

            logger.info(f"Чтение файла: {input_file}")
            items = read_collection_urls_file(input_file)
            if not items:
                logger.error("Не найдено ни одной подборки для обработки")
                return

            logger.info(f"Найдено подборок: {len(items)}")
            init_selenium()
            driver = browser.build_driver(eager=True)
            logger.debug("Драйвер создан (через browser.build_driver)")

            try:
                login(driver, force_login=args.force_login)
                cache = {}
                results = convert_collection_urls(driver, items, cache)
                output_file = save_results(results, OUTPUT_DIR)
                logger.info(f"\n{'='*60}")
                logger.info(f"Готово! Успешно обработано: {len(results)}/{len(items)} подборок")
                logger.info(f"Результат сохранён: {output_file}")
                logger.info(f"{'='*60}")
            except Exception as e:
                logger.error(f"Ошибка в процессе конвертации: {e}", exc_info=True)
                if DEBUG_MODE:
                    save_debug_pack(driver, "critical")
            finally:
                driver.quit()

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        input("\nНажмите Enter для выхода...")

if __name__ == "__main__":
    main()
