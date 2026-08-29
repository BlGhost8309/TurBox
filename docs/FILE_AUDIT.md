# File Audit: KEEP / REFACTOR / LEGACY

Дата: 21.08.2026

## KEEP — текущий рабочий контур

| Файл | Статус | Причина |
|---|---|---|
| `collection_url_generator.py` | KEEP + REFACTOR | Основной OnlineTours collection/hotel-mode orchestration |
| `collection_link_converter.py` | KEEP + REFACTOR | Основной affiliate orchestration |
| `link_converter.py` | KEEP | Текущий рабочий Travelpayouts Selenium adapter |
| `browser.py` | KEEP | Общая фабрика ChromeDriver |
| `query_generator.py` | KEEP | Подготовка поисковых запросов из компактного JSON |
| `run_query_generator.bat` | KEEP | Пользовательский entry point генерации запросов |
| 4 `run_collection_*.bat` | KEEP | Пользовательские entry point Selenium-конвейера |
| `configs/query_generator_config.json` | KEEP | Города, направления и шаблоны поиска |
| `configs/url_generation_config.txt` | KEEP | Рабочий collection config |
| `configs/hotel_urls.txt` | KEEP | Рабочий hotel-mode config |
| `configs/departure_cities.txt` | KEEP | Рабочий hotel-mode config |
| `configs/travelpayoutsSetup.txt` | KEEP LOCAL ONLY | Legacy credentials fallback; запрещён для Git |
| `data/travelpayouts_cookies.pkl` | KEEP LOCAL ONLY | Текущая сессия Travelpayouts; запрещена для Git |

## NEW — Stage 1 core

| Файл | Назначение |
|---|---|
| `turbox/paths.py` | Единые пути |
| `turbox/query_generation.py` | Декартово произведение + безопасное обновление рабочего TXT |
| `turbox/search_config.py` | Search config parsing + filters |
| `turbox/hotel_config.py` | Hotel-mode config/URL parsing |
| `turbox/affiliate_formatting.py` | Parsing/output/sub_id |
| `tests/*` | Unit regression tests |
| `scripts/validate_stage1.py` | Диагностика без сайтов |
| `run_stage1_checks.bat` | Удобный запуск диагностики |
| `samples/golden/*` | Контрольный успешный output |

## GENERATED — не хранить в Git

- `configs/collection_urls.txt`
- `postsCollections/*`
- `debug_logs/*`
- `data/*.pkl`
- `__pycache__/*`

Они могут оставаться локально и нужны для работы/диагностики, но не являются исходным кодом.

## LEGACY — сохранено, но не production

Копия старого `configs/query_generator.py` остаётся здесь только как историческая.
Его рабочая функция возвращена в основной контур через `query_generator.py` и
`turbox/query_generation.py`.

Перенесено в `legacy/old_pipeline/`:

- `collection_parser.py`
- `parser.py`
- `io_utils.py`
- `models.py`
- `selection_builder.py`
- `post_generator.py`
- `run_link_converter.py`
- `run_post_generator.py`
- `top_hotels_parser.py`
- `_bak` версии главных файлов
- вспомогательные старые скрипты
- старые configs/docs/logs

Перенесено в `legacy/samples/`:

- старые `posts/`;
- старые `selections/`;
- старые `results/`.

## Почему `top_hotels_parser.py` — LEGACY

Он не вызывается четырьмя текущими BAT-файлами и функционально пересекается с более зрелым HotelIQ Core. В дальнейшем правильнее сделать TurBox потребителем HotelIQ, чем поддерживать вторую независимую Selenium-реализацию TopHotels.
