import logging
import re
import time
from typing import List, Optional, Tuple, Dict, Any
from urllib.parse import urljoin

import browser

BASE_URL = "https://www.onlinetours.ru"
TIMEOUT = 25
logger = logging.getLogger(__name__)


def parse_price(text: str) -> Optional[int]:
    """Извлекает число из строки типа 'от 139 510 ₽' или '139510'."""
    cleaned = text.replace("\xa0", "").replace(" ", "")
    m = re.search(r"(\d+)\s*₽", cleaned)
    if not m:
        m = re.search(r"(\d+)", cleaned)
    return int(m.group(1)) if m else None


def extract_departure_city(driver) -> str:
    """Город вылета из поля #departureCity."""
    for inp in driver.find_elements(browser.By.XPATH, "//input[@id='departureCity' or @name='departureCity']"):
        try:
            val = (inp.get_attribute("value") or "").strip()
            if val:
                return val
        except Exception:
            continue
    return "Неизвестно"


def extract_destination_country(driver) -> str:
    """Страна назначения из поля #destination."""
    try:
        el = driver.find_element(browser.By.ID, "destination")
        value = el.get_attribute("value") or ""
        return value.split(",")[0].strip() if value else "Неизвестно"
    except Exception:
        return "Неизвестно"


def collect_hotel_links_from_collection(
    driver, collection_url: str, min_price: int, max_price: int
) -> Tuple[str, str, List[Dict[str, Any]]]:
    """
    Загружает страницу подборки, собирает карточки отелей,
    фильтрует по цене, возвращает:
        departure_city,
        destination_country,
        список словарей: [{"hotel_url": str, "price_from_card": int}, ...]
    """
    logger.info(f"Загрузка подборки: {collection_url}")
    driver.get(collection_url)
    browser.WebDriverWait(driver, TIMEOUT).until(
        browser.EC.presence_of_element_located((browser.By.TAG_NAME, "body"))
    )
    browser.close_popups(driver)

    # Прокрутка для подгрузки всех карточек
    for _ in range(5):
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(0.7)

    departure_city = extract_departure_city(driver)
    destination_country = extract_destination_country(driver)
    logger.info(f"Город вылета: {departure_city}, Страна: {destination_country}")

    # Надёжный селектор карточек отелей на подборке (по вашему HTML)
    cards = driver.find_elements(
        browser.By.XPATH,
        "//li[contains(@class, 'flex flex-col rounded-4xl') and contains(@class, 'bg-white')]"
    )
    logger.info(f"Найдено карточек в подборке: {len(cards)}")

    filtered = []
    for card in cards:
        try:
            # Цена в meta itemprop="price"
            price_meta = card.find_element(browser.By.XPATH, ".//meta[@itemprop='price']")
            price = int(price_meta.get_attribute("content"))
            logger.debug(f"Цена из карточки: {price}")

            # Ссылка на отель (может быть в любом <a> с href, содержащим '/oteli/')
            hotel_link = card.find_element(
                browser.By.XPATH,
                ".//a[contains(@href, '/oteli/')]"
            )
            href = hotel_link.get_attribute("href")
            if not href:
                continue
            if href.startswith("//"):
                href = "https:" + href
            if href.startswith("/"):
                href = urljoin(BASE_URL, href)

            if min_price <= price <= max_price:
                logger.info(f"Цена {price} подходит, отель {href}")
                filtered.append({"hotel_url": href, "price_from_card": price})
            else:
                logger.info(f"Цена {price} вне диапазона [{min_price}, {max_price}] – пропускаем")
        except Exception as e:
            logger.debug(f"Ошибка при обработке карточки: {e}")
            continue

    logger.info(f"Отобрано отелей по цене: {len(filtered)}")
    return departure_city, destination_country, filtered


def extract_hotel_name(driver, fallback_url: str) -> str:
    """Извлекает название отеля из H1/H2."""
    for h in driver.find_elements(browser.By.XPATH, "//h1|//h2"):
        try:
            text = (h.text or "").strip()
            if h.is_displayed() and len(text) > 4:
                return text
        except Exception:
            continue
    slug = fallback_url.split("/oteli/")[-1].split("?")[0].split("/")[-1]
    return slug.replace("-", " ").title()


def extract_min_offer_from_hotel(
    driver,
    hotel_url: str,
    departure_city: str,
    arrival_country: str,
    source_url: str
) -> Optional[Dict[str, Any]]:
    logger.info(f"Обработка отеля: {hotel_url}")
    driver.get(hotel_url)
    browser.WebDriverWait(driver, TIMEOUT).until(
        browser.EC.presence_of_element_located((browser.By.TAG_NAME, "body"))
    )
    browser.close_popups(driver)

    # Извлечение целевой цены из URL (параметр cheapest_price)
    match = re.search(r'cheapest_price=(\d+)', hotel_url)
    expected_price = int(match.group(1)) if match else None
    tolerance = 0.03  # 3% допуск на естественные колебания цены

    if expected_price:
        logger.debug(f"Ожидаемая минимальная цена из URL: {expected_price}")
        logger.info("Ожидание загрузки реальных цен (до 10 сек)...")
        start_time = time.time()
        while time.time() - start_time < 10:
            links = driver.find_elements(browser.By.XPATH, "//a[contains(@href, '/offer_groups')]")
            if links:
                found = False
                for link in links:
                    try:
                        # Пытаемся найти цену внутри ссылки или рядом
                        price_text = None
                        price_elem = link.find_elements(browser.By.XPATH, ".//*[contains(text(), '₽')]")
                        if price_elem:
                            price_text = price_elem[0].text
                        else:
                            parent = link.find_element(browser.By.XPATH, "..")
                            price_elem = parent.find_elements(browser.By.XPATH, ".//*[contains(text(), '₽')]")
                            if price_elem:
                                price_text = price_elem[0].text
                        if not price_text:
                            price_text = link.text

                        if not price_text:
                            continue

                        price_val = parse_price(price_text)
                        if price_val and price_val <= expected_price * (1 + tolerance):
                            logger.info(f"Цены стабилизировались: найдена цена {price_val} <= {expected_price} (допуск {tolerance*100}%)")
                            found = True
                            break
                    except Exception:
                        continue
                if found:
                    break
            time.sleep(0.5)
        else:
            logger.warning(f"Не удалось дождаться цен в пределах {tolerance*100}% от {expected_price} за 10 секунд, продолжаем с текущими")
    else:
        # Небольшая задержка, если URL не содержит cheapest_price
        time.sleep(3)

    # Небольшая дополнительная пауза для полной отрисовки
    time.sleep(0.5)

    hotel_name = extract_hotel_name(driver, hotel_url)
    logger.debug(f"Название отеля: {hotel_name}")

    # Поиск всех ссылок на предложения (offer_groups)
    candidates = []
    try:
        offer_links = driver.find_elements(
            browser.By.XPATH,
            "//a[contains(@href, '/offer_groups')]"
        )
        logger.info(f"Найдено ссылок с /offer_groups: {len(offer_links)}")

        for link in offer_links:
            try:
                price_text = None
                price_elem = link.find_elements(browser.By.XPATH, ".//*[contains(text(), '₽')]")
                if price_elem:
                    price_text = price_elem[0].text
                else:
                    parent = link.find_element(browser.By.XPATH, "..")
                    price_elem = parent.find_elements(browser.By.XPATH, ".//*[contains(text(), '₽')]")
                    if price_elem:
                        price_text = price_elem[0].text
                if not price_text:
                    price_text = link.text

                if not price_text:
                    logger.debug("Не удалось найти текст с ценой в предложении")
                    continue

                price_val = parse_price(price_text)
                if price_val is None:
                    logger.debug(f"Не удалось распарсить цену из текста: {price_text}")
                    continue

                href = link.get_attribute("href")
                if not href:
                    continue
                if href.startswith("//"):
                    href = "https:" + href
                if href.startswith("/"):
                    href = urljoin(BASE_URL, href)

                candidates.append((price_val, href))
                logger.debug(f"Найдено предложение: цена {price_val}, ссылка {href}")

            except Exception as e:
                logger.debug(f"Ошибка при обработке предложения: {e}")
                continue
    except Exception as e:
        logger.error(f"Не удалось найти предложения на {hotel_url}: {e}")
        return None

    if not candidates:
        logger.warning(f"Нет доступных предложений для отеля {hotel_url}")
        return None

    candidates.sort(key=lambda x: x[0])
    chosen_price, chosen_offer_url = candidates[0]
    logger.info(f"Минимальная цена для {hotel_name}: {chosen_price}")

    logger.info(f"Переход по ссылке предложения: {chosen_offer_url}")
    driver.get(chosen_offer_url)

    try:
        browser.WebDriverWait(driver, 15).until(
            lambda d: "/book/" in d.current_url
        )
        book_url = driver.current_url
        logger.info(f"Получен book_url: {book_url}")
    except browser.TimeoutException:
        logger.warning("Автоматический переход не произошёл, ищем ссылку вручную")
        book_links = driver.find_elements(browser.By.XPATH, "//a[contains(@href, '/book/')]")
        if book_links:
            raw = book_links[0].get_attribute("href")
            if raw:
                if raw.startswith("//"):
                    raw = "https:" + raw
                if raw.startswith("/"):
                    raw = urljoin(BASE_URL, raw)
                book_url = raw
                logger.info(f"Найдена ссылка book вручную: {book_url}")
            else:
                logger.error("Не удалось получить book_url")
                return None
        else:
            logger.error("Не найдена ссылка /book/")
            return None

    details = extract_book_details(driver)
    logger.debug(f"Детали тура: {details}")

    return {
        "source_url": source_url,
        "hotel_url": hotel_url,
        "hotel_name": hotel_name,
        "departure_city": departure_city,
        "arrival_country": arrival_country,
        "price": chosen_price,
        "book_url": book_url,
        "details": details,
    }


def extract_book_details(driver) -> str:
    """Извлекает детали поездки из текста страницы бронирования."""
    text = driver.find_element(browser.By.TAG_NAME, "body").text
    parts = []
    date_match = re.search(
        r"\d{1,2}\s+(?:янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)[^\n]*-\s*\d{1,2}\s+(?:янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)[^\n]*",
        text,
        re.IGNORECASE,
    )
    nights_match = re.search(r"\d+\s+ноч", text)
    adults_match = re.search(r"\d+\s+взросл", text, re.IGNORECASE)
    meal_match = re.search(
        r"(Ультра всё включено|Всё включено|Завтрак|Полупансион)",
        text,
        re.IGNORECASE,
    )
    if date_match:
        parts.append(date_match.group(0).strip())
    if nights_match:
        parts.append(nights_match.group(0).strip())
    if meal_match:
        parts.append(meal_match.group(0).strip())
    if adults_match:
        parts.append(adults_match.group(0).strip())
    return " | ".join(parts)
