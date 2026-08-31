# Актуальная архитектура TurBox

Обновлено: 31.08.2026

## 1. Рабочий production-контур

### Collection mode

```text
configs/query_generator_config.json
  -> run_query_generator.bat
     -> query_generator.py
        -> turbox.query_generation
        -> configs/url_generation_config.txt

run_collection_url_generator.bat
  -> collection_url_generator.py
     -> turbox.search_config
     -> browser.py
     -> OnlineTours
     -> configs/collection_urls.txt

run_collection_link_converter.bat
  -> collection_link_converter.py
     -> turbox.affiliate_formatting
     -> link_converter.py
        -> browser.py
        -> Travelpayouts
     -> postsCollections/collection_*.txt
```

### Hotel city mode

```text
run_collection_url_generator_hotel.bat
  -> collection_url_generator.py --hotel-mode
     -> turbox.hotel_config
     -> browser.py
     -> OnlineTours
     -> postsCollections/hotel_cities_*.txt

run_collection_link_converter_hotel.bat
  -> collection_link_converter.py --hotel-mode
     -> turbox.affiliate_formatting
     -> link_converter.py
     -> Travelpayouts
     -> postsCollections/hotel_cities_PARTNERS_*.txt
```

## 2. Границы ответственности

### `query_generator.py` / `turbox/query_generation.py`
Создают рабочие поисковые строки до запуска браузера:
- читают список шаблонов из `configs/query_generator_config.json`;
- для каждого шаблона строят декартово произведение `cities × countries`;
- заменяют только раздел `ЗАПРОСЫ` в `url_generation_config.txt`;
- сохраняют пользовательский раздел `ПАРАМЕТРЫ`;
- записывают файл атомарно, чтобы не оставить его частично обновлённым.

### `browser.py`
Единая фабрика ChromeDriver и базовые browser helpers. Все новые site-dependent компоненты должны использовать её, а не создавать ChromeDriver самостоятельно.

### `collection_url_generator.py`
Orchestration + Selenium OnlineTours:
- заполняет город, направление, даты, ночи и взрослых;
- при `searchMinPriceData=true` пытается выбрать минимальный процент;
- при недоступном графике продолжает с исходной датой и отмечает
  `CHEAPEST_DATE_UNAVAILABLE`;
- применяет URL-фильтры;
- классифицирует результат как `PRICE`, `NO_RESULTS`, `PRICE_PARSE_ERROR` или
  `REQUEST_ERROR`;
- сохраняет одну запись на каждый входной запрос;
- не останавливает пакет для ручного `Enter`;
- выводит итоговую сводку, а при технических ошибках возвращает ненулевой exit code.

### `turbox/search_config.py`
Не знает о Selenium. Отвечает за:
- секции `ПАРАМЕТРЫ` / `ЗАПРОСЫ`;
- legacy DSL;
- price/rating/meal/sort filters;
- построение query string OnlineTours.

### `turbox/hotel_config.py`
Не знает о Selenium. Отвечает за:
- URL списка отелей;
- города вылета;
- извлечение параметров тура из URL отеля.

### `turbox/collection_io.py`
Читает промежуточный двухстрочный `collection_urls.txt` без Selenium. Блоки
`NO_RESULTS`, `PRICE_PARSE_ERROR` и `REQUEST_ERROR` пропускает целиком, поэтому
они не могут быть ошибочно приняты за партнёрные URL.

### `collection_link_converter.py`
Orchestration конвертации. Читает промежуточные результаты, вызывает affiliate adapter и пишет финальный TXT.

### `turbox/affiliate_formatting.py`
Не знает о Travelpayouts UI. Отвечает за:
- транслитерацию;
- parsing строки подборки;
- формат финальной строки;
- `sub_id`;
- parsing hotel-city строки.

### `link_converter.py`
Текущий Selenium adapter Travelpayouts. В будущем это место должно быть заменяемым: Selenium adapter или API adapter.

### `turbox/paths.py`
Единая база путей. Убирает зависимость от случайного current working directory.

## 3. Почему пока не введены классы для всего

Проект небольшой и используется одним владельцем. Stage 1 сознательно не добавляет service/repository/factory слои без необходимости. Сначала выделяются реальные границы ответственности и тестируемая логика.

## 4. Целевая эволюция

Возможная дальнейшая эволюция после отдельного решения владельца:

```text
SearchRequest
  -> OnlineToursClient
  -> TourOffer[]
  -> HotelIQ enrichment
  -> DealScore
  -> AffiliateClient (API/Selenium)
  -> Telegram-ready formatter
```

`AffiliateClient` должен иметь одинаковый внешний интерфейс независимо от того, используется Travelpayouts API или браузер.

## 5. Принцип рефакторинга

Критерий каждого изменения: оно должно либо
- уменьшать зависимость от внешней вёрстки,
- делать ошибку диагностируемой,
- делать функцию тестируемой,
- либо уменьшать ручную работу пользователя.

Перемещение кода ради «красоты папок» без такой пользы не является целью.
