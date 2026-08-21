#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import re
import time
import random
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import quote
import glob

import browser
from browser import init_selenium, build_driver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("top_hotels_parser")

# Путь к конфигу (папка configs)
CONFIG_PATH = Path("configs/config_global.json")
CACHE_DIR = Path("data")
CACHE_FILE = CACHE_DIR / "hotel_cache.json"

DEFAULT_CONFIG = {
    "top_hotel_cache_ttl_days": 7,
    "enable_reviews_parsing": True,
    "enable_yearly_ratings": False,
    "max_reviews": 5,
    "search_timeout": 15,
}

_CONFIG = None

def get_config():
    global _CONFIG
    if _CONFIG is None:
        if not CONFIG_PATH.exists():
            logger.warning(f"Файл {CONFIG_PATH} не найден, используются настройки по умолчанию")
            _CONFIG = DEFAULT_CONFIG.copy()
        else:
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    _CONFIG = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in _CONFIG:
                        _CONFIG[k] = v
            except Exception as e:
                logger.error(f"Ошибка загрузки конфига: {e}")
                _CONFIG = DEFAULT_CONFIG.copy()
    return _CONFIG

def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not CACHE_FILE.exists():
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)

def _load_cache() -> Dict[str, Any]:
    _ensure_cache_dir()
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.debug(f"Ошибка загрузки кэша: {e}")
        return {}

def _save_cache(cache: Dict[str, Any]):
    _ensure_cache_dir()
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def normalize(s: str) -> str:
    s = s.strip().lower()
    return re.sub(r'\s+', ' ', s)

def _cache_key(hotel_name: str, arrival_country: str) -> str:
    return f"{normalize(hotel_name)}|{normalize(arrival_country)}"

def _is_cache_fresh(entry: Dict[str, Any], ttl_days: int) -> bool:
    last = entry.get("last_updated")
    if not last:
        return False
    try:
        last_date = datetime.strptime(last, "%Y-%m-%d")
        return datetime.now() - last_date < timedelta(days=ttl_days)
    except Exception as e:
        logger.debug(f"Ошибка проверки свежести кэша: {e}")
        return False

def _search_hotel_on_tophotels(driver, hotel_name: str, arrival_country: str, timeout: int) -> Optional[str]:
    query = f"{hotel_name} {arrival_country}"
    search_url = f"https://tophotels.ru/search/?q={quote(query)}"
    logger.info(f"Поиск: {search_url}")
    driver.get(search_url)
    try:
        browser.WebDriverWait(driver, timeout).until(browser.EC.presence_of_element_located((browser.By.TAG_NAME, "body")))
    except browser.TimeoutException:
        return None
    browser.close_popups(driver)

    try:
        links = browser.WebDriverWait(driver, timeout).until(
            browser.EC.presence_of_all_elements_located((browser.By.XPATH, "//a[contains(@href, '/hotel/')]"))
        )
    except browser.TimeoutException:
        links = driver.find_elements(browser.By.XPATH, "//a[contains(@href, '/hotel/')]")
        if not links:
            return None

    max_check = 3
    for link in links[:max_check]:
        href = link.get_attribute("href")
        link_text = (link.text or "").strip().lower()
        if not link_text:
            parent = link.find_element(browser.By.XPATH, "..")
            headings = parent.find_elements(browser.By.XPATH, ".//h3|.//h4|.//b")
            if headings:
                link_text = headings[0].text.strip().lower()
        hotel_norm = normalize(hotel_name)
        if link_text and (hotel_norm in link_text or link_text in hotel_norm):
            logger.info(f"Найден отель: {href}")
            return href
    if links:
        first_url = links[0].get_attribute("href")
        logger.warning(f"Точное совпадение не найдено, берём первое: {first_url}")
        return first_url
    return None

def _parse_rating_section(driver, timeout: int):
    rating_value = None
    yearly_ratings = []
    reviews = []
    config = get_config()

    try:
        rating_section = browser.WebDriverWait(driver, timeout).until(
            browser.EC.presence_of_element_located((browser.By.XPATH, "//section[contains(@class, 'rating')]"))
        )
        stat_div = rating_section.find_element(browser.By.XPATH, ".//div[contains(@class, 'rating__statistic')]")
        first_link = stat_div.find_element(browser.By.XPATH, ".//a[contains(@class, 'rating__bb')]")
        b_elem = first_link.find_element(browser.By.TAG_NAME, "b")
        spans = b_elem.find_elements(browser.By.TAG_NAME, "span")
        if spans:
            raw = spans[0].text.strip().replace(',', '.')
            rating_value = float(raw)
            logger.info(f"Общий рейтинг: {rating_value}")
    except Exception as e:
        logger.warning(f"Не удалось извлечь общий рейтинг: {e}")

    if config["enable_yearly_ratings"]:
        try:
            rating_links = stat_div.find_elements(browser.By.XPATH, ".//a[contains(@class, 'rating__bb')]")
            for link in rating_links[1:]:
                href = link.get_attribute("href")
                match = re.search(r'yeartime=(\d+)', href)
                if not match:
                    continue
                year = match.group(1)
                b_elem = link.find_element(browser.By.TAG_NAME, "b")
                spans = b_elem.find_elements(browser.By.TAG_NAME, "span")
                if spans:
                    year_rating = float(spans[0].text.strip().replace(',', '.'))
                    change = spans[1].text.strip() if len(spans) > 1 else None
                    yearly_ratings.append({"year": year, "rating": year_rating, "change": change})
            logger.info(f"Найдено рейтингов по годам: {len(yearly_ratings)}")
        except Exception as e:
            logger.warning(f"Ошибка при парсинге годовых рейтингов: {e}")

    if config["enable_reviews_parsing"]:
        try:
            reviews_table = driver.find_element(browser.By.XPATH, "//table[contains(@class, 'lsfw-tbl') and contains(@class, 'reviews-tbl')]")
            rows = reviews_table.find_elements(browser.By.XPATH, ".//tbody/tr")
            max_rev = config["max_reviews"]
            for idx, row in enumerate(rows):
                if idx >= max_rev:
                    break
                try:
                    rating_elem = row.find_element(browser.By.XPATH, ".//b[contains(@class, 'fz23')]")
                    rev_rating = float(rating_elem.text.strip().replace(',', '.'))
                    title_elem = row.find_element(browser.By.XPATH, ".//b[contains(@class, 'lsfw-tbl__cut')]")
                    title = title_elem.text.strip()
                    text_elem = row.find_element(browser.By.XPATH, ".//p[contains(@class, 'mt5')]")
                    review_text = text_elem.text.strip()[:300]
                    last_cell = row.find_element(browser.By.XPATH, "td[last()]")
                    author_link = last_cell.find_element(browser.By.XPATH, ".//a[contains(@class, 'bth__ava-40')]")
                    author = author_link.get_attribute("title") or author_link.text.strip()
                    if not author:
                        hint_span = author_link.find_element(browser.By.XPATH, ".//span[contains(@class, 'hint')]")
                        author = hint_span.text.strip()
                    date_div = row.find_element(browser.By.XPATH, ".//div[contains(@class, 'lsfw-tbl__inline') and contains(@class, 'fz14')]")
                    date_str = date_div.text.strip()
                    recommendation = None
                    if row.find_elements(browser.By.XPATH, ".//i[contains(@class, 'fa-thumbs-up')]"):
                        recommendation = "recommend"
                    elif row.find_elements(browser.By.XPATH, ".//i[contains(@class, 'fa-thumbs-down')]"):
                        recommendation = "not_recommend"
                    elif row.find_elements(browser.By.XPATH, ".//i[contains(@class, 'fa-yin-yang')]"):
                        recommendation = "neutral"
                    reviews.append({
                        "rating": rev_rating,
                        "title": title,
                        "text": review_text,
                        "author": author,
                        "date": date_str,
                        "recommendation": recommendation
                    })
                except Exception:
                    continue
            logger.info(f"Найдено отзывов: {len(reviews)}")
        except Exception as e:
            logger.warning(f"Блок отзывов не найден: {e}")

    return rating_value, yearly_ratings, reviews

def build_stars_map_from_tours(tours: List[Dict]) -> Dict[str, int]:
    stars_map = {}
    for tour in tours:
        hotel_name = tour.get("hotel_name", "")
        arrival_country = tour.get("arrival_country", "")
        stars = tour.get("stars", 0)
        if not hotel_name or not arrival_country or not isinstance(stars, int):
            continue
        key = f"{normalize(hotel_name)}|{normalize(arrival_country)}"
        current = stars_map.get(key, 0)
        if stars > current:
            stars_map[key] = stars
    return stars_map

def expand_input_mask(input_arg: str) -> List[Path]:
    if '*' in str(input_arg) or '?' in str(input_arg):
        files = glob.glob(input_arg)
        if not files:
            raise FileNotFoundError(f"По маске {input_arg} не найдено файлов")
        return [Path(f) for f in files]
    else:
        p = Path(input_arg)
        if not p.exists():
            raise FileNotFoundError(f"Файл {p} не найден")
        return [p]

def update_cache_from_json(input_path: Path, force_refresh: bool = False) -> Dict[str, int]:
    if not input_path.exists():
        raise FileNotFoundError(f"Файл {input_path} не найден")

    with open(input_path, "r", encoding="utf-8") as f:
        offers = json.load(f)

    stars_map = build_stars_map_from_tours(offers)
    logger.info(f"Собрано звёзд для {len(stars_map)} уникальных отелей из {input_path.name}")

    config = get_config()
    ttl = config["top_hotel_cache_ttl_days"]
    timeout = config["search_timeout"]

    cache = _load_cache()
    stats = {"total": len(offers), "updated": 0, "errors": 0, "stars_added": 0, "stars_updated": 0}

    init_selenium()
    driver = build_driver()

    try:
        for idx, offer in enumerate(offers, 1):
            hotel_name = offer.get("hotel_name", "")
            arrival_country = offer.get("arrival_country", "")
            onlinetours_url = offer.get("hotel_url", "")

            if not hotel_name or not arrival_country:
                logger.warning(f"[{idx}/{stats['total']}] Пропуск: отсутствует название отеля или страна")
                stats["errors"] += 1
                continue

            key = _cache_key(hotel_name, arrival_country)
            logger.info(f"\n[{idx}/{stats['total']}] {hotel_name} ({arrival_country})")

            need_refresh = force_refresh or (key not in cache) or not _is_cache_fresh(cache[key], ttl)
            processed = False

            # Случай 1: кэш свежий, но нет поля stars (старая запись)
            if not need_refresh and key in cache and "stars" not in cache[key]:
                stars_value = stars_map.get(key, 0)
                if stars_value:
                    cache[key]["stars"] = stars_value
                    _save_cache(cache)
                    stats["stars_added"] += 1
                    logger.info(f"Добавлены звёзды для {hotel_name}: {stars_value}")
                processed = True

            # Случай 2: нужно обновить (парсинг TopHotels)
            elif need_refresh:
                logger.info("Парсинг TopHotels...")
                result = {
                    "onlinetours_url": onlinetours_url,
                    "found": False,
                    "top_hotel_rating": None,
                    "hotel_url_on_top_hotels": None,
                    "yearly_ratings": [],
                    "reviews": [],
                    "stars": stars_map.get(key, 0),
                    "last_updated": datetime.now().strftime("%Y-%m-%d"),
                }

                try:
                    hotel_url = _search_hotel_on_tophotels(driver, hotel_name, arrival_country, timeout)
                    if hotel_url:
                        result["found"] = True
                        result["hotel_url_on_top_hotels"] = hotel_url
                        driver.get(hotel_url)
                        browser.WebDriverWait(driver, timeout).until(browser.EC.presence_of_element_located((browser.By.TAG_NAME, "body")))
                        browser.close_popups(driver)
                        rating, yearly, reviews_data = _parse_rating_section(driver, timeout)
                        result["top_hotel_rating"] = rating
                        result["yearly_ratings"] = yearly
                        result["reviews"] = reviews_data
                        stats["updated"] += 1
                    else:
                        logger.warning("Отель не найден на TopHotels")
                        stats["updated"] += 1
                except Exception as e:
                    logger.error(f"Ошибка: {e}", exc_info=True)
                    stats["errors"] += 1

                cache[key] = result
                _save_cache(cache)
                if result["stars"]:
                    stats["stars_updated"] += 1
                processed = True

            # Случай 3: всё актуально и звёзды есть – просто пропускаем (без паузы)
            else:
                continue

            # Пауза только если была реальная обработка
            if processed and idx < stats["total"]:
                time.sleep(random.uniform(1, 3))

    finally:
        driver.quit()

    logger.info(f"\nСтатистика для {input_path.name}: всего {stats['total']}, обновлено/добавлено записей: {stats['updated']}, ошибок: {stats['errors']}, добавлено звёзд в старые записи: {stats['stars_added']}, обновлено звёзд при парсинге: {stats['stars_updated']}")
    return stats

def main():
    parser = argparse.ArgumentParser(description="Обновление кэша отелей данными с tophotels.ru")
    parser.add_argument("--input", "-i", required=True, help="Путь к JSON-файлу с турами (можно использовать маску, например results/*.json)")
    parser.add_argument("--force-refresh", action="store_true", help="Игнорировать TTL и перепарсить все отели")
    args = parser.parse_args()

    try:
        files = expand_input_mask(args.input)
    except FileNotFoundError as e:
        logger.error(e)
        return

    for file_path in files:
        logger.info(f"\n{'='*60}\nОбработка файла: {file_path}\n{'='*60}")
        update_cache_from_json(file_path, force_refresh=args.force_refresh)

if __name__ == "__main__":
    main()
