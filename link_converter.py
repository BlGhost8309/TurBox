#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import pickle
import time
import random
import sys
import os
import json
import argparse
import logging
from pathlib import Path
from typing import Dict, Optional

# Рекомендация: pip install python-dotenv
# Тогда можно загрузить .env автоматически:
# from dotenv import load_dotenv; load_dotenv()

# === ПРЯМЫЕ ИМПОРТЫ SELENIUM (без конфликтов с browser.py) ===
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

import browser
from browser import init_selenium, close_popups
from turbox.paths import CONFIG_DIR, DATA_DIR, DEBUG_DIR, POSTS_DIR, PROJECT_ROOT

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    # Legacy credentials file remains supported; .env loading is optional.
    pass

# === НАСТРОЙКИ ===
DEBUG_MODE = False  # ВАЖНО: False в продакшене! Включай True только при активной отладке.
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

# === ЛОГИРОВАНИЕ ===
log_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

# Консоль
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_fmt)
console_handler.setLevel(logging.INFO)

# Файл
file_handler = logging.FileHandler(DEBUG_DIR / "debug_link_converter.log", mode="w", encoding="utf-8")
file_handler.setFormatter(log_fmt)
file_handler.setLevel(logging.DEBUG)

logger = logging.getLogger("link_converter")
logger.setLevel(logging.DEBUG)
logger.addHandler(console_handler)
logger.addHandler(file_handler)

COOKIES_FILE = DATA_DIR / "travelpayouts_cookies.pkl"
CREDENTIALS_FILE = CONFIG_DIR / "travelpayoutsSetup.txt"
LOGIN_URL = "https://passport.travelpayouts.com/?client_id=b0e02fcc-0ab4-4b2c-a164-742762783a4e&response_type=code&redirect_uri=https%3A%2F%2Fapp.travelpayouts.com%2Fapi%2Fauth%2Fcallback&locale=en"
TOOLS_URL = "https://app.travelpayouts.com/tools/links/recent?source=183635"

def save_debug_pack(driver, step_name: str):
    """Сохраняет скриншот, HTML, мету и куки для отладки."""
    if not DEBUG_MODE:
        return
    try:
        ts = int(time.time())
        pack_dir = DEBUG_DIR / f"pack_{ts}_{step_name}"
        pack_dir.mkdir(exist_ok=True)

        driver.save_screenshot(pack_dir / "screenshot.png")

        with open(pack_dir / "meta.txt", "w", encoding="utf-8") as f:
            f.write(f"URL: {driver.current_url}\nTitle: {driver.title}\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        with open(pack_dir / "source_snippet.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source[:30000])

        # НЕ сохраняем куки в дебаг-паках по умолчанию (риск утечки сессии)
        # Если очень нужно — раскомментируй вручную при отладке
        # try:
        #     with open(pack_dir / "cookies.json", "w", encoding="utf-8") as f:
        #         json.dump(driver.get_cookies(), f, indent=2, ensure_ascii=False)
        # except:
        #     pass

        logger.debug(f"✓ Дебаг-пак сохранён: {pack_dir} (cookies опущены для безопасности)")
    except Exception as e:
        logger.error(f"✗ Ошибка сохранения дебаг-пака: {e}")

def _create_fast_driver():
    """Создаёт драйвер с ускоренной загрузкой страниц (eager)."""
    opts = Options()
    opts.page_load_strategy = 'eager'  # ⚡ Ждём только DOM, не ждём рекламу/метрику
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})

    driver = webdriver.Chrome(service=ChromeService(), options=opts)
    driver.implicitly_wait(0)  # Отключаем неявные ожидания, чтобы работали точные WebDriverWait
    return driver

def load_credentials() -> tuple:
    """
    Загружает учётные данные Travelpayouts.
    Приоритет:
      1. Переменные окружения (TRAVELPAYOUTS_EMAIL / PASSWORD / HUMAN_INPUT)
      2. Файл CREDENTIALS_FILE (legacy: travelpayoutsSetup.txt)
    Рекомендуется перенести данные в .env и использовать python-dotenv.
    """
    # 1. Пробуем env (лучший вариант)
    email = os.getenv("TRAVELPAYOUTS_EMAIL")
    password = os.getenv("TRAVELPAYOUTS_PASSWORD")
    human_input = os.getenv("TRAVELPAYOUTS_HUMAN_INPUT", "false").lower() == "true"

    if email and password:
        logger.debug("Credentials загружены из переменных окружения")
        return email, password, human_input

    # 2. Fallback на старый файл (для обратной совместимости)
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"Файл не найден: {CREDENTIALS_FILE}. "
            "Создайте .env по примеру .env.example или укажите TRAVELPAYOUTS_EMAIL / TRAVELPAYOUTS_PASSWORD"
        )
    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    file_email = file_password = None
    file_human = False
    for line in lines:
        low = line.lower()
        if low.startswith("email:"):
            file_email = line.split(":", 1)[1].strip()
        elif low.startswith("password:"):
            file_password = line.split(":", 1)[1].strip()
        elif low.startswith("humaninput:"):
            file_human = line.split(":", 1)[1].strip().lower() == "true"

    if not file_email or not file_password:
        raise ValueError("travelpayoutsSetup.txt должен содержать строки: Email: ... и Password: ... (или используйте env-переменные)")

    logger.warning("Используется legacy travelpayoutsSetup.txt. Рекомендуется перейти на .env + env vars.")
    return file_email, file_password, file_human

def save_cookies(driver):
    COOKIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(COOKIES_FILE, "wb") as f:
        pickle.dump(driver.get_cookies(), f)
    logger.info("Куки сохранены")

def load_cookies(driver):
    if not COOKIES_FILE.exists():
        logger.debug("Файл кук не найден")
        return False
    try:
        # 1. Сначала переходим на домен, иначе Selenium выкинет invalid cookie domain
        driver.get("https://app.travelpayouts.com")
        time.sleep(1)

        with open(COOKIES_FILE, "rb") as f:
            cookies = pickle.load(f)

        applied = 0
        for c in cookies:
            # Пропускаем истёкшие куки
            if 'expiry' in c and c['expiry'] < time.time():
                continue
            try:
                driver.add_cookie(c)
                applied += 1
            except Exception as e:
                logger.debug(f"Не удалось применить cookie: {e}")  # Игнорируем конфликты путей/доменов

        logger.debug(f"Куки: применено {applied} шт.")
        return applied > 0
    except Exception as e:
        logger.warning(f"Ошибка загрузки кук: {e}")
        return False

def human_type(element, text, min_delay=0.03, max_delay=0.07):
    """Имитация ручного ввода текста."""
    element.clear()
    for ch in text:
        element.send_keys(ch)
        time.sleep(random.uniform(min_delay, max_delay))

def _wait_tools(driver, timeout=12):
    """Ожидание элемента генерации ссылок."""
    try:
        WebDriverWait(driver, timeout, poll_frequency=0.3).until(
            EC.presence_of_element_located((By.ID, "brand-tools-link-input"))
        )
        return True
    except TimeoutException:
        return False

def _is_logged_in(driver):
    """Проверка: мы не на странице логина и видим инструмент."""
    if "passport.travelpayouts.com" in driver.current_url:
        return False
    try:
        driver.find_element(By.ID, "brand-tools-link-input")
        return True
    except Exception:
        return False

def _has_captcha(driver):
    """Проверка наличия капчи на странице."""
    src = driver.page_source.lower()
    if "captcha" in src or "recaptcha" in src:
        return True
    if driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha')]"):
        return True
    return False

def manual_login(driver):
    logger.info("Режим ручного входа...")
    driver.get(LOGIN_URL)
    WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    close_popups(driver)
    if DEBUG_MODE:
        save_debug_pack(driver, "manual_page")

    print("\n[ВНИМАНИЕ] Войдите вручную в открывшемся окне. После входа нажмите Enter...\n", flush=True)
    input()

    if _is_logged_in(driver):
        logger.info("Ручной вход OK")
        save_cookies(driver)
    else:
        logger.warning("Принудительный переход на TOOLS_URL...")
        driver.get(TOOLS_URL)
        if _wait_tools(driver, 8):
            save_cookies(driver)
        else:
            logger.error("Не удалось открыть инструменты")

def auto_login(driver, email, password, force_login=False):
    # 1. Быстрая проверка: вдруг уже залогинены
    if not force_login:
        driver.get(TOOLS_URL)
        time.sleep(2)
        if "app.travelpayouts.com" in driver.current_url:
            try:
                driver.find_element(browser.By.ID, "brand-tools-link-input")
                logger.info("Уже залогинены (без куки)")
                return
            except Exception:
                pass

    # 2. Пробуем куки
    if not force_login and load_cookies(driver):
        driver.get(TOOLS_URL)
        time.sleep(2)
        if "app.travelpayouts.com" in driver.current_url:
            try:
                driver.find_element(browser.By.ID, "brand-tools-link-input")
                logger.info("Успешный вход через куки")
                return
            except Exception:
                pass
        logger.warning("Куки протухли, логин заново")

    # 3. Автоматический логин
    logger.info("Выполняем автоматический вход...")
    driver.get(LOGIN_URL)
    browser.WebDriverWait(driver, 10).until(browser.EC.presence_of_element_located((browser.By.TAG_NAME, "body")))
    browser.close_popups(driver)

    email_input = browser.WebDriverWait(driver, 5).until(browser.EC.presence_of_element_located((browser.By.XPATH, "//input[@data-testid='email']")))
    human_type(email_input, email)
    pwd_input = driver.find_element(browser.By.XPATH, "//input[@data-testid='password']")
    human_type(pwd_input, password)
    driver.find_element(browser.By.XPATH, "//button[@data-testid='auth_form_submit']").click()
    time.sleep(1)

    # Капча
    if "captcha" in driver.page_source.lower() or driver.find_elements(browser.By.XPATH, "//iframe[contains(@src, 'recaptcha')]"):
        logger.warning("Капча! Решите и нажмите Enter.")
        print("\n[ВНИМАНИЕ] Решите капчу, затем Enter...\n", flush=True)
        input()
        print("\n[DEBUG] ✓ Enter получен. Перехожу на инструменты.\n", flush=True)
        driver.get(TOOLS_URL)
        time.sleep(2)
    else:
        # Если капчи нет, пробуем дождаться редиректа, иначе фолбэк
        try:
            browser.WebDriverWait(driver, 10).until(lambda d: "app.travelpayouts.com/tools" in d.current_url)
        except browser.TimeoutException:
            driver.get(TOOLS_URL)
            time.sleep(2)

    # Финальная проверка
    try:
        browser.WebDriverWait(driver, 15).until(browser.EC.presence_of_element_located((browser.By.ID, "brand-tools-link-input")))
        logger.info("Вход выполнен")
        save_cookies(driver)
    except browser.TimeoutException:
        logger.error("Не удалось попасть на страницу инструментов. Проверьте логин/пароль.")
        raise

def login(driver, force_login=False):
    email, password, human_input = load_credentials()
    if human_input:
        manual_login(driver)
    else:
        auto_login(driver, email, password, force_login)

def get_partner_link(driver, book_url: str, sub_id: str, cache: Dict[str, str]) -> Optional[str]:
    cache_key = f"{book_url}|{sub_id}"
    if cache_key in cache:
        return cache[cache_key]

    if driver.current_url != TOOLS_URL:
        driver.get(TOOLS_URL)

    link_input = browser.WebDriverWait(driver, 10).until(
        browser.EC.presence_of_element_located((browser.By.ID, "brand-tools-link-input"))
    )

    driver.execute_script("arguments[0].focus();", link_input)
    link_input.send_keys(browser.Keys.CONTROL + "a")
    link_input.send_keys(browser.Keys.DELETE)
    time.sleep(0.2)
    link_input.send_keys(book_url)
    time.sleep(0.3)

    sub_input = driver.find_element(browser.By.XPATH, "//input[@data-testid='autocomplete-input']")
    driver.execute_script("arguments[0].focus();", sub_input)
    sub_input.send_keys(browser.Keys.CONTROL + "a")
    sub_input.send_keys(browser.Keys.DELETE)
    time.sleep(0.2)
    if sub_id and sub_id.strip():
        sub_input.send_keys(sub_id.strip())

    generate_btn = driver.find_element(browser.By.XPATH, "//button[@data-testid='brand-tools-submit']")

    # УНИВЕРСАЛЬНЫЙ ПОДХОД: запоминаем количество ссылок до генерации
    links_before = driver.find_elements(browser.By.XPATH, "//div[@data-testid='brand-tools-link-title']")
    count_before = len(links_before)

    generate_btn.click()

    # Ждём появления НОВОЙ ссылки (не по классу строки, а по data-testid)
    try:
        browser.WebDriverWait(driver, 15).until(
            lambda d: len(d.find_elements(browser.By.XPATH, "//div[@data-testid='brand-tools-link-title']")) > count_before
        )
    except browser.TimeoutException:
        generate_btn.click()
        try:
            browser.WebDriverWait(driver, 15).until(
                lambda d: len(d.find_elements(browser.By.XPATH, "//div[@data-testid='brand-tools-link-title']")) > count_before
            )
        except browser.TimeoutException:
            logger.error(f"Нет новой ссылки для {book_url}")
            return None

    time.sleep(0.5)
    # Берём ПЕРВУЮ ссылку в списке (она будет самой свежей)
    link_divs = driver.find_elements(browser.By.XPATH, "//div[@data-testid='brand-tools-link-title']")
    if not link_divs:
        return None

    # Берём самую новую (первую в списке)
    partner_link = link_divs[0].text.strip()
    if not partner_link.startswith("http"):
        return None

    cache[cache_key] = partner_link
    logger.info(f"Ссылка: {book_url} -> {partner_link}")
    return partner_link

def process_file(file_path: Path, driver, cache: Dict[str, str]) -> None:
    logger.info(f"Обработка: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    sub_id_pattern = re.compile(r'<!-- sub_id: ([a-z0-9_]+) -->')
    matches = list(sub_id_pattern.finditer(content))
    if not matches:
        logger.warning("Нет sub_id")
        return

    pairs = []
    for i, match in enumerate(matches):
        sub_id = match.group(1)
        start_pos = match.end()
        # Ищем следующий sub_id или конец файла
        next_match = sub_id_pattern.search(content, start_pos)
        end_pos = next_match.start() if next_match else len(content)
        block = content[start_pos:end_pos]

        # ⚡ ИСПРАВЛЕНИЕ: точный матч — ровно 32 хекс-символа + граница слова
        url_match = re.search(r'https://www\.onlinetours\.ru/book/[a-f0-9]{32}(?!\S)', block)
        if url_match:
            pairs.append((sub_id, url_match.group(0)))

    if not pairs:
        logger.warning("Нет пар URL+sub_id")
        return

    # ⚡ ИСПРАВЛЕНИЕ: заменяем через re.sub с точным паттерном, а не str.replace
    new_content = content
    for sub_id, original_url in pairs:
        partner = get_partner_link(driver, original_url, sub_id, cache)
        if partner:
            # Экранируем спецсимволы в original_url для regex
            escaped_url = re.escape(original_url)
            # Заменяем только точное вхождение (с границей слова в конце)
            new_content = re.sub(rf'{escaped_url}(?!\S)', partner, new_content, count=1)
            logger.debug(f"Замена: {original_url[:50]}... -> {partner[:50]}...")

    output_file = file_path.parent / (file_path.stem + "_PARTNERS.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    logger.info(f"Сохранён: {output_file}, заменено {len(pairs)} ссылок")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input")
    parser.add_argument("--force-login", action="store_true")
    args = parser.parse_args()

    files = [Path(args.input)] if args.input else [f for f in sorted(POSTS_DIR.glob("*.txt")) if not f.stem.endswith("_PARTNERS")]
    if not files:
        return logger.error("Нет файлов")

    init_selenium()
    driver = None
    try:
        driver = browser.build_driver(eager=True)  # или browser.build_driver(headless=True) для продакшена
        logger.debug(f"Драйвер создан. URL: {driver.current_url}")
        if DEBUG_MODE:
            save_debug_pack(driver, "ready")

        login(driver, force_login=args.force_login)

        cache = {}
        for f in files:
            try:
                process_file(f, driver, cache)
            except Exception as e:
                logger.error(f"Ошибка {f}: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        if DEBUG_MODE:
            save_debug_pack(driver, "critical")
    finally:
        if driver:
            driver.quit()
        input("\nНажмите Enter для выхода...")

if __name__ == "__main__":
    main()
