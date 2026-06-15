# TurBox — Пайплайн генерации постов для арбитража туров (обновлённая версия)

Скрипты для автоматического сбора дешёвых туров из подборок onlinetours.ru, обогащения рейтингами tophotels.ru, построения подборок по гибким фильтрам и генерации готовых текстов постов для Telegram + конвертации ссылок через Travelpayouts Tools.

**Текущая архитектура (collection pipeline)** — отличается от описания в старых частях README.

## Актуальная структура и порядок запуска (2026)

1. `configs/` — все настройки и входные данные.
2. `collection_url_generator.py` + `configs/url_generation_config.txt` — генерация/сбор URL подборок.
3. `collection_parser.py` или старый `parser.py` — парсинг отелей из подборок (с Selenium).
4. `link_converter.py` / `run_link_converter.py` + `collection_link_converter.py` — логин в Travelpayouts и конвертация book-ссылок в партнёрские (самая чувствительная часть).
5. `top_hotels_parser.py` — обогащение рейтингами и отзывами (с кэшем).
6. `selection_builder.py` + `configs/selection_config.json` — оффлайн построение финальных подборок.
7. `post_generator.py` + `run_post_generator.py` — генерация текстов постов по шаблону.
8. `browser.py`, `io_utils.py`, `models.py` — общие утилиты.

**Основные entry points для запуска:**
- `python run_link_converter.py` — интерактивный выбор постов и конвертация ссылок.
- `python run_post_generator.py` — генерация постов из selections.
- `python selection_builder.py`
- `python top_hotels_parser.py --input results/....json`
- `python collection_url_generator.py` и т.д.

Подробности по каждому скрипту — см. комментарии в коде и старые README_*.txt в корне.

## Ключевые улучшения, внесённые при ревью
- Централизованное создание драйвера в `browser.py` (поддержка `headless`, `eager`).
- Поддержка `.env` + переменных окружения для credentials (см. `.env.example`).
- `DEBUG_MODE = False` по умолчанию в конвертерах (безопасность).
- Лучшая обработка ошибок и логирование в ключевых местах.
- Обновлён `.gitignore` для секретов.

**ВАЖНО ПО БЕЗОПАСНОСТИ:**
- Никогда не коммитьте реальные пароли и `*.pkl` куки.
- Используйте `.env` (см. `.env.example`).
- После миграции на env можно удалить/заигнорить `configs/travelpayoutsSetup.txt`.

## Быстрый старт после ревью

```bash
# 1. Установи зависимости
pip install -r requirements.txt

# 2. Настрой credentials (рекомендуется)
cp .env.example .env
# отредактируй .env

# 3. Пример запуска конвертера ссылок
python run_link_converter.py

# 4. Построение подборок
python selection_builder.py

# 5. Генерация постов
python run_post_generator.py
```

Смотри комментарии в скриптах и старые `README_*.txt` для деталей конфигов.

## Что было улучшено в этом ревью (все 5 пунктов)
1. Безопасность: .env + env vars, DEBUG_MODE=False, убрано сохранение cookies в дебаг, улучшен .gitignore.
2. Обработка ошибок: убраны многие bare `except`, добавлено логирование.
3. Selenium: централизован `browser.build_driver(...)` с поддержкой headless/eager.
4. Документация: README обновлён под реальную структуру.
5. requirements.txt создан + пример .env + задел на Pydantic/undetected-chromedriver/tenacity.

Дальнейшие улучшения (по желанию): добавить tenacity для ретраев, вынести общие утилиты, строгие типы конфигов.


## Описание файлов

### `main.py`
Оркестрирует весь процесс:
- Загружает конфигурацию (`config.txt`).
- Инициализирует Selenium.
- Для каждого URL подборки получает отфильтрованные отели и обрабатывает их.
- Собирает объекты `ParsedOffer`, удаляет дубликаты, сортирует по цене.
- Сохраняет результаты в `results/result_<город вылета>.txt`.

### `browser.py`
Содержит функции для работы с Selenium:
- `init_selenium()` – динамический импорт модулей Selenium.
- `build_driver()` – создание экземпляра ChromeDriver с настройками окна и уведомлений.
- `_safe_click()` – надёжный клик с прокруткой и JS-кликом при необходимости.
- `close_popups()` – закрытие всплывающих окон (согласие, закрыть и т.д.).

### `parser.py`
Основная логика парсинга:
- `parse_price()` – извлекает число из строки с ценой (например, `"От 139 510 ₽"` → `139510`).
- `extract_departure_city()`, `extract_destination_country()` – получение города вылета и страны прибытия из полей формы.
- `collect_hotel_links_from_collection()` – загружает подборку, находит все карточки отелей по классам, читает цену из `<meta itemprop="price">`, фильтрует по `min_price`/`max_price` и возвращает список отелей для дальнейшей обработки.
- `extract_hotel_name()` – извлекает название отеля из `<h1>` или `<h2>`.
- `extract_min_offer_from_hotel()` – **ключевая функция**:
    - Заходит на страницу отеля.
    - Ждёт стабилизации цен (сравнивая с `cheapest_price` из URL, допуск 3%).
    - Находит все ссылки `/offer_groups` и парсит цены.
    - Выбирает минимальную цену, переходит по ссылке.
    - Получает итоговый URL с `/book/...`.
    - Извлекает детали (даты, ночи, питание, взрослые).
    - Если финальная цена превышает ожидаемую на >3%, добавляет предупреждение в `details`.
- `extract_book_details()` – регулярные выражения для извлечения дат, ночей, типа питания, количества взрослых.

### `io_utils.py`
Вспомогательные файловые операции:
- `parse_config_parameters()` – читает из `config.txt` блок `ПАРАМЕТРЫ` и возвращает `(min_price, max_price, searchMinPriceData)`.
- `parse_config_urls()` – читает блок `ССЫЛКИ` и возвращает список URL подборок.
- `write_results()` – записывает отсортированные предложения в текстовый файл.
- `get_unique_result_path()` – генерирует уникальное имя файла в папке `results/` (добавляет суффикс, если файл уже существует).

### `models.py`
Определяет dataclass `ParsedOffer` со следующими полями:
- `source_url` – URL подборки
- `hotel_url` – URL страницы отеля
- `hotel_name` – название отеля
- `departure_city` – город вылета
- `arrival_country` – страна назначения
- `price` – минимальная цена тура (найденная на странице отеля)
- `book_url` – ссылка на страницу бронирования (`/book/...`)
- `details` – строка с деталями (даты, ночи, питание, взрослые + возможное предупреждение)

### `config.txt`
Файл с настройками. Пример:
ПАРАМЕТРЫ
min_price=80000
max_price=160000
searchMinPriceData=true


ССЫЛКИ
https://www.onlinetours.ru/tours/2f9b5b367632faa85649905c3ddf7929?ticket_strategy=include&sort=popularity


- `min_price` и `max_price` – диапазон цен (в рублях) для фильтрации карточек на подборке.
- `searchMinPriceData` – зарезервировано на будущее (пока не используется).
- В блоке `ССЫЛКИ` – одна или несколько ссылок на подборки (каждая с новой строки).



### Парсер рейтингов TopHotels (top_hotels_parser.py)

Обогащает данные об отелях рейтингом с tophotels.ru, кэширует результат. Читает result_*.json из папки results, ищет отель на tophotels.ru, извлекает общий рейтинг (число), а также при необходимости годовые рейтинги и последние отзывы. Сохраняет в data/hotel_cache.json с ключом "название|страна". Повторные запуски используют кэш, если запись свежая (TTL задаётся в config_global.json). Запуск: python top_hotels_parser.py --input results/result_Москва-Египет.json

### Построитель подборок (selection_builder.py)

Формирует подборки туров по гибким правилам без интернета. Читает selection_config.json, который содержит массив подборок с фильтрами (цена, ночи, питание, рейтинг TopHotels и др.), сортировкой и лимитом. Обрабатывает все result_*.json по указанной маске, обогащает каждый тур рейтингом из hotel_cache.json, фильтрует, сортирует, сохраняет результат в JSON (и опционально CSV) в папку selections/. Запуск: python selection_builder.py

### Генератор поста (post_generator.py)

Создаёт текстовый черновик для Telegram на основе JSON-подборки и шаблона post_template.txt. Заменяет плейсхолдеры вида {hotel_name} на данные из туров. Результат сохраняется в папку posts/ с именем подборки. Запуск: python post_generator.py --input selections/egypt_top_rating.json

### Конфигурационные файлы

- config_global.json: настройки top_hotels_parser (TTL, включение отзывов и годовых рейтингов, таймауты).
- selection_config.json: описание подборок (см. README_selection_config.txt).
- post_template.txt: шаблон поста с плейсхолдерами (см. README_post_template.txt).

### Файлы README для конфигов

- README_selection_config.txt – подробное описание всех полей selection_config.json.
- README_post_template.txt – список всех доступных плейсхолдеров для шаблона.



## Требования и установка

- **Python 3.8+**
- **Google Chrome** (последняя версия)
- **ChromeDriver** (управляется автоматически через `webdriver-manager` – рекомендуется установить)

Установка зависимостей (выполните в терминале):
```bash
pip install selenium
# (опционально, но упрощает управление драйвером)
pip install webdriver-manager

