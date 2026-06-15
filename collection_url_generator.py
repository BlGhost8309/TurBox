#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import logging
import argparse
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import browser
from browser import init_selenium, build_driver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("collection_url_generator")

CONFIG_FILE = Path("configs/url_generation_config.txt")
OUTPUT_FILE = Path("configs/collection_urls2.txt")
DEBUG_DIR = Path("debug_logs")
BASE_URL = "https://www.onlinetours.ru/"

DEFAULT_CONFIG = {
    "search_min_price_data": False,
}


def smart_split(line: str, delimiter: str = '|') -> List[str]:
    """Разбивает строку по разделителю, игнорируя разделители внутри скобок ()."""
    result = []
    current = []
    depth = 0
    for char in line:
        if char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif char == delimiter and depth == 0:
            result.append(''.join(current))
            current = []
        else:
            current.append(char)
    if current:
        result.append(''.join(current))
    return result

def split_filters_aware(filter_str: str) -> List[str]:
    """Разбивает строку фильтров по |, игнорируя | внутри скобок ()."""
    result = []
    current = []
    depth = 0
    for char in filter_str:
        if char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif char == '|' and depth == 0:
            result.append(''.join(current))
            current = []
        else:
            current.append(char)
    if current:
        result.append(''.join(current))
    return result


def save_debug_info(driver, step_name: str):
    """Сохраняет дебаг при ошибках. 
    ВАЖНО ДЛЯ БЕЗОПАСНОСТИ: не сохраняем куки и ограничиваем объём HTML.
    """
    DEBUG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pack_dir = DEBUG_DIR / f"debug_{step_name}_{timestamp}"
    pack_dir.mkdir(exist_ok=True)
    try:
        driver.save_screenshot(pack_dir / "screenshot.png")
    except Exception as e:
        logger.debug(f"Не удалось сохранить скрин: {e}")
    try:
        # Ограничиваем дамп HTML (не весь огромный page_source)
        html_snippet = driver.page_source[:150000]
        with open(pack_dir / "source.html", "w", encoding="utf-8") as f:
            f.write(html_snippet)
    except Exception as e:
        logger.debug(f"Не удалось сохранить source: {e}")
    with open(pack_dir / "error.txt", "w", encoding="utf-8") as f:
        f.write(f"Step: {step_name}\n")
        f.write(traceback.format_exc())
    logger.error(f"Сохранён отладочный пакет: {pack_dir} (куки НЕ сохраняются)")


def read_sections(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Не найден {path}")

    sections: Dict[str, List[str]] = {}
    current = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper() in ("ПАРАМЕТРЫ", "ЗАПРОСЫ"):
            current = line.upper()
            sections[current] = []
            continue
        if current:
            sections[current].append(line)
    return sections


def parse_config_parameters(sections: Dict[str, List[str]]) -> Dict[str, any]:
    params = sections.get("ПАРАМЕТРЫ", [])
    config = DEFAULT_CONFIG.copy()
    for line in params:
        if line.startswith("searchMinPriceData="):
            val = line.split("=", 1)[1].strip().lower()
            config["search_min_price_data"] = val == "true"
    return config


def parse_extra_filters(filter_str: str) -> Dict[str, any]:
    """
    Разбирает дополнительные фильтры из строки запроса.
    Формат: цена:50000-150000|рейтинг:5|питание:(Всё включено|Ультра всё включено)|сортировка:цена
    """
    result = {
        "price_min": None,
        "price_max": None,
        "rating": None,
        "meal_ids": [],
        "sort": "popularity"
    }

    if not filter_str:
        return result

    meal_map = {
        "Всё включено": "739",
        "Ультра всё включено": "740",
        "3-разовое": "3",
        "2-разовое": "731",
        "Завтраки": "730",
    }

    parts = split_filters_aware(filter_str)
    for part in parts:
        part = part.strip()
        if part.startswith("цена:"):
            price_part = part[5:].strip()
            if '-' in price_part:
                min_str, max_str = price_part.split('-')
                if min_str:
                    result["price_min"] = int(min_str)
                if max_str:
                    result["price_max"] = int(max_str)
            else:
                result["price_min"] = int(price_part)
        elif part.startswith("рейтинг:"):
            rating_val = int(part[8:].strip())
            if 5 <= rating_val <= 9:
                result["rating"] = rating_val
        elif part.startswith("сортировка:"):
            sort_val = part[11:].strip().lower()
            if sort_val == "цена":
                result["sort"] = "price"
            elif sort_val == "популярность":
                result["sort"] = "popularity"
        elif part.startswith("питание:"):
            meal_part = part[8:].strip()
            if meal_part.startswith('(') and meal_part.endswith(')'):
                meal_part = meal_part[1:-1]
                for meal in meal_part.split('|'):
                    meal = meal.strip()
                    if meal in meal_map:
                        result["meal_ids"].append(meal_map[meal])

    return result


def parse_config_links(sections: Dict[str, List[str]]) -> List[Tuple]:
    links = sections.get("ЗАПРОСЫ", [])
    requests = []
    for line in links:
        line = line.strip()
        if not line:
            continue

        extra_filters = {}
        parts = smart_split(line)
        filter_indices = []
        for i, part in enumerate(parts):
            if part.startswith('цена:') or part.startswith('рейтинг:') or part.startswith('сортировка:') or part.startswith('питание:'):
                filter_indices.append(i)

        if filter_indices:
            filter_parts = parts[filter_indices[0]:]
            filter_str = '|'.join(filter_parts)
            extra_filters = parse_extra_filters(filter_str)
            parts = parts[:filter_indices[0]]

        if len(parts) < 5:
            logger.warning(f"Неверный формат строки, пропускаем: {line}")
            continue

        city = parts[0]
        country = parts[1]
        date_range_str = parts[2]
        nights_part = parts[3]
        adults_part = parts[4]

        if '-' in date_range_str:
            start_str, end_str = date_range_str.split('-')
            start_date = datetime.strptime(start_str.strip(), "%d.%m.%Y")
            end_date = datetime.strptime(end_str.strip(), "%d.%m.%Y")
        else:
            start_date = datetime.strptime(date_range_str.strip(), "%d.%m.%Y")
            end_date = start_date

        nights_match = re.search(r'ночей:(\d+)(?:-(\d+))?', nights_part, re.IGNORECASE)
        if not nights_match:
            logger.warning(f"Не удалось извлечь ночи из: {line}")
            continue
        nights_min = int(nights_match.group(1))
        nights_max = int(nights_match.group(2)) if nights_match.group(2) else nights_min

        adults_match = re.search(r'взрослых:(\d+)', adults_part, re.IGNORECASE)
        if not adults_match:
            logger.warning(f"Не удалось извлечь взрослых из: {line}")
            continue
        adults = int(adults_match.group(1))

        requests.append((city, country, start_date, end_date, nights_min, nights_max, adults, extra_filters))

    return requests


def get_last_index() -> int:
    if not OUTPUT_FILE.exists():
        return 0
    content = OUTPUT_FILE.read_text(encoding="utf-8")
    matches = re.findall(r'^(\d+)\.', content, re.MULTILINE)
    if not matches:
        return 0
    return max(int(m) for m in matches)


def append_result(index: int, city: str, country: str, start_date: datetime, end_date: datetime, nights_min: int, nights_max: int, adults: int, url: str, extra_info: str = None):
    if start_date == end_date:
        date_str = start_date.strftime("%d.%m.%Y")
    else:
        date_str = f"{start_date.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')}"
    if nights_min == nights_max:
        nights_str = f"{nights_min}"
    else:
        nights_str = f"{nights_min}-{nights_max}"

    main_part = f"{index}. {city}, {country}, {date_str}, ночей:{nights_str}, взрослых:{adults}"
    if extra_info:
        main_part += f" ({extra_info})"

    block = f"{main_part}\n{url}\n\n"
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(block)


def clear_input_field(driver, element):
    driver.execute_script("arguments[0].value = '';", element)
    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
    time.sleep(0.3)


def set_city_country(driver, placeholder: str, value: str) -> bool:
    logger.info(f"Выбор '{value}' в поле '{placeholder}'")
    try:
        input_field = browser.WebDriverWait(driver, 15).until(
            browser.EC.presence_of_element_located((browser.By.XPATH, f"//input[@placeholder='{placeholder}']"))
        )
        driver.execute_script("arguments[0].click();", input_field)
        time.sleep(0.3)

        input_field.send_keys(browser.Keys.CONTROL + "a")
        input_field.send_keys(browser.Keys.DELETE)
        # time.sleep(0.3)  # можно вернуть при проблемах

        input_field.send_keys(value)
        # time.sleep(0.5)  # даём время на автокомплит; лучше было бы WebDriverWait на дропдаун

        dropdown = browser.WebDriverWait(driver, 5).until(
            browser.EC.presence_of_element_located((browser.By.XPATH, "//div[contains(@class, 'absolute') and contains(@class, 'z-50')]"))
        )
        try:
            target = dropdown.find_element(browser.By.XPATH, f".//div[contains(@class, 'cursor-pointer') and normalize-space()='{value}']")
        except Exception:
            target = dropdown.find_element(browser.By.XPATH, f".//div[contains(@class, 'cursor-pointer')]//*[normalize-space()='{value}']/..")
        target.click()
        # time.sleep(0.5)
        return True
    except Exception as e:
        logger.error(f"Ошибка выбора '{value}' в поле '{placeholder}': {e}")
        save_debug_info(driver, f"select_{placeholder}")
        return False


def click_date(driver, target_date: datetime) -> bool:
    months = driver.find_elements(browser.By.XPATH, "//div[starts-with(@id, 'month')]")
    target_year = target_date.year
    target_month = target_date.month
    target_day = target_date.day
    month_names_ru = {
        'Январь': 1, 'Февраль': 2, 'Март': 3, 'Апрель': 4, 'Май': 5, 'Июнь': 6,
        'Июль': 7, 'Август': 8, 'Сентябрь': 9, 'Октябрь': 10, 'Ноябрь': 11, 'Декабрь': 12
    }

    for month_elem in months:
        header = month_elem.find_elements(browser.By.XPATH, ".//div[contains(@class, 'pb-2') and contains(@class, 'pt-3')]")
        if not header:
            continue
        header_text = header[0].text.strip()
        parts = header_text.split()
        month_name = parts[0]
        year = None
        if len(parts) > 1 and parts[1].isdigit():
            year = int(parts[1])
        month_num = month_names_ru.get(month_name)
        if month_num is None:
            continue
        if year is None:
            year = datetime.now().year
        if (month_num, year) == (target_month, target_year):
            month_id = month_elem.get_attribute('id')
            month_index = month_id.replace('month', '')
            day_id = f"day{month_index}_{target_day}"
            day_elem = month_elem.find_elements(browser.By.ID, day_id)
            if not day_elem:
                logger.warning(f"Не найден день {target_day} в месяце {month_name}")
                return False
            day_elem[0].click()
            return True
    return False


def select_date_range(driver, start_date: datetime, end_date: datetime) -> bool:
    logger.info(f"Выбор дат: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
    try:
        date_label = browser.WebDriverWait(driver, 15).until(
            browser.EC.element_to_be_clickable((browser.By.XPATH, "//label[text()='Дата вылета']/.."))
        )
        date_label.click()
        logger.info("Календарь открыт")
        time.sleep(1)
    except Exception as e:
        logger.error(f"Не удалось открыть календарь: {e}")
        save_debug_info(driver, "open_calendar")
        return False

    if not click_date(driver, start_date):
        logger.error(f"Не удалось выбрать первую дату")
        return False
    time.sleep(0.5)

    if start_date != end_date:
        if not click_date(driver, end_date):
            logger.error(f"Не удалось выбрать вторую дату")
            return False
    else:
        if not click_date(driver, start_date):
            logger.error("Не удалось выбрать повторную дату")
            return False

    logger.info("Диапазон дат выбран")
    time.sleep(1)
    return True


def set_nights_range(driver, nights_min: int, nights_max: int) -> bool:
    logger.info(f"Выбор ночей: {nights_min} - {nights_max}")
    try:
        nights_label = browser.WebDriverWait(driver, 15).until(
            browser.EC.element_to_be_clickable((browser.By.XPATH, "//label[text()='На сколько']/.."))
        )
        nights_label.click()
        time.sleep(1)
    except Exception as e:
        logger.error(f"Не удалось открыть панель ночей: {e}")
        save_debug_info(driver, "open_nights")
        return False

    def click_night(value: int):
        btn = browser.WebDriverWait(driver, 10).until(
            browser.EC.presence_of_element_located((browser.By.XPATH, f"//div[contains(@class, 'absolute')]//div[text()='{value}']"))
        )
        # Прокручиваем элемент в центр видимости
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        time.sleep(0.3)
        # Ждём, пока элемент станет кликабельным и не будет перекрыт
        browser.WebDriverWait(driver, 5).until(
            browser.EC.element_to_be_clickable(btn)
        )
        # Пытаемся кликнуть через JS, если обычный клик не сработает
        try:
            btn.click()
        except browser.exceptions.ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", btn)
        time.sleep(0.5)

    click_night(nights_min)
    if nights_max != nights_min:
        click_night(nights_max)
    else:
        click_night(nights_min)

    time.sleep(1)
    return True


def set_adults(driver, adults: int) -> bool:
    if adults == 2:
        logger.info("Взрослых 2 (по умолчанию), пропускаем")
        return True
    logger.warning("Изменение взрослых не поддерживается")
    return True


def select_cheapest_date(driver, timeout=30):
    logger.info("Поиск блока с датами для выбора самой дешёвой даты...")
    try:
        buttons = browser.WebDriverWait(driver, timeout).until(
            browser.EC.presence_of_all_elements_located((browser.By.XPATH, "//button[contains(@style, 'calc(')]"))
        )
        logger.info(f"Найдено {len(buttons)} кнопок с процентами")
    except browser.TimeoutException:
        raise Exception("Не найдено кнопок с процентами")

    candidates = []
    for btn in buttons:
        style = btn.get_attribute("style") or ""
        match = re.search(r'calc\(([\d\.]+)%', style)
        if match:
            percent = float(match.group(1))
            candidates.append((percent, btn))

    if not candidates:
        raise Exception("Не найдено кнопок с валидными процентами")

    min_percent, best_button = min(candidates, key=lambda x: x[0])
    logger.info(f"Выбрана кнопка с минимальным процентом {min_percent} (самая дешёвая дата)")

    browser._safe_click(driver, best_button)
    logger.info("Ожидание перезагрузки страницы после выбора даты...")
    time.sleep(4)
    browser.WebDriverWait(driver, timeout).until(
        browser.EC.presence_of_element_located((browser.By.TAG_NAME, "body"))
    )
    return True


def build_filtered_url(base_url: str, filters: Dict[str, any]) -> str:
    parsed = urlparse(base_url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))

    if filters.get("sort"):
        query_params["sort"] = filters["sort"]
    if filters.get("price_min") is not None:
        query_params["price_from"] = str(filters["price_min"])
    if filters.get("price_max") is not None:
        query_params["price_to"] = str(filters["price_max"])
    if filters.get("rating"):
        query_params["rating"] = str(filters["rating"])

    # Удаляем старые meal_type[]
    for k in list(query_params.keys()):
        if k.startswith("meal_type"):
            del query_params[k]

    # Добавляем новые meal_type[] как список
    meal_ids = filters.get("meal_ids", [])
    if meal_ids:
        query_params["meal_type[]"] = meal_ids

    # Собираем параметры вручную
    new_query_parts = []
    for key, value in query_params.items():
        if isinstance(value, list):
            for v in value:
                new_query_parts.append(f"{key}={v}")
        else:
            new_query_parts.append(f"{key}={value}")
    new_query_str = "&".join(new_query_parts)

    return urlunparse(parsed._replace(query=new_query_str))


def extract_min_price(driver) -> Optional[int]:
    """Извлекает минимальную цену со страницы результатов (из первого тура)."""
    try:
        price_elem = driver.find_element(browser.By.XPATH, "//span[contains(@class, 'text-ds-mobile-h4') and contains(@class, 'text-ds-primary')]")
        price_text = price_elem.text.strip()
        # Извлекаем число из "от 98 662 ₽" или "98 662 ₽"
        match = re.search(r'от\s+([\d\s]+)₽', price_text)
        if not match:
            match = re.search(r'([\d\s]+)₽', price_text)
        if match:
            price_str = match.group(1).replace(' ', '').replace('&nbsp;', '')
            return int(price_str)
        return None
    except Exception as e:
        logger.warning(f"Не удалось извлечь минимальную цену: {e}")
        return None


def extract_final_date(driver, original_start_date: datetime, original_end_date: datetime) -> Optional[str]:
    """Извлекает итоговую дату из поля 'Дата вылета', если она изменилась."""
    try:
        # Берём дату из div с классами text-ds-body-md и text-ds-primary
        date_elem = driver.find_element(browser.By.XPATH, "//div[contains(@class, 'text-ds-body-md') and contains(@class, 'text-ds-primary')]")
        date_text = date_elem.text.strip()
        if not date_text:
            return None

        # Проверяем, изменилась ли дата относительно исходной
        original_str = original_start_date.strftime("%d.%m.%Y")
        original_range_str = f"{original_start_date.strftime('%d.%m.%Y')}-{original_end_date.strftime('%d.%m.%Y')}"
        if date_text != original_str and date_text != original_range_str:
            return date_text
        return None
    except Exception as e:
        logger.warning(f"Не удалось извлечь дату: {e}")
        return None


def fill_form_and_get_url(city: str, country: str, start_date: datetime, end_date: datetime, nights_min: int, nights_max: int, adults: int, search_min_price_data: bool, extra_filters: Dict) -> Optional[Dict]:
    init_selenium()
    # Централизованный драйвер с eager loading (быстрее + меньше ждём рекламу)
    driver = build_driver(eager=True)
    try:
        driver.get(BASE_URL)
        # Даём странице время на полную отрисовку
        time.sleep(2)
        logger.info("Главная страница загружена")

        if not set_city_country(driver, "Город вылета", city):
            return None
        if not set_city_country(driver, "Страна, курорт, отель", country):
            return None
        if not select_date_range(driver, start_date, end_date):
            return None
        if not set_nights_range(driver, nights_min, nights_max):
            return None
        if not set_adults(driver, adults):
            return None

        try:
            search_btn = browser.WebDriverWait(driver, 10).until(
                browser.EC.element_to_be_clickable((browser.By.XPATH, "//button[contains(@class, 'bg-orange-500') and contains(., 'Найти тур')]"))
            )
        except:
            search_btn = browser.WebDriverWait(driver, 10).until(
                browser.EC.element_to_be_clickable((browser.By.XPATH, "//button[contains(text(), 'Найти тур')]"))
            )
        driver.execute_script("arguments[0].scrollIntoView(true);", search_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", search_btn)
        logger.info("Кнопка 'Найти тур' нажата")

        browser.WebDriverWait(driver, 20).until(lambda d: "/tours/" in d.current_url)
        url = driver.current_url
        logger.info(f"Получен URL после поиска: {url}")

        # === ПРОВЕРКА НА ОТСУТСТВИЕ ТУРОВ ===
        try:
            # Ждём до 5 секунд ПОЛНОЙ видимости элемента (не просто presence)
            no_results = browser.WebDriverWait(driver, 10).until(
                browser.EC.visibility_of_element_located((
                    browser.By.XPATH,
                    "//h3[normalize-space()='Таких предложений у туроператоров не нашлось']"
                ))
            )
            if no_results:
                logger.warning("Обнаружено сообщение: 'Таких предложений у туроператоров не нашлось'")
                return {"url": "NO_RESULTS", "extra_info": None}
        except browser.TimeoutException:
            pass  # Не появилось за 5 сек — значит, есть результаты, идём дальше

        if search_min_price_data:
            logger.info("Выбор самой дешёвой даты (searchMinPriceData=true)...")
            select_cheapest_date(driver)
            url = driver.current_url
            logger.info(f"Новый URL после выбора дешёвой даты: {url}")

        # Применение фильтров через URL
        if extra_filters and (extra_filters.get("price_min") or extra_filters.get("price_max") or extra_filters.get("rating") or extra_filters.get("meal_ids") or extra_filters.get("sort")):
            logger.info(f"Применение фильтров через параметры URL...")
            new_url = build_filtered_url(url, extra_filters)
            if new_url != url:
                logger.info(f"Новый URL с фильтрами: {new_url}")
                driver.get(new_url)
                time.sleep(2)
                browser.WebDriverWait(driver, 20).until(lambda d: "/tours/" in d.current_url)
                url = driver.current_url
                logger.info(f"Финальный URL после фильтров: {url}")

        # === ПРОВЕРКА НА ОТСУТСТВИЕ ТУРОВ ===
        try:
            # Ждём до 5 секунд ПОЛНОЙ видимости элемента (не просто presence)
            no_results = browser.WebDriverWait(driver, 10).until(
                browser.EC.visibility_of_element_located((
                    browser.By.XPATH,
                    "//h3[normalize-space()='Таких предложений у туроператоров не нашлось']"
                ))
            )
            if no_results:
                logger.warning("Обнаружено сообщение: 'Таких предложений у туроператоров не нашлось'")
                return {"url": "NO_RESULTS", "extra_info": None}
        except browser.TimeoutException:
            pass  # Не появилось за 5 сек — значит, есть результаты, идём дальше

        # Извлечение минимальной цены (если сортировка по цене)
        min_price = None
        if extra_filters.get("sort") == "price":
            min_price = extract_min_price(driver)
            if min_price:
                logger.info(f"Минимальная цена: {min_price}")

        # Извлечение итоговой даты (если она изменилась)
        final_date = extract_final_date(driver, start_date, end_date)
        if final_date:
            logger.info(f"Итоговая дата изменилась: {final_date}")

        # Формируем дополнительную информацию
        extra_parts = []
        if final_date:
            extra_parts.append(f"Новая дата {final_date}")
        if min_price:
            extra_parts.append(f"от {min_price}")

        # Добавляем информацию о питании
        meal_ids = extra_filters.get("meal_ids", [])
        if meal_ids:
            if "739" in meal_ids or "740" in meal_ids:
                extra_parts.append("всё включено")
            if "730" in meal_ids:
                extra_parts.append("завтраки")

        extra_info = " | ".join(extra_parts) if extra_parts else None
        return {"url": url, "extra_info": extra_info}

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        save_debug_info(driver, "general")
        return None
    finally:
        driver.quit()
        logger.info("Драйвер закрыт")


def main():
    try:
        sections = read_sections(CONFIG_FILE)
        config = parse_config_parameters(sections)
        requests = parse_config_links(sections)
    except Exception as e:
        logger.error(f"Ошибка чтения конфигурации: {e}")
        input("Нажмите Enter для выхода...")
        return

    if not requests:
        logger.warning("Нет запросов в файле")
        input("Нажмите Enter для выхода...")
        return

    last_index = get_last_index()
    current_index = last_index + 1

    for city, country, start_date, end_date, nights_min, nights_max, adults, extra_filters in requests:
        if start_date == end_date:
            date_desc = start_date.strftime('%d.%m.%Y')
        else:
            date_desc = f"{start_date.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')}"
        if nights_min == nights_max:
            nights_desc = f"{nights_min}"
        else:
            nights_desc = f"{nights_min}-{nights_max}"

        logger.info(f"\n{'='*60}\n{city} -> {country}, даты {date_desc}, ночей {nights_desc}, взрослых {adults}, фильтры: {extra_filters}\n{'='*60}")

        result = fill_form_and_get_url(city, country, start_date, end_date, nights_min, nights_max, adults, config["search_min_price_data"], extra_filters)
        if result:
            append_result(current_index, city, country, start_date, end_date, nights_min, nights_max, adults, result["url"], result["extra_info"])
            logger.info(f"Сохранён #{current_index}")
            current_index += 1
        else:
            logger.error(f"Не удалось получить URL для запроса")
            input("Нажмите Enter для продолжения...")

    logger.info("Готово")
    input("Нажмите Enter для выхода...")


# ============================================================
# НОВЫЙ РЕЖИМ: hotel city variants (доп. опция)
# Не затрагивает старый collection-логику (Работает — не трогай!)
# Использует отдельные конфиги:
#   configs/hotel_urls.txt   (1-я строка — общие параметры для человека, ниже — ссылки на отели)
#   configs/departure_cities.txt
# Выход: postsCollections/hotel_cities_*.txt
# ============================================================

def read_hotel_urls_config(path: Path = Path("configs/hotel_urls.txt")) -> Tuple[str, List[str]]:
    """Читает hotel_urls.txt.
    Возвращает (common_params_line, list_of_hotel_urls)
    Первая непустая строка без # — общие параметры.
    Дальше — URL-ы отелей.
    """
    if not path.exists():
        raise FileNotFoundError(f"Не найден {path}")
    lines = [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    common = ""
    urls = []
    for line in lines:
        if line.startswith("#"):
            continue
        if not common:
            common = line
            continue
        if line.startswith("http"):
            urls.append(line)
    if not urls:
        raise ValueError("В hotel_urls.txt не найдено ни одной ссылки на отель")
    return common, urls


def read_departure_cities(path: Path = Path("configs/departure_cities.txt")) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Не найден {path}")
    cities = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            cities.append(line)
    return cities


def extract_hotel_name(driver) -> str:
    """Берёт название отеля из h2 'Туры в Semt Luna Beach Hotel (2 предложения)'."""
    try:
        h2 = driver.find_element(
            browser.By.XPATH,
            "//h2[contains(@class, 'text-ds-mobile-h2') and contains(text(), 'Туры в ')]"
        )
        text = h2.text.strip()
        # "Туры в Semt Luna Beach Hotel (2 предложения)" → "Semt Luna Beach Hotel"
        m = re.search(r'Туры в (.+?)(?:\s*\(|\s*$)', text)
        if m:
            return m.group(1).strip()
        return text.replace("Туры в ", "").strip()
    except Exception:
        return "Unknown Hotel"


def set_departure_city(driver, city: str) -> bool:
    """Меняет город вылета на странице отеля (id=departureCity или placeholder)."""
    try:
        # Пробуем по id
        try:
            inp = browser.WebDriverWait(driver, 8).until(
                browser.EC.element_to_be_clickable((browser.By.ID, "departureCity"))
            )
        except:
            inp = browser.WebDriverWait(driver, 8).until(
                browser.EC.element_to_be_clickable((browser.By.XPATH, "//input[@placeholder='Город вылета']"))
            )

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
        time.sleep(0.2)
        inp.click()
        inp.send_keys(browser.Keys.CONTROL + "a")
        inp.send_keys(browser.Keys.DELETE)
        time.sleep(0.3)
        inp.send_keys(city)
        time.sleep(0.6)  # даём время на автокомплит

        # Пробуем выбрать из дропдауна, если появился (переиспользуем логику)
        try:
            dropdown = browser.WebDriverWait(driver, 4).until(
                browser.EC.presence_of_element_located((browser.By.XPATH, "//div[contains(@class, 'absolute') and contains(@class, 'z-50')]"))
            )
            try:
                target = dropdown.find_element(browser.By.XPATH, f".//div[contains(@class, 'cursor-pointer') and normalize-space()='{city}']")
            except:
                target = dropdown.find_element(browser.By.XPATH, f".//div[contains(@class, 'cursor-pointer')]//*[normalize-space()='{city}']/..")
            target.click()
            time.sleep(0.4)
        except:
            pass  # иногда не нужен дропдаун

        return True
    except Exception as e:
        logger.error(f"Не удалось установить город {city}: {e}")
        save_debug_info(driver, f"set_city_{city}")
        return False


def click_find_tour_button(driver) -> bool:
    """Нажимает кнопку 'Найти тур' (ищет по тексту и классу, как в старом коде)."""
    try:
        try:
            btn = browser.WebDriverWait(driver, 10).until(
                browser.EC.element_to_be_clickable((browser.By.XPATH, "//button[contains(@class, 'bg-orange-500') and contains(., 'Найти тур')]"))
            )
        except:
            btn = browser.WebDriverWait(driver, 10).until(
                browser.EC.element_to_be_clickable((browser.By.XPATH, "//button[contains(text(), 'Найти тур')]"))
            )
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", btn)
        logger.info("Нажата кнопка 'Найти тур'")
        return True
    except Exception as e:
        logger.error(f"Не удалось нажать 'Найти тур': {e}")
        save_debug_info(driver, "click_find_tour")
        return False


def get_cheapest_price_and_url(driver, max_wait_seconds: int = 45) -> Tuple[str, str]:
    """
    Ещё более терпеливая версия.
    Ждёт до max_wait_seconds (по умолчанию 45 сек), пока не появится кнопка с реальной ценой "от XXX ₽".
    "Выбрать" и другие не-ценовые тексты игнорируются — продолжаем ждать.
    Только явное сообщение "Таких предложений..." даёт быстрый NO_RESULTS.
    На таймауте сохраняет дебаг-пак для анализа.
    """
    price_pattern = re.compile(r'от\s+([\d\s\xa0]+)')
    deadline = time.time() + max_wait_seconds

    while time.time() < deadline:
        time.sleep(1.5)

        try:
            buttons = driver.find_elements(browser.By.CSS_SELECTOR, "a.bg-orange-500")
            for btn in buttons:
                try:
                    span = btn.find_element(browser.By.TAG_NAME, "span")
                    price_text = span.text.strip()
                except:
                    price_text = btn.text.strip()

                m = price_pattern.search(price_text)
                if m:
                    num = m.group(1).replace(' ', '').replace('\xa0', '').replace('&nbsp;', '')
                    if num.isdigit():
                        price_str = f"от {int(num):,} р".replace(',', ' ')
                        return price_str, driver.current_url
        except Exception:
            pass

        # Только явное "нет результатов" даёт быстрый NO_RESULTS.
        # "Выбрать" и отсутствие кнопок — ждём дальше.
        try:
            no_res = driver.find_element(
                browser.By.XPATH,
                "//h3[normalize-space()='Таких предложений у туроператоров не нашлось']"
            )
            if no_res.is_displayed():
                return "NO_RESULTS", driver.current_url
        except:
            pass

    # Полный таймаут — нет цены за отведённое время
    logger.warning(f"Таймаут {max_wait_seconds} сек: не дождались реальной цены (возможно медленно грузится или нет предложений)")
    try:
        save_debug_info(driver, "price_timeout")
    except:
        pass
    return "NO_RESULTS", driver.current_url


def run_hotel_city_mode():
    """Новый режим для конкретных отелей + разные города вылета.
    Полностью независим от старого collection-логики.
    """
    logger.info("=== Запущен HOTEL CITY MODE ===")
    try:
        common_params, hotel_urls = read_hotel_urls_config()
        cities = read_departure_cities()
    except Exception as e:
        logger.error(f"Ошибка чтения конфигов hotel mode: {e}")
        input("Нажмите Enter для выхода...")
        return

    logger.info(f"Общие параметры: {common_params}")
    logger.info(f"Отелей: {len(hotel_urls)}, городов: {len(cities)}")

    OUTPUT_DIR = Path("postsCollections")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_file = OUTPUT_DIR / f"hotel_cities_{ts}.txt"

    all_lines = [common_params, ""]  # общие параметры один раз вверху для человека

    for hotel_idx, base_url in enumerate(hotel_urls, 1):
        logger.info(f"\n=== Отель {hotel_idx} ===")
        logger.info(f"URL: {base_url[:100]}...")

        init_selenium()
        driver = build_driver(eager=True)
        hotel_name = "Unknown Hotel"
        hotel_lines = []

        try:
            driver.get(base_url)
            time.sleep(2.5)
            hotel_name = extract_hotel_name(driver)
            logger.info(f"Название отеля: {hotel_name}")

            # Заголовок для этого отеля (с названием отеля через | )
            header_line = common_params.rstrip("|") + f"|{hotel_name}"
            hotel_lines.append(header_line)
            hotel_lines.append(f"Отель {hotel_idx}: {hotel_name}")

            for city in cities:
                logger.info(f"  Обрабатываем город: {city}")
                if not set_departure_city(driver, city):
                    hotel_lines.append(f"{city} - NO_RESULTS")
                    continue

                if not click_find_tour_button(driver):
                    hotel_lines.append(f"{city} - NO_RESULTS")
                    continue

                # Даём странице время на рендер предложений перед долгим ожиданием
                time.sleep(3)
                logger.info(f"    Ожидаем загрузки цен для {city} (до 45 сек)...")
                price, final_url = get_cheapest_price_and_url(driver)
                if price == "NO_RESULTS":
                    hotel_lines.append(f"{city} - NO_RESULTS")
                else:
                    hotel_lines.append(f"{city} - {price}")
                logger.info(f"    {city} → {price}")

                # Небольшая пауза между городами
                time.sleep(1.0)

            hotel_lines.append("")  # разделитель между отелями
            all_lines.extend(hotel_lines)

        except Exception as e:
            logger.error(f"Ошибка по отелю {hotel_name}: {e}")
            safe_city = city if 'city' in locals() else "unknown"
            save_debug_info(driver, f"hotel_{hotel_idx}_{safe_city}")
            hotel_lines.append(f"Ошибка обработки отеля: {e}")
        finally:
            try:
                driver.quit()
            except:
                pass

    # Сохраняем результат
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines))

    logger.info(f"\nГотово! Результат сохранён: {out_file}")
    logger.info("=== HOTEL CITY MODE завершён ===")
    input("Нажмите Enter для выхода...")


# ==================== КОНЕЦ НОВОГО РЕЖИМА ====================


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="collection_url_generator (collection + hotel city mode)")
    parser.add_argument("--hotel-mode", action="store_true", help="Запустить режим для конкретных отелей + разные города вылета (использует hotel_urls.txt и departure_cities.txt)")
    args = parser.parse_args()

    if args.hotel_mode:
        run_hotel_city_mode()
    else:
        main()
