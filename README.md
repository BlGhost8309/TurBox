# Парсер туров с onlinetours.ru

Скрипт для автоматического сбора предложений туров из подборок (коллекций) на сайте [onlinetours.ru](https://www.onlinetours.ru).
Отбирает отели по цене из карточки подборки, затем на странице каждого отеля находит самое дешёвое предложение, переходит к бронированию и сохраняет ссылку на тур (`/book/...`), цену и детали (даты, ночи, питание, взрослые).

## Структура проекта
- main.py – главный скрипт парсера onlinetours.
- browser.py – инициализация Selenium и вспомогательные функции.
- parser.py – логика сбора туров.
- io_utils.py – чтение конфига, запись результатов.
- models.py – dataclass ParsedOffer.
- config.txt (рекомендуется переименовать в parser_config.txt) – конфиг парсера onlinetours.
- results/ – папка с result_*.json и result_*.txt от первого парсера.
- top_hotels_parser.py – парсер рейтингов с tophotels.ru с кэшированием.
- config_global.json – общий конфиг для top_hotels_parser (TTL кэша, парсинг отзывов и т.д.).
- data/ – папка с кэшем hotel_cache.json.
- selection_builder.py – построитель подборок по фильтрам (без интернета).
- selection_config.json – конфиг подборок (фильтры, сортировка, лимит).
- selections/ – результаты подборок в JSON.
- post_generator.py – генератор черновика поста Telegram.
- post_template.txt – текстовый шаблон поста с плейсхолдерами.
- posts/ – сгенерированные текстовые посты.
- README_selection_config.txt – описание полей selection_config.json.
- README_post_template.txt – описание плейсхолдеров для шаблона поста.


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

