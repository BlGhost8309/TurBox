# HANDOFF — TurBox, состояние на 21.08.2026

Этот файл предназначен для продолжения работы в новом ChatGPT-аккаунте/чате или с другим разработчиком.

## Контекст продукта

TurBox ищет выгодные туры на OnlineTours, затем превращает обычные ссылки в партнёрские Travelpayouts и готовит материал для Telegram-канала `@turbox24`.

Идея развития: не конкурировать с крупными каналами количеством публикаций, а повышать качество автоматического отбора. В перспективе — HotelIQ enrichment, DealScore и аналитика собственной воронки через `sub_id`.

## Что реально используется

Только четыре пользовательских workflow:

1. `run_collection_url_generator.bat`
2. `run_collection_link_converter.bat`
3. `run_collection_url_generator_hotel.bat`
4. `run_collection_link_converter_hotel.bat`

Обычный pipeline:

```text
url_generation_config.txt
 -> OnlineTours Selenium
 -> collection_urls.txt
 -> Travelpayouts Selenium
 -> postsCollections/collection_*.txt
```

Hotel mode:

```text
hotel_urls.txt + departure_cities.txt
 -> OnlineTours Selenium
 -> hotel_cities_*.txt
 -> Travelpayouts Selenium
 -> hotel_cities_PARTNERS_*.txt
```

## Что сделано на Stage 1

- Старые экспериментальные файлы вынесены в `legacy/`, не удалены.
- Создан `turbox/` с чистой логикой.
- Вынесены search config, filters, hotel URL parsing, formatting и sub_id.
- Централизованы пути.
- Сохранены четыре BAT entry point.
- Добавлены 15 unit-тестов, `run_stage1_checks.bat` и два коротких live smoke BAT.
- Сохранён golden output 19.08.2026.
- Credentials/cookies исключены из новой Git-истории.
- README полностью переписан.

## Что НЕ сделано специально

- Не переписана OnlineTours Selenium-вёрстка.
- Не заменён Travelpayouts Selenium на API.
- Не заменён TXT transport на JSON.
- Не интегрирован HotelIQ.
- Не реализован DealScore.
- Не исправлена legacy-особенность диапазона даты в `sub_id`.

## Проверки разработчика

В контейнере:

- Python compile: OK;
- 15 unit tests: OK;
- текущий search config: 57 валидных запросов;
- hotel URLs: 1;
- departure cities: 14;
- найден дубликат `Екатеринбург`;
- новые pure functions сравнены с исходным `TurBox.zip`: regression comparison OK.

Live Selenium не проверялся, потому что нужен пользовательский Windows/Chrome/сессия Travelpayouts.

## Что нужно сделать следующим сообщением

Пользователь должен выполнить `docs/TEST_PLAN.md` и прислать логи/результаты.

Не начинать Stage 2, пока не подтверждён обычный live pipeline хотя бы на одном запуске.

## Следующий Stage 2 после подтверждения

Приоритет:

1. Исправить только ошибки, выявленные live-тестом.
2. Убрать самые хрупкие `sleep()` в пользу WebDriverWait.
3. Сделать явные статусы ошибок Selenium.
4. Ввести типизированные внутренние модели `SearchRequest` / `TourOffer`.
5. Перейти на JSON как внутренний формат, сохранив TXT для человека.
6. Проверить Travelpayouts API и при успехе добавить API adapter.
7. Подключить HotelIQ как отдельный сервис/ядро.
8. После накопления данных — DealScore и funnel analytics.

## Важные файлы для нового разработчика

Прочитать в порядке:

1. `README.md`
2. `docs/STAGE1_REFACTORING.md`
3. `docs/ARCHITECTURE.md`
4. `docs/TEST_PLAN.md`
5. `docs/FILE_AUDIT.md`

После этого смотреть только текущий production-контур; `legacy/` использовать как справочный архив.
