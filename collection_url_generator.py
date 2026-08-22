#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict
import logging
import argparse
import browser
from browser import init_selenium, build_driver
from turbox.hotel_config import (
    parse_hotel_params_from_url,
    read_departure_cities,
    read_hotel_urls_config,
)
from turbox.paths import CONFIG_DIR, DEBUG_DIR, POSTS_COLLECTIONS_DIR
from turbox.search_config import (
    build_filtered_url,
    parse_config_links,
    parse_config_parameters,
    parse_extra_filters,
    read_sections,
    smart_split,
    split_filters_aware,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("collection_url_generator")

CONFIG_FILE = CONFIG_DIR / "url_generation_config.txt"
OUTPUT_FILE = CONFIG_DIR / "collection_urls.txt"
BASE_URL = "https://www.onlinetours.ru/"

DEFAULT_CONFIG = {
    "search_min_price_data": False,
}



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


def save_page_snapshot(driver, step_name: str):
    """Сохраняет страницу для разбора штатной аномалии без ERROR/traceback."""
    DEBUG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pack_dir = DEBUG_DIR / f"snapshot_{step_name}_{timestamp}"
    pack_dir.mkdir(exist_ok=True)

    try:
        driver.save_screenshot(pack_dir / "screenshot.png")
    except Exception as e:
        logger.debug(f"Не удалось сохранить скрин: {e}")

    try:
        html_snippet = driver.page_source[:150000]
        with open(pack_dir / "source.html", "w", encoding="utf-8") as f:
            f.write(html_snippet)
    except Exception as e:
        logger.debug(f"Не удалось сохранить source: {e}")

    try:
        with open(pack_dir / "info.txt", "w", encoding="utf-8") as f:
            f.write(f"Step: {step_name}\n")
            f.write(f"URL: {driver.current_url}\n")
    except Exception as e:
        logger.debug(f"Не удалось сохранить info: {e}")

    logger.warning(f"Сохранён снимок страницы: {pack_dir} (куки НЕ сохраняются)")


def get_last_index(output_file=OUTPUT_FILE) -> int:
    if not output_file.exists():
        return 0
    content = output_file.read_text(encoding="utf-8")
    matches = re.findall(r'^(\d+)\.', content, re.MULTILINE)
    if not matches:
        return 0
    return max(int(m) for m in matches)

def append_result(index: int, city: str, country: str, start_date: datetime, end_date: datetime, nights_min: int, nights_max: int, adults: int, url: str, extra_info: str = None, output_file=OUTPUT_FILE):
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

    block = f"{main_part}\n{url}\n"

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(block)

def clear_input_field(driver, element):
    driver.execute_script("arguments[0].value = '';", element)
    driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", element)
    time.sleep(0.3)

def set_city_country(driver, placeholder: str, value: str) -> bool:
    """Выбирает город вылета.

    На текущей версии OnlineTours ввод значения + Enter стабильно работает, а
    ожидание старого dropdown каждый раз добавляло около 5 секунд. Поэтому
    сначала используем Enter, а старый dropdown оставляем как fallback.
    """
    logger.info(f"Выбор '{value}' в поле '{placeholder}'")
    try:
        input_field = browser.WebDriverWait(driver, 15).until(
            browser.EC.presence_of_element_located((browser.By.XPATH, f"//input[@placeholder='{placeholder}']"))
        )
        driver.execute_script("arguments[0].click();", input_field)
        time.sleep(0.2)
        input_field.send_keys(browser.Keys.CONTROL + "a")
        input_field.send_keys(browser.Keys.DELETE)
        time.sleep(0.1)
        input_field.send_keys(value)

        # Основной путь: на текущей верстке OnlineTours Enter выбирает город
        # стабильнее старого поиска dropdown. Проверяем итоговое значение.
        input_field.send_keys(browser.Keys.ENTER)
        try:
            browser.WebDriverWait(driver, 2).until(
                lambda d: (input_field.get_attribute("value") or "").strip() == value
            )
            logger.info(f"Значение '{value}' выбрано через Enter")
            return True
        except browser.TimeoutException:
            logger.info("Enter не подтвердил значение, пробуем выбор из списка")

        # Fallback для возможного будущего изменения поведения сайта.
        dropdown = browser.WebDriverWait(driver, 3).until(
            browser.EC.presence_of_element_located((
                browser.By.XPATH,
                "//div[contains(@class, 'shadow-ds-sm') and contains(@class, 'absolute') and contains(@class, 'z-20')]"
            ))
        )

        try:
            target_span = dropdown.find_element(browser.By.XPATH, f".//span[text()='{value}']")
            target = target_span.find_element(
                browser.By.XPATH,
                "./ancestor::div[contains(@class, 'cursor-pointer')]"
            )
        except Exception:
            try:
                target = dropdown.find_element(
                    browser.By.XPATH,
                    f".//div[contains(@class, 'cursor-pointer') and normalize-space(.)='{value}']"
                )
            except Exception:
                target = dropdown.find_element(
                    browser.By.XPATH,
                    f".//div[contains(@class, 'cursor-pointer') and contains(., '{value}')]"
                )

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
        driver.execute_script("arguments[0].click();", target)
        logger.info(f"Значение '{value}' выбрано из списка")
        return True

    except Exception as e:
        logger.error(f"Ошибка выбора '{value}' в поле '{placeholder}': {e}")
        save_debug_info(driver, f"select_{placeholder}")
        return False


def set_destination_country(driver, value: str) -> bool:
    placeholder = "Страна, курорт, отель"
    logger.info(f"Выбор страны '{value}' в поле '{placeholder}'")
    try:
        input_field = browser.WebDriverWait(driver, 15).until(
            browser.EC.presence_of_element_located((browser.By.XPATH, f"//input[@placeholder='{placeholder}']"))
        )
        driver.execute_script("arguments[0].click();", input_field)
        time.sleep(0.3)
        input_field.send_keys(browser.Keys.CONTROL + "a")
        input_field.send_keys(browser.Keys.DELETE)
        time.sleep(0.2)
        input_field.send_keys(value)

        # Ждём кликабельный div.cursor-pointer, внутри которого есть span с нужным текстом
        target = browser.WebDriverWait(driver, 5).until(
            browser.EC.element_to_be_clickable((
                browser.By.XPATH,
                f"//div[contains(@class, 'cursor-pointer')]//span[text()='{value}']/ancestor::div[contains(@class, 'cursor-pointer')]"
            ))
        )

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", target)
        logger.info(f"Страна '{value}' выбрана")
        time.sleep(0.5)
        return True

    except Exception as e:
        logger.error(f"Ошибка выбора страны '{value}': {e}")
        # fallback: Enter
        try:
            input_field.send_keys(browser.Keys.ENTER)
            time.sleep(1)
            current_val = input_field.get_attribute("value")
            if current_val.strip() == value:
                logger.info(f"Страна '{value}' выбрана через Enter")
                return True
        except:
            pass
        save_debug_info(driver, "select_destination")
        return False
def click_date(driver, target_date: datetime) -> bool:
    target_month = target_date.month
    target_day = target_date.day
    target_year = target_date.year

    month_names_ru = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                      'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']
    target_month_name = month_names_ru[target_month - 1]

    # 1. Находим боковую панель
    try:
        sidebar = driver.find_element(browser.By.XPATH,
            "//div[contains(@class, 'bg-ds-neutral-50') and contains(@class, 'min-w-[120px]')]")
    except Exception:
        logger.warning("Боковая панель месяцев не найдена")
        return False

    # 2. Ищем в панели нужный месяц (без учёта года)
    month_items = sidebar.find_elements(browser.By.XPATH,
        ".//div[contains(@class, 'cursor-pointer') and contains(@class, 'pl-4')]")
    found = None
    for item in month_items:
        # Текст может быть "Июль" или "Июль 2027"
        if item.text.strip().startswith(target_month_name):
            found = item
            break
    if not found:
        logger.warning(f"Месяц {target_month_name} не найден в панели")
        return False

    # Кликаем по месяцу
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", found)
    time.sleep(0.3)
    found.click()
    time.sleep(0.5)

    # 3. Находим блок месяца по id
    month_index = target_month - 1  # июль -> 6
    month_block_id = f"month{month_index}"
    try:
        month_block = driver.find_element(browser.By.ID, month_block_id)
    except Exception:
        logger.warning(f"Блок {month_block_id} не найден")
        return False

    # 4. Ищем день
    day_id = f"day{month_index}_{target_day}"
    try:
        day_elem = month_block.find_element(browser.By.ID, day_id)
    except Exception:
        logger.warning(f"День {day_id} не найден")
        return False

    # 5. Кликаем по дню
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", day_elem)
    time.sleep(0.3)
    try:
        day_elem.click()
        logger.info(f"Выбран день {target_day}.{target_month}.{target_year}")
        return True
    except Exception as e:
        logger.warning(f"Клик по дню не удался: {e}")
        return False

def select_date_range(driver, start_date: datetime, end_date: datetime) -> bool:
    logger.info(f"Выбор дат: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
    try:
        # Новый селектор: ищем контейнер с текстом "Дата вылета" и кликабельным родителем
        date_container = browser.WebDriverWait(driver, 15).until(
            browser.EC.element_to_be_clickable((
                browser.By.XPATH,
                "//div[contains(@class, 'cursor-pointer') and .//div[text()='Дата вылета']]"
            ))
        )
        date_container.click()
        logger.info("Календарь открыт")
        time.sleep(1)
    except Exception as e:
        logger.error(f"Не удалось открыть календарь: {e}")
        save_debug_info(driver, "open_calendar")
        return False

    # Выбор первой даты
    if not click_date(driver, start_date):
        logger.error("Не удалось выбрать первую дату")
        return False

    time.sleep(0.5)

    # Выбор второй даты (если диапазон)
    if start_date != end_date:
        if not click_date(driver, end_date):
            logger.error("Не удалось выбрать вторую дату")
            return False
    else:
        # Если даты одинаковые, кликаем ещё раз по той же дате (для подтверждения)
        if not click_date(driver, start_date):
            logger.error("Не удалось выбрать повторную дату")
            return False

    logger.info("Диапазон дат выбран")
    time.sleep(1)
    return True

def set_nights_range(driver, nights_min: int, nights_max: int) -> bool:
    logger.info(f"Выбор ночей: {nights_min} - {nights_max}")

    def open_nights_panel():
        try:
            container = browser.WebDriverWait(driver, 10).until(
                browser.EC.element_to_be_clickable((
                    browser.By.XPATH,
                    "//div[contains(@class, 'cursor-pointer') and .//div[text()='На сколько']]"
                ))
            )
            container.click()
            logger.info("Панель ночей открыта")
            time.sleep(0.8)
            return True
        except Exception as e:
            logger.error(f"Не удалось открыть панель ночей: {e}")
            return False

    def click_night_value(value: int):
        try:
            # Ищем div.cursor-pointer, внутри которого span с нужным числом
            clickable = driver.find_element(
                browser.By.XPATH,
                f"//div[contains(@class, 'cursor-pointer') and .//span[text()='{value}']]"
            )
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", clickable)
            time.sleep(0.2)
            driver.execute_script("arguments[0].click();", clickable)
            logger.info(f"Клик по контейнеру с числом {value} выполнен")
            time.sleep(0.3)
            return True
        except Exception as e:
            logger.error(f"Не удалось кликнуть по контейнеру с числом {value}: {e}")
            return False

    # Открываем панель
    if not open_nights_panel():
        return False

    # Выбираем минимальное
    if not click_night_value(nights_min):
        return False

    # Если диапазон разный, выбираем максимальное
    if nights_max != nights_min:
        time.sleep(0.5)
        if not click_night_value(nights_max):
            time.sleep(0.5)
            if not click_night_value(nights_max):
                logger.error("Не удалось выбрать максимальное количество ночей")
                return False

    # Закрываем панель
    try:
        container = driver.find_element(
            browser.By.XPATH,
            "//div[contains(@class, 'cursor-pointer') and .//div[text()='На сколько']]"
        )
        driver.execute_script("arguments[0].click();", container)
        logger.info("Панель ночей закрыта")
    except:
        driver.execute_script("document.body.click();")

    time.sleep(0.5)
    return True

    # Закрываем панель, чтобы применить выбор
    try:
        # Кликаем по тому же контейнеру "На сколько"
        container = driver.find_element(
            browser.By.XPATH,
            "//div[contains(@class, 'cursor-pointer') and .//div[text()='На сколько']]"
        )
        driver.execute_script("arguments[0].click();", container)
        logger.info("Панель ночей закрыта (применён выбор)")
    except:
        # Если не получилось, кликаем по body
        driver.execute_script("document.body.click();")
        logger.info("Панель ночей закрыта через body")

    time.sleep(0.5)
    return True

def set_adults(driver, adults: int) -> bool:
    if adults == 2:
        logger.info("Взрослых 2 (по умолчанию), пропускаем")
        return True
    logger.warning("Изменение взрослых не поддерживается")
    return True

def _has_no_results(driver) -> bool:
    """Проверяет известное сообщение OnlineTours об отсутствии предложений."""
    try:
        elements = driver.find_elements(
            browser.By.XPATH,
            "//*[self::h2 or self::h3 or self::p][contains(normalize-space(.), 'Таких предложений у туроператоров не нашлось')]"
        )
        return any(element.is_displayed() for element in elements)
    except Exception:
        return False


def _has_price(driver) -> bool:
    """Возвращает True, когда на странице появился используемый нами элемент цены."""
    try:
        elements = driver.find_elements(
            browser.By.XPATH,
            "//span[contains(@class, 'text-ds-mobile-h4') and contains(@class, 'text-ds-primary')]"
        )
        return any(element.is_displayed() and element.text.strip() for element in elements)
    except Exception:
        return False


def wait_price_or_no_results(driver, timeout=12) -> str:
    """Ждёт полезное состояние страницы вместо фиксированного ожидания.

    Возвращает PRICE, NO_RESULTS или UNKNOWN.
    """
    try:
        return browser.WebDriverWait(driver, timeout, poll_frequency=0.25).until(
            lambda d: "NO_RESULTS" if _has_no_results(d) else ("PRICE" if _has_price(d) else False)
        )
    except browser.TimeoutException:
        return "UNKNOWN"


def select_cheapest_date(driver, timeout=30):
    logger.info("Поиск блока с датами для выбора самой дешёвой даты...")
    buttons_xpath = "//button[contains(@style, 'calc(')]"

    def _date_buttons_or_empty_state(d):
        if _has_no_results(d):
            return "NO_RESULTS"
        buttons = d.find_elements(browser.By.XPATH, buttons_xpath)
        return buttons if buttons else False

    try:
        state = browser.WebDriverWait(driver, timeout, poll_frequency=0.25).until(_date_buttons_or_empty_state)
        if state == "NO_RESULTS":
            raise Exception("NO_RESULTS")
        buttons = state
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


def extract_min_price(driver) -> Optional[int]:
    """Извлекает минимальную цену со страницы результатов (из первого тура)."""
    try:
        price_elem = driver.find_element(browser.By.XPATH, "//span[contains(@class, 'text-ds-mobile-h4') and contains(@class, 'text-ds-primary')]")
        price_text = price_elem.text.strip()
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
        date_elem = driver.find_element(browser.By.XPATH, "//div[contains(@class, 'text-ds-body-md') and contains(@class, 'text-ds-primary')]")
        date_text = date_elem.text.strip()
        if not date_text:
            return None

        original_str = original_start_date.strftime("%d.%m.%Y")
        original_range_str = f"{original_start_date.strftime('%d.%m.%Y')}-{original_end_date.strftime('%d.%m.%Y')}"

        if date_text != original_str and date_text != original_range_str:
            return date_text
        return None
    except Exception as e:
        logger.warning(f"Не удалось извлечь дату: {e}")
        return None

def fill_form_and_get_url(city: str, country: str, start_date: datetime, end_date: datetime, nights_min: int, nights_max: int, adults: int, search_min_price_data: bool, extra_filters: Dict) -> Optional[Dict]:
    request_started = time.perf_counter()
    timings = {}
    stage_started = request_started
    init_selenium()
    driver = build_driver(eager=True)
    try:
        driver.get(BASE_URL)
        time.sleep(2)
        logger.info("Главная страница загружена")
        timings["open"] = time.perf_counter() - stage_started

        stage_started = time.perf_counter()
        if not set_city_country(driver, "Город вылета", city): return None
        timings["city"] = time.perf_counter() - stage_started

        stage_started = time.perf_counter()
        if not set_destination_country(driver, country): return None
        timings["destination"] = time.perf_counter() - stage_started

        stage_started = time.perf_counter()
        if not select_date_range(driver, start_date, end_date): return None
        timings["dates"] = time.perf_counter() - stage_started

        stage_started = time.perf_counter()
        if not set_nights_range(driver, nights_min, nights_max): return None
        timings["nights"] = time.perf_counter() - stage_started

        stage_started = time.perf_counter()
        if not set_adults(driver, adults): return None
        timings["adults"] = time.perf_counter() - stage_started

        stage_started = time.perf_counter()

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
        timings["search"] = time.perf_counter() - stage_started

        if search_min_price_data:
            stage_started = time.perf_counter()
            logger.info("Выбор самой дешёвой даты (searchMinPriceData=true)...")
            try:
                select_cheapest_date(driver)
            except Exception:
                # Не тратим отдельные 10 секунд на поиск отсутствующего сообщения
                # перед каждой успешной выдачей. Проверяем NO_RESULTS только если
                # поиск дешёвой даты действительно не смог продолжить.
                if _has_no_results(driver):
                    logger.warning("Обнаружено сообщение: 'Таких предложений у туроператоров не нашлось'")
                    return {"url": "NO_RESULTS", "extra_info": None}
                raise
            url = driver.current_url
            logger.info(f"Новый URL после выбора дешёвой даты: {url}")
            timings["cheapest_date"] = time.perf_counter() - stage_started

        stage_started = time.perf_counter()
        if extra_filters and (extra_filters.get("price_min") or extra_filters.get("price_max") or extra_filters.get("rating") or extra_filters.get("meal_ids") or extra_filters.get("sort")):
            logger.info(f"Применение фильтров через параметры URL...")
            new_url = build_filtered_url(url, extra_filters)
            if new_url != url:
                logger.info(f"Новый URL с фильтрами: {new_url}")
                driver.get(new_url)
                browser.WebDriverWait(driver, 20).until(lambda d: "/tours/" in d.current_url)
                url = driver.current_url
                logger.info(f"Финальный URL после фильтров: {url}")
        timings["filters"] = time.perf_counter() - stage_started

        stage_started = time.perf_counter()
        min_price = None
        if extra_filters.get("sort") == "price":
            # Раньше здесь всегда сначала ждали 10 секунд, чтобы убедиться,
            # что сообщения NO_RESULTS нет, даже если цена уже была на странице.
            # Теперь идём дальше сразу после появления цены или empty-state.
            state = wait_price_or_no_results(driver, timeout=12)
            if state == "NO_RESULTS":
                logger.warning("Обнаружено сообщение: 'Таких предложений у туроператоров не нашлось'")
                return {"url": "NO_RESULTS", "extra_info": None}

            min_price = extract_min_price(driver)
            if min_price:
                logger.info(f"Минимальная цена: {min_price}")
            else:
                logger.warning(f"Цена не найдена после ожидания состояния страницы: {state}")
                save_page_snapshot(driver, "price_missing")
        elif _has_no_results(driver):
            logger.warning("Обнаружено сообщение: 'Таких предложений у туроператоров не нашлось'")
            return {"url": "NO_RESULTS", "extra_info": None}
        timings["price_state"] = time.perf_counter() - stage_started

        final_date = extract_final_date(driver, start_date, end_date)
        if final_date:
            logger.info(f"Итоговая дата изменилась: {final_date}")

        extra_parts = []
        if final_date:
            extra_parts.append(f"Новая дата {final_date}")
        if min_price:
            extra_parts.append(f"от {min_price}")

        meal_ids = extra_filters.get("meal_ids", [])
        if meal_ids:
            if "739" in meal_ids or "740" in meal_ids:
                extra_parts.append("всё включено")
            if "730" in meal_ids:
                extra_parts.append("завтраки")

        extra_info = " | ".join(extra_parts) if extra_parts else None


        # === ФИНАЛЬНАЯ ПРОВЕРКА НА NO_RESULTS ===
        try:
            no_results = driver.find_element(
                browser.By.XPATH,
                "//h3[normalize-space()='Таких предложений у туроператоров не нашлось']"
            )
            if no_results.is_displayed():
                logger.warning("Финальная проверка: обнаружено 'Таких предложений у туроператоров не нашлось'")
                return {"url": "NO_RESULTS", "extra_info": None}
        except:
            pass

        return {"url": url, "extra_info": extra_info}

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        save_debug_info(driver, "general")
        return None
    finally:
        driver.quit()
        elapsed = time.perf_counter() - request_started
        timing_text = ", ".join(f"{name}={value:.1f}s" for name, value in timings.items())
        if timing_text:
            logger.info(f"Тайминги: {timing_text}, total={elapsed:.1f}s")
        logger.info(f"Драйвер закрыт; время запроса: {elapsed:.1f} сек")

def main(config_file=CONFIG_FILE, output_file=OUTPUT_FILE, limit: Optional[int] = None):
    try:
        sections = read_sections(config_file)
        config = parse_config_parameters(sections)
        requests = parse_config_links(sections)
    except Exception as e:
        logger.error(f"Ошибка чтения конфигурации: {e}")
        input("Нажмите Enter для выхода...")
        return

    if limit is not None:
        requests = requests[:max(limit, 0)]

    if not requests:
        logger.warning("Нет запросов в файле")
        input("Нажмите Enter для выхода...")
        return

    last_index = get_last_index(output_file)
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
            append_result(current_index, city, country, start_date, end_date, nights_min, nights_max, adults, result["url"], result["extra_info"], output_file=output_file)
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
#   configs/hotel_urls.txt   (ссылки на отели, первая строка игнорируется)
#   configs/departure_cities.txt
# Выход: postsCollections/hotel_cities_*.txt
# ============================================================



def extract_hotel_name(driver) -> str:
    """Берёт название отеля из h2 'Туры в Semt Luna Beach Hotel (2 предложения)'."""
    try:
        h2 = driver.find_element(
            browser.By.XPATH,
            "//h2[contains(@class, 'text-ds-mobile-h2') and contains(text(), 'Туры в ')]"
        )
        text = h2.text.strip()
        m = re.search(r'Туры в (.+?)(?:\s*\(|\s*$)', text)
        if m:
            return m.group(1).strip()
        return text.replace("Туры в ", "").strip()
    except Exception:
        return "Unknown Hotel"

def set_departure_city(driver, city: str) -> bool:
    """Меняет город вылета на странице отеля (id=departureCity или placeholder)."""
    try:
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
        time.sleep(0.6)

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
            pass

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

        try:
            no_res = driver.find_element(
                browser.By.XPATH,
                "//h3[normalize-space()='Таких предложений у туроператоров не нашлось']"
            )
            if no_res.is_displayed():
                return "NO_RESULTS", driver.current_url
        except:
            pass

    logger.warning(f"Таймаут {max_wait_seconds} сек: не дождались реальной цены")
    try:
        save_debug_info(driver, "price_timeout")
    except:
        pass
    return "NO_RESULTS", driver.current_url

# === НОВЫЕ ФУНКЦИИ ДЛЯ УМНОГО ЗАГОЛОВКА ===


def extract_meal_type(driver) -> str:
    """Извлекает тип питания со страницы отеля (над кнопкой с ценой)."""
    # Сначала ждём появления контейнера с питанием (до 10 секунд)
    try:
        container = browser.WebDriverWait(driver, 10).until(
            browser.EC.presence_of_element_located((
                browser.By.XPATH,
                "//div[contains(@class, 'flex flex-col gap-4') and contains(@class, 'md:flex-row')]"
            ))
        )
        meal_div = container.find_element(
            browser.By.XPATH,
            ".//div[contains(@class, 'text-ds-body-sm') and contains(@class, 'text-ds-primary')]"
        )
        text = meal_div.text.strip()
        if text:
            return text
    except Exception as e:
        logger.debug(f"Не удалось извлечь тип питания через контейнер: {e}")

    # Фоллбэк: ищем по тексту питания на всей странице
    try:
        meal_keywords = ["Ультра всё включено", "Всё включено", "Завтрак", "Полупансион", "Без питания"]
        for keyword in meal_keywords:
            elements = driver.find_elements(
                browser.By.XPATH,
                f"//*[contains(text(), '{keyword}')]"
            )
            for el in elements:
                text = el.text.strip()
                if text and len(text) < 50:  # Фильтруем слишком длинные тексты
                    return text
    except Exception as e:
        logger.debug(f"Фоллбэк по типу питания не сработал: {e}")

    return "Питание не указано"

# === КОНЕЦ НОВЫХ ФУНКЦИЙ ===

def run_hotel_city_mode():
    """Новый режим для конкретных отелей + разные города вылета.
    Полностью независим от старого collection-логики.
    """
    logger.info("=== Запущен HOTEL CITY MODE ===")
    try:
        hotel_urls = read_hotel_urls_config()
        cities = read_departure_cities()
    except Exception as e:
        logger.error(f"Ошибка чтения конфигов hotel mode: {e}")
        input("Нажмите Enter для выхода...")
        return

    logger.info(f"Отелей: {len(hotel_urls)}, городов: {len(cities)}")

    OUTPUT_DIR = POSTS_COLLECTIONS_DIR
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_file = OUTPUT_DIR / f"hotel_cities_{ts}.txt"

    all_lines = []  # Теперь заголовки формируются для каждого отеля отдельно

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

            # === НОВОЕ: Парсим параметры из URL и извлекаем питание ===
            url_params = parse_hotel_params_from_url(base_url)
            meal_type = extract_meal_type(driver)

            # Формируем умный заголовок для этого отеля
            header_parts = [
                url_params["country"],
                url_params["dates"],
                f"ночей: {url_params['nights']}",
                f"взрослых: {url_params['adults']}"
            ]
            if url_params["kids_info"]:
                header_parts.append(url_params["kids_info"])
            header_parts.append(meal_type)
            header_parts.append(hotel_name)

            header_line = " | ".join(header_parts)

            hotel_lines.append(header_line)
            hotel_lines.append(f"Отель {hotel_idx}: {hotel_name}")

            city_idx = 1  # Счётчик туров для каждого отеля
            for city in cities:
                logger.info(f"  Обрабатываем город: {city}")
                if not set_departure_city(driver, city):
                    hotel_lines.append(f"{city_idx}. {city} - NO_RESULTS")
                    city_idx += 1
                    continue

                if not click_find_tour_button(driver):
                    hotel_lines.append(f"{city_idx}. {city} - NO_RESULTS")
                    city_idx += 1
                    continue

                time.sleep(3)
                logger.info(f"    Ожидаем загрузки цен для {city} (до 45 сек)...")
                price, final_url = get_cheapest_price_and_url(driver)
                if price == "NO_RESULTS":
                    hotel_lines.append(f"{city_idx}. {city} - NO_RESULTS")
                else:
                    # ДОБАВЛЯЕМ URL ЧЕРЕЗ РАЗДЕЛИТЕЛЬ
                    hotel_lines.append(f"{city_idx}. {city} - {price} | {final_url}")

                logger.info(f"    {city} → {price}")
                city_idx += 1

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
    parser.add_argument("--hotel-mode", action="store_true", help="Запустить режим для конкретных отелей + разные города вылета")
    parser.add_argument("--config", help="Альтернативный search config (обычный режим)")
    parser.add_argument("--output", help="Альтернативный collection_urls output (обычный режим)")
    parser.add_argument("--limit", type=int, help="Обработать только первые N запросов (удобно для smoke-test)")
    args = parser.parse_args()

    if args.hotel_mode:
        run_hotel_city_mode()
    else:
        main(
            config_file=CONFIG_DIR / "url_generation_config.txt" if not args.config else Path(args.config).resolve(),
            output_file=CONFIG_DIR / "collection_urls.txt" if not args.output else Path(args.output).resolve(),
            limit=args.limit,
        )
