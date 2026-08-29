# Архитектура TurBox после Stage 1

Дата: 21.08.2026

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
Остаётся orchestration + Selenium OnlineTours. На Stage 1 из него убрана часть чистого parsing/URL кода.

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
Читает промежуточный двухстрочный `collection_urls.txt` без Selenium. Отдельно понимает legacy-блок `NO_RESULTS` и пропускает его целиком.

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

После живого подтверждения Stage 1:

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
