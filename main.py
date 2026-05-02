import logging
import sys
from pathlib import Path

from browser import init_selenium, build_driver
from io_utils import parse_config_urls, write_results, get_unique_result_path
from models import ParsedOffer
import parser

CONFIG_FILE = Path("config.txt")
LOG_FILE = Path("parser_debug.log")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8", mode="w"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def run():
    setup_logging()
    init_selenium()

    urls = parse_config_urls(CONFIG_FILE)

    driver = build_driver()

    try:
        for collection_url in urls:
            departure_city, hotel_links = parser.collect_hotel_links_from_collection(
                driver, collection_url
            )

            all_offers = []

            for hotel_url in hotel_links:
                cheapest = parser.choose_cheapest_on_hotel_page(
                    driver, hotel_url
                )

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

    finally:
        driver.quit()


if __name__ == "__main__":
    run()
