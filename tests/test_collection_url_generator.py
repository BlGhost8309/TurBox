import unittest
from types import SimpleNamespace
from unittest import mock

import collection_url_generator


class FakeButton:
    def __init__(self, percent):
        self.style = f"width: calc({percent}% - 2px)"
        self.clicked = False

    def get_attribute(self, name):
        return self.style if name == "style" else None


class FakeDriver:
    def __init__(self, buttons):
        self.buttons = buttons
        self.current_url = "https://example.test/tours/original"

    def find_elements(self, _by, _selector):
        return self.buttons


class ImmediateWait:
    def __init__(self, driver, _timeout, poll_frequency=None):
        self.driver = driver

    def until(self, condition):
        result = condition(self.driver)
        if not result:
            raise AssertionError("wait condition was not satisfied")
        return result


class FakeTimeoutException(Exception):
    pass


class TimeoutAfterButtonsWait(ImmediateWait):
    calls = 0

    def until(self, condition):
        type(self).calls += 1
        if type(self).calls == 2:
            raise FakeTimeoutException()
        return super().until(condition)


class SelectCheapestDateTests(unittest.TestCase):
    def _browser_patches(self, wait_class, safe_click):
        return (
            mock.patch.object(
                collection_url_generator.browser,
                "By",
                SimpleNamespace(XPATH="xpath"),
            ),
            mock.patch.object(
                collection_url_generator.browser,
                "WebDriverWait",
                wait_class,
            ),
            mock.patch.object(
                collection_url_generator.browser,
                "TimeoutException",
                FakeTimeoutException,
            ),
            mock.patch.object(
                collection_url_generator.browser,
                "_safe_click",
                safe_click,
            ),
        )

    def test_selects_minimum_percent_and_waits_for_url_change(self):
        buttons = [FakeButton(63.5), FakeButton(21.25), FakeButton(48.0)]
        driver = FakeDriver(buttons)

        def safe_click(current_driver, button):
            button.clicked = True
            current_driver.current_url = "https://example.test/tours/cheapest"

        patches = self._browser_patches(ImmediateWait, safe_click)
        with patches[0], patches[1], patches[2], patches[3], mock.patch.object(
            collection_url_generator.time, "sleep"
        ) as sleep:
            self.assertTrue(collection_url_generator.select_cheapest_date(driver))

        self.assertFalse(buttons[0].clicked)
        self.assertTrue(buttons[1].clicked)
        self.assertFalse(buttons[2].clicked)
        sleep.assert_not_called()

    def test_reports_timeout_when_click_does_not_change_url(self):
        TimeoutAfterButtonsWait.calls = 0
        driver = FakeDriver([FakeButton(21.25)])
        patches = self._browser_patches(
            TimeoutAfterButtonsWait,
            lambda _driver, button: setattr(button, "clicked", True),
        )

        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaisesRegex(
                Exception,
                "URL не изменился после выбора самой дешёвой даты",
            ):
                collection_url_generator.select_cheapest_date(driver)


if __name__ == "__main__":
    unittest.main()
