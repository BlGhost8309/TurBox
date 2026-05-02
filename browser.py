import importlib
from typing import Any

webdriver: Any = None
By: Any = None
Keys: Any = None
WebDriverWait: Any = None
EC: Any = None

TimeoutException: Any = None
ElementClickInterceptedException: Any = None
StaleElementReferenceException: Any = None
ElementNotInteractableException: Any = None


def init_selenium():
    global webdriver, By, Keys, WebDriverWait, EC
    global TimeoutException, ElementClickInterceptedException
    global StaleElementReferenceException, ElementNotInteractableException

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
    options.add_experimental_option(
        "prefs", {"profile.default_content_setting_values.notifications": 2}
    )

    service = importlib.import_module("selenium.webdriver.chrome.service").Service
    driver = webdriver.Chrome(service=service(), options=options)
    return driver


def _safe_click(driver, elem):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    try:
        elem.click()
    except (ElementClickInterceptedException, ElementNotInteractableException):
        try:
            driver.execute_script("arguments[0].click();", elem)
            return
        except Exception:
            pass

        parent = elem.find_elements(
            By.XPATH, "./ancestor::button[1] | ./ancestor::a[1]"
        )
        if parent:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", parent[0])
            driver.execute_script("arguments[0].click();", parent[0])
            return

        raise


def close_popups(driver):
    for xp in [
        "//button[contains(., 'Понятно') or contains(., 'Согласен') or contains(., 'Закрыть')]",
        "//button[@aria-label='Закрыть']",
    ]:
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            _safe_click(driver, btn)
        except TimeoutException:
            pass
