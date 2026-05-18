import logging
import sys
from pathlib import Path

from browser import init_selenium, build_driver
from io_utils import read_collection_params, read_collection_urls, write_results, write_json_results, get_unique_result_path
from models import ParsedOffer
import parser

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

    # Чтение параметров и URL из новых конфигурационных файлов
    min_price, max_price, search_min_price_data, hotel_num = read_collection_params()
    urls = read_collection_urls()

    if not urls:
        logger.error("Не найдено ни одной ссылки в configs/collection_urls.txt. Завершение.")
        return

    logger.info(f"Используем параметры из configs/collection_params.txt: min_price={min_price}, max_price={max_price}, searchMinPriceData={search_min_price_data}, hotelNum={hotel_num}")
    logger.info(f"URL подборок из configs/collection_urls.txt: найдено {len(urls)} ссылок")
    for i, url in enumerate(urls, 1):
        logger.info(f"  {i}. {url}")

    driver = build_driver()

    try:
        for idx, collection_url in enumerate(urls, start=1):
            logger.info(f"\n=== [{idx}/{len(urls)}] Обработка подборки: {collection_url} ===")
            try:
                departure_city, arrival_country, filtered_cards = parser.collect_hotel_links_from_collection(
                    driver, collection_url, min_price, max_price, search_min_price_data, hotel_num
                )

                all_offers = []
                for hotel_idx, card in enumerate(filtered_cards, start=1):
                    hotel_url = card["hotel_url"]
                    logger.info(f"\n{hotel_idx}. Обработка отеля: {hotel_url}")
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

                # Не сохраняем, если нет предложений
                if not final_offers:
                    logger.warning(f"Подборка {idx} не содержит подходящих туров. Файл не создан.")
                else:
                    result_path = get_unique_result_path(departure_city, arrival_country)
                    write_results(result_path, final_offers)
                    write_json_results(result_path, final_offers)
                    logger.info(f"Подборка {idx} обработана успешно. Сохранено {len(final_offers)} предложений в {result_path} и JSON")

            except Exception as e:
                logger.error(f"Ошибка при обработке подборки {idx}: {e}", exc_info=True)
                logger.info("Пропускаем эту подборку и продолжаем со следующей...")
                continue

    finally:
        driver.quit()
        logger.info("Работа завершена, драйвер закрыт.")


if __name__ == "__main__":
    run()
