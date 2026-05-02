import re
import time
from typing import List, Optional, Tuple, Any
from urllib.parse import urljoin

import browser

BASE_URL = "https://www.onlinetours.ru"
TIMEOUT = 25


def parse_price(text: str) -> Optional[int]:
    cleaned = text.replace("\xa0", " ")
    m = re.search(r"(\d[\d ]*)\s*₽", cleaned)
    if not m:
        return None
    return int(re.sub(r"\s+", "", m.group(1)))


def extract_departure_city(driver) -> str:
    city_input = driver.find_elements(
        browser.By.XPATH,
        "//input[@id='departureCity' or @name='departureCity']",
    )
    for inp in city_input:
        try:
            val = (inp.get_attribute("value") or "").strip()
            if val:
                return val
        except Exception:
            continue
    return "Неизвестно"


def collect_hotel_links_from_collection(driver, collection_url: str):
    driver.get(collection_url)

    browser.WebDriverWait(driver, TIMEOUT).until(
        browser.EC.presence_of_element_located((browser.By.TAG_NAME, "body"))
    )

    browser.close_popups(driver)

    for _ in range(5):
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(0.7)

    departure_city = extract_departure_city(driver)

    links = driver.find_elements(
        browser.By.XPATH,
        "//a[.//span[contains(normalize-space(.), 'Выбрать')] or contains(normalize-space(.), 'Выбрать')]",
    )

    result = []
    seen = set()

    for link in links:
        href = link.get_attribute("href") or ""
        if not href:
            continue
        if href.startswith("//"):
            href = "https:" + href
        if "/oteli/" not in href:
            continue
        if href in seen:
            continue
        seen.add(href)
        result.append(href)

    return departure_city, result


def extract_hotel_name(driver, fallback_url: str) -> str:
    headers = driver.find_elements(browser.By.XPATH, "//h1|//h2")
    for h in headers:
        try:
            text = (h.text or "").strip()
            if h.is_displayed() and text and len(text) > 4:
                return text
        except Exception:
            continue

    slug = fallback_url.split("/oteli/")[-1].split("?")[0].split("/")[-1]
    return slug.replace("-", " ").title()


def extract_book_details(driver) -> str:
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


def choose_cheapest_on_hotel_page(driver, hotel_url: str):
    driver.get(hotel_url)

    browser.WebDriverWait(driver, TIMEOUT).until(
        browser.EC.presence_of_element_located((browser.By.TAG_NAME, "body"))
    )

    browser.close_popups(driver)
    time.sleep(1.0)

    hotel_name = extract_hotel_name(driver, hotel_url)

    candidates = []

    for _ in range(3):
        candidates = []
        offer_links = driver.find_elements(
            browser.By.XPATH,
            "//a[contains(@href, '/offer_groups') and contains(., '₽')]",
        )

        for node in offer_links:
            try:
                if not node.is_displayed():
                    continue

                price = parse_price(node.text)
                if price is None:
                    continue

                href = node.get_attribute("href") or ""
                if not href:
                    continue

                if href.startswith("//"):
                    href = "https:" + href
                if href.startswith("/"):
                    href = urljoin(BASE_URL, href)

                candidates.append((price, href))

            except browser.StaleElementReferenceException:
                continue

        if candidates:
            break

        time.sleep(0.5)

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    min_price, offer_groups_url = candidates[0]

    driver.get(offer_groups_url)

    browser.WebDriverWait(driver, 10).until(
        browser.EC.presence_of_element_located((browser.By.TAG_NAME, "body"))
    )

    book_url = ""

    if "/book/" in driver.current_url:
        book_url = driver.current_url

    if not book_url:
        book_links = driver.find_elements(
            browser.By.XPATH,
            "//a[contains(@href, '/book/')]",
        )
        if book_links:
            raw = book_links[0].get_attribute("href") or ""
            if raw.startswith("//"):
                raw = "https:" + raw
            if raw.startswith("/"):
                raw = urljoin(BASE_URL, raw)
            book_url = raw

    if not book_url:
        price_nodes = driver.find_elements(
            browser.By.XPATH,
            "//*[contains(., '₽')]",
        )
        local_candidates = []

        for n in price_nodes:
            try:
                if not n.is_displayed():
                    continue

                p = parse_price(n.text)
                if p is None:
                    continue

                clickable = n.find_elements(
                    browser.By.XPATH,
                    "./ancestor::button[1] | ./ancestor::a[1]",
                )
                target = clickable[0] if clickable else n

                local_candidates.append((p, target))

            except browser.StaleElementReferenceException:
                continue

        if local_candidates:
            local_candidates.sort(key=lambda x: x[0])
            browser._safe_click(driver, local_candidates[0][1])

            try:
                browser.WebDriverWait(driver, 10).until(
                    lambda d: "/book/" in d.current_url
                )
                book_url = driver.current_url
            except browser.TimeoutException:
                pass

    if not book_url:
        return None

    details = extract_book_details(driver)

    return hotel_name, min_price, book_url, details
