import tempfile
import unittest
from pathlib import Path
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


class AlwaysTimeoutWait(ImmediateWait):
    def until(self, condition):
        raise FakeTimeoutException()


class FalseThenTimeoutWait(ImmediateWait):
    def until(self, condition):
        if condition(self.driver) is not False:
            raise AssertionError("intermediate state should keep waiting")
        raise FakeTimeoutException()


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
            self.assertEqual(
                collection_url_generator.select_cheapest_date(driver),
                collection_url_generator.CHEAPEST_DATE_SELECTED,
            )

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
            self.assertEqual(
                collection_url_generator.select_cheapest_date(driver),
                collection_url_generator.CHEAPEST_DATE_UNAVAILABLE,
            )

    def test_missing_percentage_chart_falls_back_to_original_date(self):
        driver = FakeDriver([])
        patches = self._browser_patches(AlwaysTimeoutWait, mock.Mock())

        with patches[0], patches[1], patches[2], patches[3]:
            self.assertEqual(
                collection_url_generator.select_cheapest_date(driver),
                collection_url_generator.CHEAPEST_DATE_UNAVAILABLE,
            )


class CollectionMainTests(unittest.TestCase):
    CONFIG_TEXT = """ПАРАМЕТРЫ
searchMinPriceData=true

ЗАПРОСЫ
Самара|Сочи|23.09.2026|ночей:7|взрослых:2|цена:30000-75000|рейтинг:5|питание:()|сортировка:цена
"""

    def test_request_error_is_saved_without_manual_pause(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.txt"
            output_path = temp_path / "results.txt"
            config_path.write_text(self.CONFIG_TEXT, encoding="utf-8")

            with mock.patch.object(
                collection_url_generator,
                "fill_form_and_get_url",
                return_value=None,
            ), mock.patch("builtins.input") as user_input:
                exit_code = collection_url_generator.main(config_path, output_path)

            output = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 2)
        self.assertIn("REQUEST_ERROR", output)
        user_input.assert_not_called()

    def test_cheapest_date_fallback_is_a_successful_price_result(self):
        result = {
            "url": "https://example.test/tours/original?price_to=75000",
            "extra_info": "Новая дата 23 сен - 30 сен | от 55000",
            "status": collection_url_generator.PRICE,
            "cheapest_date_status": collection_url_generator.CHEAPEST_DATE_UNAVAILABLE,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "config.txt"
            output_path = temp_path / "results.txt"
            config_path.write_text(self.CONFIG_TEXT, encoding="utf-8")

            with mock.patch.object(
                collection_url_generator,
                "fill_form_and_get_url",
                return_value=result,
            ):
                exit_code = collection_url_generator.main(config_path, output_path)

            output = output_path.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("https://example.test/tours/original", output)
        self.assertNotIn("CHEAPEST_DATE_UNAVAILABLE", output)


class PriceStateTests(unittest.TestCase):
    def _state(
        self,
        *,
        no_results=False,
        price=False,
        cards=False,
        parsed_price=50000,
        price_min=None,
        price_max=None,
        wait=ImmediateWait,
    ):
        driver = object()
        with mock.patch.object(
            collection_url_generator, "_has_no_results", return_value=no_results
        ), mock.patch.object(
            collection_url_generator, "_has_price", return_value=price
        ), mock.patch.object(
            collection_url_generator, "_has_tour_cards", return_value=cards
        ), mock.patch.object(
            collection_url_generator,
            "extract_min_price",
            return_value=parsed_price,
        ), mock.patch.object(
            collection_url_generator.browser, "WebDriverWait", wait
        ), mock.patch.object(
            collection_url_generator.browser,
            "TimeoutException",
            FakeTimeoutException,
        ):
            return collection_url_generator.wait_price_or_no_results(
                driver,
                price_min=price_min,
                price_max=price_max,
            )

    def test_explicit_no_results_wins_over_other_signals(self):
        self.assertEqual(
            self._state(no_results=True, price=True, cards=True),
            collection_url_generator.NO_RESULTS,
        )

    def test_price_element_is_price(self):
        self.assertEqual(
            self._state(
                price=True,
                cards=True,
                parsed_price=77009,
                price_min=40000,
                price_max=120000,
            ),
            collection_url_generator.PRICE,
        )

    def test_loaded_cards_without_price_element_are_parse_error(self):
        self.assertEqual(
            self._state(cards=True),
            collection_url_generator.PRICE_PARSE_ERROR,
        )

    def test_timeout_is_parse_error_not_no_results(self):
        self.assertEqual(
            self._state(wait=AlwaysTimeoutWait),
            collection_url_generator.PRICE_PARSE_ERROR,
        )

    def test_price_outside_filter_is_not_accepted_as_loaded_state(self):
        self.assertEqual(
            self._state(
                price=True,
                parsed_price=111264,
                price_max=75000,
                wait=FalseThenTimeoutWait,
            ),
            collection_url_generator.PRICE_PARSE_ERROR,
        )

    def test_debug_snapshot_prefers_body_html(self):
        driver = SimpleNamespace(
            execute_script=lambda _script: "<body><main>results</main></body>",
            page_source="<html><head>large scripts</head></html>",
        )
        self.assertEqual(
            collection_url_generator._get_debug_html_snippet(driver),
            "<body><main>results</main></body>",
        )


if __name__ == "__main__":
    unittest.main()
