from __future__ import annotations

import importlib
import importlib.util
import logging
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple
from urllib.parse import urljoin

BASE_URL = "https://www.onlinetours.ru"
CONFIG_FILE = Path("config.txt")
RESULTS_FILE = Path("results.txt")
RESULTS_DIR = Path("results")
LOG_FILE = Path("parser_debug.log")
TIMEOUT = 25

webdriver: Any = None
By: Any = None
Keys: Any = None
WebDriverWait: Any = None
EC: Any = None
TimeoutException: Any = None
ElementClickInterceptedException: Any = None
StaleElementReferenceException: Any = None
ElementNotInteractableException: Any = None


@dataclass
class ParsedOffer:
    source_url: str
    hotel_url: str
    hotel_name: str
    departure_city: str
    price: int
    book_url: str
    details: str


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8", mode="w"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("=== Старт парсера подборок ===")
    logging.info("Лог пишется в %s", LOG_FILE.resolve())


def ensure_selenium_available() -> None:
    if importlib.util.find_spec("selenium") is not None:
        return
    logging.warning("selenium не найден. Пробую установить автоматически...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "selenium"], capture_output=True, text=True)
    if result.returncode != 0:
        logging.error("Автоустановка selenium не удалась.\n%s\n%s", result.stdout, result.stderr)
        raise RuntimeError("Не удалось установить selenium")


def init_selenium() -> None:
    global webdriver, By, Keys, WebDriverWait, EC, TimeoutException, ElementClickInterceptedException
    global StaleElementReferenceException, ElementNotInteractableException
    ensure_selenium_available()

    webdriver = importlib.import_module("selenium.webdriver")
    By = importlib.import_module("selenium.webdriver.common.by").By
    Keys = importlib.import_module("selenium.webdriver.common.keys").Keys
    WebDriverWait = importlib.import_module("selenium.webdriver.support.ui").WebDriverWait
    EC = importlib.import_module("selenium.webdriver.support.expected_conditions")
    exceptions = importlib.import_module("selenium.common.exceptions")
    TimeoutException = exceptions.TimeoutException
    ElementClickInterceptedException = exceptions.ElementClickInterceptedException
    StaleElementReferenceException = exceptions.StaleElementReferenceException
    ElementNotInteractableException = exceptions.ElementNotInteractableException


def build_driver():
    options = importlib.import_module("selenium.webdriver").ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})

    service = importlib.import_module("selenium.webdriver.chrome.service").Service
    driver = webdriver.Chrome(service=service(), options=options)
    return driver


def parse_config_urls(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Не найден {path}")
    urls: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            urls.append(line)
    if not urls:
        raise ValueError("В config.txt не найдено ни одной ссылки")
    return urls


def parse_price(text: str) -> Optional[int]:
    cleaned = text.replace("\xa0", " ")
    m = re.search(r"(\d[\d ]*)\s*₽", cleaned)
    if not m:
        return None
    return int(re.sub(r"\s+", "", m.group(1)))


def _safe_click(driver, elem) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    try:
        elem.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        try:
            driver.execute_script("arguments[0].click();", elem)
            return
        except Exception:
            pass

        # Фолбэк: кликаем по ближайшему кликабельному предку.
        parent = elem.find_elements(By.XPATH, "./ancestor::button[1] | ./ancestor::a[1]")
        if parent:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", parent[0])
            driver.execute_script("arguments[0].click();", parent[0])
            return
        raise


def close_popups(driver) -> None:
    for xp in [
        "//button[contains(., 'Понятно') or contains(., 'Согласен') or contains(., 'Закрыть')]",
        "//button[@aria-label='Закрыть']",
    ]:
        try:
            btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.XPATH, xp)))
            _safe_click(driver, btn)
        except TimeoutException:
            pass


def collect_hotel_links_from_collection(driver, collection_url: str) -> List[str]:
    driver.get(collection_url)
    WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    close_popups(driver)

    # Прокрутка для подгрузки карточек.
    for _ in range(5):
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(0.7)

    departure_city = extract_departure_city(driver)
    logging.info("Подборка %s: город вылета '%s'", collection_url, departure_city)

    links = driver.find_elements(
        By.XPATH,
        "//a[.//span[contains(normalize-space(.), 'Выбрать')] or contains(normalize-space(.), 'Выбрать')]",
    )

    result: List[str] = []
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

    logging.info("Подборка %s: найдено кнопок/ссылок 'Выбрать': %s", collection_url, len(result))
    return departure_city, result


def extract_departure_city(driver) -> str:
    city_input = driver.find_elements(By.XPATH, "//input[@id='departureCity' or @name='departureCity']")
    for inp in city_input:
        try:
            val = (inp.get_attribute("value") or "").strip()
            if val:
                return val
        except Exception:
            continue
    return "Неизвестно"


def choose_cheapest_on_hotel_page(driver, hotel_url: str) -> Optional[Tuple[str, int, str, str]]:
    driver.get(hotel_url)
    WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    close_popups(driver)
    time.sleep(1.0)
    hotel_name = extract_hotel_name(driver, hotel_url)

    candidates: List[Tuple[int, str]] = []
    for attempt in range(1, 4):
        candidates = []
        offer_links = driver.find_elements(
            By.XPATH,
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
            except StaleElementReferenceException:
                continue

        if candidates:
            break
        logging.warning("Повторный сбор цен из-за stale элементов (%s/3): %s", attempt, hotel_url)
        time.sleep(0.5)

    if not candidates:
        logging.warning("На странице отеля не найдены варианты цен: %s", hotel_url)
        return None

    candidates.sort(key=lambda x: x[0])
    min_price, offer_groups_url = candidates[0]
    logging.info("%s -> минимальная найденная цена: %s", hotel_url, min_price)

    driver.get(offer_groups_url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    book_url = ""
    if "/book/" in driver.current_url:
        book_url = driver.current_url

    if not book_url:
        # Последняя попытка: найти ссылки book на странице.
        book_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/book/')]")
        if book_links:
            raw = book_links[0].get_attribute("href") or ""
            if raw.startswith("//"):
                raw = "https:" + raw
            if raw.startswith("/"):
                raw = urljoin(BASE_URL, raw)
            book_url = raw

    if not book_url:
        # Фолбэк: клик по минимальной цене уже на странице offer_groups.
        price_nodes = driver.find_elements(By.XPATH, "//*[contains(., '₽')]")
        local_candidates: List[Tuple[int, Any]] = []
        for n in price_nodes:
            try:
                if not n.is_displayed():
                    continue
                p = parse_price(n.text)
                if p is None:
                    continue
                clickable = n.find_elements(By.XPATH, "./ancestor::button[1] | ./ancestor::a[1]")
                target = clickable[0] if clickable else n
                local_candidates.append((p, target))
            except StaleElementReferenceException:
                continue
        if local_candidates:
            local_candidates.sort(key=lambda x: x[0])
            _safe_click(driver, local_candidates[0][1])
            try:
                WebDriverWait(driver, 10).until(lambda d: "/book/" in d.current_url)
                book_url = driver.current_url
            except TimeoutException:
                pass

    if not book_url:
        logging.warning("Не удалось получить ссылку /book/ для отеля: %s", hotel_url)
        return None

    details = extract_book_details(driver)
    return hotel_name, min_price, book_url, details


def extract_hotel_name(driver, fallback_url: str) -> str:
    headers = driver.find_elements(By.XPATH, "//h1|//h2")
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
    text = driver.find_element(By.TAG_NAME, "body").text
    parts: List[str] = []

    date_match = re.search(
        r"\d{1,2}\s+(?:янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)[^\\n]*-\\s*\\d{1,2}\s+(?:янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)[^\\n]*",
        text,
        flags=re.IGNORECASE,
    )
    nights_match = re.search(r"\d+\s+ноч", text)
    adults_match = re.search(r"\d+\s+взросл", text, flags=re.IGNORECASE)
    meal_match = re.search(r"(Ультра всё включено|Всё включено|Завтрак|Полупансион)", text, flags=re.IGNORECASE)

    if date_match:
        parts.append(date_match.group(0).strip())
    if nights_match:
        parts.append(nights_match.group(0).strip())
    if meal_match:
        parts.append(meal_match.group(0).strip())
    if adults_match:
        parts.append(adults_match.group(0).strip())

    return " | ".join(parts)


def write_results(path: Path, offers: List[ParsedOffer]) -> None:
    offers = sorted(offers, key=lambda x: x.price)
    lines: List[str] = []
    for o in offers:
        lines.append(f"{o.hotel_name} (город вылета - {o.departure_city})")
        lines.append(f"{o.price} — {o.book_url} — {o.details}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _safe_filename(text: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]+', "_", text).strip()
    return safe or "Неизвестно"


def get_unique_result_path(city: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    base = _safe_filename(city)
    candidate = RESULTS_DIR / f"result_{base}.txt"
    if not candidate.exists():
        return candidate
    idx = 2
    while True:
        candidate = RESULTS_DIR / f"result_{base}_{idx}.txt"
        if not candidate.exists():
            return candidate
        idx += 1


def run() -> None:
    setup_logging()
    init_selenium()
    urls = parse_config_urls(CONFIG_FILE)
    logging.info("В config.txt найдено подборок: %s", len(urls))

    driver = build_driver()
    try:
        for collection_url in urls:
            departure_city, hotel_links = collect_hotel_links_from_collection(driver, collection_url)
            all_offers: List[ParsedOffer] = []
            for hotel_url in hotel_links:
                cheapest = choose_cheapest_on_hotel_page(driver, hotel_url)
                if cheapest is None:
                    continue
                hotel_name, price, book_url, details = cheapest
                all_offers.append(
                    ParsedOffer(
                        source_url=collection_url,
                        hotel_url=hotel_url,
                        hotel_name=hotel_name,
                        departure_city=departure_city,
                        price=price,
                        book_url=book_url,
                        details=details,
                    )
                )

            unique = {}
            for offer in all_offers:
                unique[(offer.price, offer.book_url)] = offer
            final_offers = sorted(unique.values(), key=lambda x: x.price)
            result_path = get_unique_result_path(departure_city)
            write_results(result_path, final_offers)
            logging.info("Сохранено ссылок: %s в %s", len(final_offers), result_path.resolve())
    finally:
        driver.quit()


def pause_console() -> None:
    try:
        input("\nНажмите Enter для выхода...")
    except EOFError:
        pass


def main() -> int:
    try:
        run()
        return 0
    except Exception:
        logging.exception("Скрипт завершился с ошибкой")
        print(f"\n[ERROR] Подробный лог: {LOG_FILE.resolve()}")
        return 1
    finally:
        pause_console()


if __name__ == "__main__":
    raise SystemExit(main())



