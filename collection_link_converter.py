#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import pickle
import time
import random
import sys
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Optional, Tuple, List
import argparse

# === ИМПОРТЫ SELENIUM ===
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService

import browser
from browser import init_selenium, close_popups
from link_converter import login, get_partner_link, _create_fast_driver, save_debug_pack

# === КОНФИГУРАЦИЯ ===
INPUT_FILE = Path("configs/collection_urls2.txt")
OUTPUT_DIR = Path("postsCollections")
DEBUG_MODE = True
DEBUG_DIR = Path("debug_logs")
DEBUG_DIR.mkdir(exist_ok=True)

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

# === ТРАНСЛИТЕРАЦИЯ (копируем из post_generator.py) ===
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    ' ': '_', '-': '_', '’': '', "'": '',
}

CUSTOM_TRANSLIT = {
    'москва': 'moskva',
    'санкт-петербург': 'spb',
    'екатеринбург': 'ekb',
    'казань': 'kazan',
    'нижний новгород': 'n_novgorod',
    'египет': 'egipet',
    'турция': 'turkey',
    'таиланд': 'tailand',
    'шарм-эль-шейх': 'sharm',
    'хургада': 'hurgada',
    'оаэ': 'oae',
    'индия': 'indiya',
    'мальдивы': 'maldivy',
}

MONTHS_RU = {
    'янв': '01', 'фев': '02', 'мар': '03', 'апр': '04',
    'май': '05', 'июн': '06', 'июл': '07', 'авг': '08',
    'сен': '09', 'окт': '10', 'ноя': '11', 'дек': '12'
}

def transliterate(text: str) -> str:
    """Упрощённая транслитерация кириллицы в латиницу."""
    text = text.lower()
    for ru, en in CUSTOM_TRANSLIT.items():
        text = re.sub(r'\b' + ru + r'\b', en, text)
    result = []
    for ch in text:
        result.append(TRANSLIT_MAP.get(ch, ch if ch.isalnum() else '_'))
    cleaned = re.sub(r'_+', '_', ''.join(result)).strip('_')
    return cleaned

def parse_russian_date(date_str: str) -> str:
    """
    Преобразует "26 май" → "26_05_2026"
    Преобразует "20 - 30 июн" → "20_06_2026-30_06_2026"
    """
    def convert_single(d):
        d = d.strip()
        match = re.match(r'(\d{1,2})\s+([а-я]+)', d)
        if not match:
            return d.replace(' ', '_')
        day = int(match.group(1))
        month_name = match.group(2)[:3]
        month = MONTHS_RU.get(month_name)
        if not month:
            return d.replace(' ', '_')
        today = date.today()
        year = today.year
        if int(month) < today.month:
            year += 1
        return f"{day}_{month}_{year}"

    if ' - ' in date_str:
        start, end = date_str.split(' - ', 1)
        return f"{convert_single(start)}-{convert_single(end)}"
    else:
        return convert_single(date_str)

def parse_collection_line(line: str) -> Optional[Tuple[int, str, str, str, str, str, int]]:
    """
    Разбирает строку вида:
    "1. Москва, Турция, 20.06.2026-21.06.2026, ночей:10, взрослых:2 (Новая дата 20 - 30 июн | от 108446)"
    или
    "2. Санкт-Петербург, Турция, 18.06.2026, ночей:8-9, взрослых:2 (Новая дата 17 - 26 июн | от 113142)"
    или
    "10. Москва, Таиланд, 20.06.2026-21.06.2026, ночей:10, взрослых:2 (Новая дата 5 - 15 июн)"
    Возвращает (index, city, country, nights, adults, new_date_range, price)
    price = 0 если цена не указана
    """
    # Регулярное выражение с опциональной ценой
    match = re.match(
        r'^(\d+)\.\s+([^,]+),\s+([^,]+),\s+(?:\d+\.\d+\.\d+(?:-\d+\.\d+\.\d+)?),\s+ночей:(\d+(?:-\d+)?),\s+взрослых:(\d+)\s+\(Новая дата\s+(.+?)(?:\s+\|\s+от\s+(\d+))?\)$',
        line
    )
    if not match:
        logger.warning(f"Не удалось распарсить строку: {line}")
        return None

    index = int(match.group(1))
    city = match.group(2).strip()
    country = match.group(3).strip()
    nights = match.group(4).strip()
    adults = match.group(5).strip()
    new_date_range = match.group(6).strip()
    price = int(match.group(7)) if match.group(7) else 0  # 0 означает "ЦЕНА НЕ УКАЗАНА"

    return (index, city, country, nights, adults, new_date_range, price)

def format_output_line(index: int, city: str, country: str, nights: str, adults: str, new_date_range: str, price: int) -> str:
    """
    Форматирует строку в нужном формате:
    "1. Москва, Турция, ночей:10, взрослых:2, 20 - 30 июн, от 108446"
    или если цены нет:
    "10. Москва, Таиланд, ночей:10, взрослых:2, 5 - 15 июн, ЦЕНА НЕ УКАЗАНА"
    """
    if price > 0:
        return f"{index}. {city}, {country}, ночей:{nights}, взрослых:{adults}, {new_date_range}, от {price}"
    else:
        return f"{index}. {city}, {country}, ночей:{nights}, взрослых:{adults}, {new_date_range}, ЦЕНА НЕ УКАЗАНА"

def generate_sub_id_for_collection(city: str, country: str, new_date_range: str, price: int) -> str:
    """
    Генерирует sub_id в формате:
    spb_turkey_25_05_2026-3_06_2026_pr_89925
    Если цены нет, то без _pr_XXX
    """
    city_lat = transliterate(city)
    country_lat = transliterate(country)
    date_part = parse_russian_date(new_date_range)

    if price > 0:
        sub_id = f"{city_lat}_{country_lat}_{date_part}_pr_{price}"
    else:
        sub_id = f"{city_lat}_{country_lat}_{date_part}"

    # Очистка от лишних символов
    sub_id = re.sub(r'[^a-z0-9_]', '_', sub_id)
    sub_id = re.sub(r'_+', '_', sub_id).strip('_')
    return sub_id

def generate_sub_id_fallback(city: str, country: str, price: int) -> str:
    """Генерация sub_id на случай ошибки парсинга даты"""
    city_lat = transliterate(city)
    country_lat = transliterate(country)
    if price > 0:
        return f"{city_lat}_{country_lat}_date_unknown_pr_{price}"
    else:
        return f"{city_lat}_{country_lat}_date_unknown"

def read_collection_urls_file(file_path: Path) -> List[Tuple[int, str, str, str, str, str, int, str]]:
    """
    Читает файл collection_urls2.txt и возвращает список элементов.
    Возвращает: (index, city, country, nights, adults, new_date_range, price, original_url)
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Файл {file_path} не найден")

    items = []
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.rstrip() for line in f.readlines()]

    i = 0
    while i < len(lines):
        # Строка с описанием
        desc_line = lines[i]
        if not desc_line:
            i += 1
            continue

        parsed = parse_collection_line(desc_line)
        if not parsed:
            logger.warning(f"Пропускаем строку: {desc_line}")
            i += 1
            continue

        index, city, country, nights, adults, new_date_range, price = parsed

        # Следующая строка должна быть URL
        if i + 1 >= len(lines):
            logger.warning(f"Нет URL для индекса {index}")
            break

        url = lines[i + 1]
        if not url.startswith("http"):
            logger.warning(f"Строка не похожа на URL: {url}")
            i += 1
            continue

        items.append((index, city, country, nights, adults, new_date_range, price, url))
        i += 2  # Переходим к следующей паре

    return items

def convert_collection_urls(driver, items: List[Tuple], cache: Dict) -> List[Tuple[int, str, str]]:
    """
    Конвертирует URL в партнёрские ссылки.
    Возвращает список (index, formatted_line, partner_url or "ЦЕНА НЕ УКАЗАНА")
    """
    results = []

    for idx, (index, city, country, nights, adults, new_date_range, price, original_url) in enumerate(items, 1):
        logger.info(f"\n[{idx}/{len(items)}] Обработка подборки #{index}")
        logger.info(f"Город: {city}, Страна: {country}")
        logger.info(f"Новая дата: {new_date_range}, Цена: {price if price > 0 else 'НЕ УКАЗАНА'}")
        logger.info(f"URL: {original_url}")

        # Форматируем выходную строку
        formatted_line = format_output_line(index, city, country, nights, adults, new_date_range, price)
        logger.info(f"Форматированная строка: {formatted_line}")

        # Если нет цены - пропускаем генерацию партнёрской ссылки
        if price == 0:
            logger.warning(f"Цена не указана, пропускаем конвертацию ссылки")
            results.append((index, formatted_line, "ЦЕНА НЕ УКАЗАНА"))
        else:
            # Генерируем sub_id
            try:
                sub_id = generate_sub_id_for_collection(city, country, new_date_range, price)
            except Exception as e:
                logger.warning(f"Ошибка генерации sub_id: {e}, используем fallback")
                sub_id = generate_sub_id_fallback(city, country, price)

            logger.info(f"Сгенерирован sub_id: {sub_id}")

            # Получаем партнёрскую ссылку
            partner_url = get_partner_link(driver, original_url, sub_id, cache)

            if partner_url:
                results.append((index, formatted_line, partner_url))
                logger.info(f"✓ Получена партнёрская ссылка: {partner_url[:80]}...")
            else:
                logger.error(f"✗ Не удалось получить партнёрскую ссылку для {original_url}")
                # В случае ошибки оставляем оригинальную ссылку
                results.append((index, formatted_line, original_url))

        # Пауза между запросами
        if idx < len(items):
            time.sleep(random.uniform(1, 3))

    return results

def save_results(results: List[Tuple[int, str, str]], output_dir: Path) -> Path:
    """Сохраняет результаты в файл"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Формируем имя файла: collection_2026-05-27_15-30-45.txt
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_file = output_dir / f"collection_{timestamp}.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        for index, formatted_line, url in results:
            f.write(f"{formatted_line}\n")
            f.write(f"{url}\n\n")

    logger.info(f"Сохранено {len(results)} подборок в {output_file}")
    return output_file

def main():
    parser = argparse.ArgumentParser(description="Конвертация ссылок из collection_urls2.txt в партнёрские")
    parser.add_argument("--force-login", action="store_true", help="Принудительный вход (игнорировать куки)")
    parser.add_argument("--input", "-i", help="Путь к файлу collection_urls (по умолчанию configs/collection_urls2.txt)")
    args = parser.parse_args()

    input_file = Path(args.input) if args.input else INPUT_FILE

    try:
        # Читаем исходные подборки
        logger.info(f"Чтение файла: {input_file}")
        items = read_collection_urls_file(input_file)

        if not items:
            logger.error("Не найдено ни одной подборки для обработки")
            return

        logger.info(f"Найдено подборок: {len(items)}")

        # Инициализация Selenium
        init_selenium()

        # Создаём драйвер
        driver = _create_fast_driver()
        logger.debug("Драйвер создан")

        try:
            # Логинимся в Travelpayouts
            login(driver, force_login=args.force_login)

            # Конвертируем ссылки
            cache = {}
            results = convert_collection_urls(driver, items, cache)

            # Сохраняем результат
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
