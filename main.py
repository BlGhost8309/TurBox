import logging
import sys
from pathlib import Path

from browser import init_selenium, build_driver
from io_utils import parse_config_urls, parse_config_parameters, write_results, write_json_results, get_unique_result_path
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
    logging.getLogger("parser").setLevel(logging.DEBUG)


def run():
    setup_logging()
    logger = logging.getLogger(__name__)
    init_selenium()

    urls = parse_config_urls(CONFIG_FILE)
    min_price, max_price, search_min_price_data = parse_config_parameters(CONFIG_FILE)

    logger.info(f"Параметры: min_price={min_price}, max_price={max_price}, searchMinPriceData={search_min_price_data}")
    logger.info(f"Подборки: {urls}")

    driver = build_driver()

    try:
        for collection_url in urls:
            logger.info(f"\n=== Обработка подборки: {collection_url} ===")
            departure_city, arrival_country, filtered_cards = parser.collect_hotel_links_from_collection(
                driver, collection_url, min_price, max_price, search_min_price_data
            )

            all_offers = []
            for idx, card in enumerate(filtered_cards, start=1):
                hotel_url = card["hotel_url"]
                logger.info(f"\n{idx}. Обработка отеля: {hotel_url}")
                offer_data = parser.extract_min_offer_from_hotel(
                    driver, hotel_url, departure_city, arrival_country, collection_url
                )
                if offer_data:
                    all_offers.append(ParsedOffer(**offer_data))
                logger.info("")

            unique = {}
            for o in all_offers:
                unique[(o.price, o.book_url)] = o
            final_offers = sorted(unique.values(), key=lambda x: x.price)

            result_path = get_unique_result_path(departure_city, arrival_country)
            # Сохраняем в .txt (без изменений)
            write_results(result_path, final_offers)
            # Сохраняем в .json рядом
            json_path = result_path.with_suffix('.json')
            write_json_results(json_path, final_offers)
            logger.info(f"Сохранено {len(final_offers)} предложений в {result_path} и {json_path}")

    finally:
        driver.quit()


if __name__ == "__main__":
    run()
