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
    cleaned = text.replace("\xa0", "").replace(" ", "")
    m = re.search(r"(\d+)\s*₽", cleaned)
    if not m:
        m = re.search(r"(\d+)", cleaned)
    return int(m.group(1)) if m else None


def extract_departure_city(driver) -> str:
    for inp in driver.find_elements(browser.By.XPATH, "//input[@id='departureCity' or @name='departureCity']"):
        try:
            val = (inp.get_attribute("value") or "").strip()
            if val:
                return val
        except Exception:
            continue
    return "Неизвестно"


def extract_destination_country(driver) -> str:
    try:
        el = driver.find_element(browser.By.ID, "destination")
        value = el.get_attribute("value") or ""
        return value.split(",")[0].strip() if value else "Неизвестно"
    except Exception:
        return "Неизвестно"


def extract_hotel_rating_and_stars(driver) -> Tuple[float, int]:
    rating = 0.0
    stars = 0
    try:
        container = browser.WebDriverWait(driver, 5).until(
            browser.EC.presence_of_element_located((browser.By.XPATH, "//div[@itemprop='aggregateRating']"))
        )
        rating_elem = container.find_element(browser.By.XPATH, ".//span[@itemprop='ratingValue']")
        rating_text = rating_elem.get_attribute("content") or rating_elem.text
        rating = float(rating_text)
        logger.debug(f"Найден рейтинг: {rating}")

        html = container.get_attribute("outerHTML")
        stars = html.count('href="#icon-StarFilled"')
        logger.debug(f"Найдено звёзд: {stars}")
    except Exception as e:
        logger.debug(f"Не удалось извлечь рейтинг/звёзды: {e}")
    return rating, stars


def extract_booking_details(driver) -> Dict[str, Any]:
    """
    Извлекает детали бронирования со страницы /book/
    Возвращает словарь с ключами:
        departure_date, return_date, nights, meal_type, adults
    """
    text = driver.find_element(browser.By.TAG_NAME, "body").text
    result = {
        "departure_date": "",
        "return_date": "",
        "nights": 0,
        "meal_type": "",
        "adults": 0,
    }

    # Диапазон дат
    date_match = re.search(
        r"(\d{1,2}\s+(?:янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)[^\n]*?)\s*-\s*(\d{1,2}\s+(?:янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)[^\n]*)",
        text,
        re.IGNORECASE,
    )
    if date_match:
        result["departure_date"] = date_match.group(1).strip()
        result["return_date"] = date_match.group(2).strip()
        logger.debug(f"Даты: {result['departure_date']} — {result['return_date']}")
    else:
        logger.warning("Не удалось найти диапазон дат на странице /book/")

    # Количество ночей
    nights_match = re.search(r"(\d+)\s+ноч", text)
    if nights_match:
        result["nights"] = int(nights_match.group(1))
        logger.debug(f"Ночей: {result['nights']}")
    else:
        logger.warning("Не удалось найти количество ночей")

    # Тип питания
    meal_match = re.search(
        r"(Ультра всё включено|Всё включено|Завтрак|Полупансион)",
        text,
        re.IGNORECASE,
    )
    if meal_match:
        result["meal_type"] = meal_match.group(1)
        logger.debug(f"Питание: {result['meal_type']}")
    else:
        logger.warning("Не удалось найти тип питания")

    # Количество взрослых
    adults_match = re.search(r"(\d+)\s+взросл", text, re.IGNORECASE)
    if adults_match:
        result["adults"] = int(adults_match.group(1))
        logger.debug(f"Взрослых: {result['adults']}")
    else:
        logger.warning("Не удалось найти количество взрослых")

    return result


def select_cheapest_date(driver, timeout=30) -> bool:
    logger.info("Поиск блока с датами для выбора самой дешёвой даты...")
    container = None
    try:
        container = browser.WebDriverWait(driver, timeout).until(
            browser.EC.presence_of_element_located((browser.By.ID, "PriceChartSwiperContainer_11"))
        )
        logger.info("Найден контейнер по ID 'PriceChartSwiperContainer_11'")
    except browser.TimeoutException:
        logger.warning("Контейнер по ID не найден, пробуем найти по классу 'swiper-wrapper'")
        try:
            container = browser.WebDriverWait(driver, timeout).until(
                browser.EC.presence_of_element_located((browser.By.XPATH, "//div[contains(@class, 'swiper-wrapper')]"))
            )
            logger.info("Найден контейнер по классу 'swiper-wrapper'")
        except browser.TimeoutException:
            raise Exception("Не удалось найти блок выбора дат ни по ID, ни по классу")

    buttons = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        buttons = container.find_elements(browser.By.XPATH, ".//button[contains(@style, 'calc(')]")
        if buttons:
            logger.info(f"Найдено {len(buttons)} кнопок с процентами")
            break
        time.sleep(0.5)

    if not buttons:
        all_buttons = container.find_elements(browser.By.XPATH, ".//button")
        logger.debug(f"Всего кнопок в контейнере: {len(all_buttons)}")
        for idx, btn in enumerate(all_buttons[:5]):
            style = btn.get_attribute("style")
            logger.debug(f"Кнопка {idx}: style={style}")
        raise Exception(f"Не найдено кнопок с процентами за {timeout} секунд. Всего кнопок: {len(all_buttons)}")

    candidates = []
    for btn in buttons:
        style = btn.get_attribute("style") or ""
        match = re.search(r'calc\(([\d\.]+)%', style)
        if match:
            percent = float(match.group(1))
            candidates.append((percent, btn))
            logger.debug(f"Найдена кнопка с процентом {percent}")
        else:
            logger.debug("Кнопка без процента (игнорируем)")

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


def collect_hotel_links_from_collection(
    driver, collection_url: str, min_price: int, max_price: int, search_min_price_data: bool = False, hotel_num: int = 0
) -> Tuple[str, str, List[Dict[str, Any]]]:
    logger.info(f"Загрузка подборки: {collection_url}")
    driver.get(collection_url)
    browser.WebDriverWait(driver, TIMEOUT).until(
        browser.EC.presence_of_element_located((browser.By.TAG_NAME, "body"))
    )
    browser.close_popups(driver)

    if search_min_price_data:
        try:
            select_cheapest_date(driver)
        except Exception as e:
            logger.error(f"Не удалось выбрать самую дешёвую дату: {e}")
            raise RuntimeError(f"Ошибка выбора даты: {e}") from e

    for _ in range(5):
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(0.7)

    departure_city = extract_departure_city(driver)
    destination_country = extract_destination_country(driver)
    logger.info(f"Город вылета: {departure_city}, Страна: {destination_country}")

    cards = driver.find_elements(
        browser.By.XPATH,
        "//li[contains(@class, 'flex flex-col rounded-4xl') and contains(@class, 'bg-white')]"
    )
    logger.info(f"Найдено карточек в подборке: {len(cards)}")

    filtered = []
    for card in cards:
        try:
            price_meta = card.find_element(browser.By.XPATH, ".//meta[@itemprop='price']")
            price = int(price_meta.get_attribute("content"))
            logger.debug(f"Цена из карточки: {price}")

            hotel_link = card.find_element(browser.By.XPATH, ".//a[contains(@href, '/oteli/')]")
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

    if hotel_num > 0 and len(filtered) > hotel_num:
        filtered = filtered[:hotel_num]
        logger.info(f"Ограничение hotelNum={hotel_num}: оставлено {len(filtered)} отелей")

    logger.info(f"Отобрано отелей по цене: {len(filtered)}")
    return departure_city, destination_country, filtered


def extract_hotel_name(driver, fallback_url: str) -> str:
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

    # Извлечение рейтинга и звёзд
    rating, stars = extract_hotel_rating_and_stars(driver)

    match = re.search(r'cheapest_price=(\d+)', hotel_url)
    expected_price = int(match.group(1)) if match else None
    tolerance = 0.03
    price_warning = None

    if expected_price:
        logger.debug(f"Ожидаемая минимальная цена из URL: {expected_price}")
        logger.info("Ожидание загрузки реальных цен (до 20 сек)...")
        start_time = time.time()
        while time.time() - start_time < 20:
            links = driver.find_elements(browser.By.XPATH, "//a[contains(@href, '/offer_groups')]")
            if links:
                found = False
                for link in links:
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
            logger.warning(f"Не удалось дождаться цен в пределах {tolerance*100}% от {expected_price} за 20 секунд, продолжаем с текущими")
    else:
        time.sleep(3)

    time.sleep(0.5)

    hotel_name = extract_hotel_name(driver, hotel_url)
    logger.debug(f"Название отеля: {hotel_name}")

    candidates = []
    try:
        offer_links = driver.find_elements(browser.By.XPATH, "//a[contains(@href, '/offer_groups')]")
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

    if expected_price and chosen_price > expected_price * (1 + tolerance):
        price_warning = f"⚠️ Изначально цена была {expected_price}, надо перепроверить"
        logger.warning(price_warning)

    logger.info(f"Переход по ссылке предложения: {chosen_offer_url}")
    driver.get(chosen_offer_url)

    try:
        browser.WebDriverWait(driver, 15).until(lambda d: "/book/" in d.current_url)
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

    # Извлекаем детали бронирования со страницы /book/
    booking_details = extract_booking_details(driver)

    # Формируем строку details для обратной совместимости
    details_parts = []
    if booking_details["departure_date"] and booking_details["return_date"]:
        details_parts.append(f"{booking_details['departure_date']} - {booking_details['return_date']}")
    if booking_details["nights"]:
        details_parts.append(f"{booking_details['nights']} ноч")
    if booking_details["meal_type"]:
        details_parts.append(booking_details["meal_type"])
    if booking_details["adults"]:
        details_parts.append(f"{booking_details['adults']} взросл")
    details_str = " | ".join(details_parts)

    if price_warning:
        details_str = f"{details_str} {price_warning}" if details_str else price_warning

    logger.debug(f"Детали тура: {details_str}")

    # Очищаем hotel_url от query-параметров
    clean_hotel_url = hotel_url.split('?')[0]

    return {
        "source_url": source_url,
        "hotel_url": clean_hotel_url,
        "hotel_name": hotel_name,
        "departure_city": departure_city,
        "arrival_country": arrival_country,
        "price": chosen_price,
        "book_url": book_url,
        "details": details_str,
        "rating": rating,
        "stars": stars,
        "nights": booking_details["nights"],
        "meal_type": booking_details["meal_type"],
        "adults": booking_details["adults"],
        "departure_date": booking_details["departure_date"],
        "return_date": booking_details["return_date"],
    }
