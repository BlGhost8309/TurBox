# HANDOFF — TurBox, состояние на 22.08.2026

Этот файл — главная точка входа для продолжения проекта в другом ChatGPT-аккаунте/чате или другим разработчиком.

## 1. Что это за проект

TurBox — локальный Python/Selenium-инструмент, который:

1. читает пользовательские поисковые условия;
2. открывает OnlineTours.ru;
3. формирует выдачу и при необходимости выбирает более дешёвую дату;
4. применяет фильтры цены, рейтинга и питания;
5. сохраняет найденные ссылки и цены;
6. отдельным этапом преобразует ссылки в партнёрские через Travelpayouts;
7. результат используется для Telegram-канала `@turbox24`.

Продуктовая идея на будущее: не максимальное количество туров, а автоматический отбор действительно сильных предложений. Позже для этого планируются HotelIQ enrichment, DealScore и аналитика воронки через `sub_id`.

## 2. Решение владельца проекта на момент handoff

**Следующий приоритет — OnlineTours parser (`collection_url_generator.py`).**

Не начинать следующую сессию с большого рефакторинга Travelpayouts converter. `collection_link_converter.py` уже прошёл smoke на 5 ссылках и сейчас работает достаточно хорошо для текущей задачи.

Также не начинать с HotelIQ, JSON transport или DealScore. Сначала довести скорость и устойчивость генератора OnlineTours.

## 3. Реальные пользовательские workflows

Основные BAT-файлы:

1. `run_collection_url_generator.bat`
2. `run_collection_link_converter.bat`
3. `run_collection_url_generator_hotel.bat`
4. `run_collection_link_converter_hotel.bat`

Диагностические:

- `run_stage1_checks.bat` — локальные проверки без сайтов;
- `run_smoke_collection.bat` — один OnlineTours smoke;
- `run_smoke_link_converter.bat` — одна Travelpayouts-конвертация;
- `tools/run_test_5_collection.bat` — диагностический прогон пяти первых запросов; пишет в `smoke_output/collection_urls_5.txt`. Если файл уже существует, результаты дописываются, поэтому перед чистым тестом его надо удалить/очистить.

Обычный pipeline:

```text
configs/url_generation_config.txt
 -> collection_url_generator.py / OnlineTours Selenium
 -> configs/collection_urls.txt
 -> collection_link_converter.py / Travelpayouts Selenium
 -> postsCollections/collection_*.txt
```

Hotel mode:

```text
configs/hotel_urls.txt + configs/departure_cities.txt
 -> collection_url_generator.py --hotel-mode
 -> hotel_cities_*.txt
 -> collection_link_converter.py --hotel-mode
 -> hotel_cities_PARTNERS_*.txt
```

## 4. Что было сделано на Stage 1

- Старые/экспериментальные файлы вынесены в `legacy/`, а не удалены.
- Создан пакет `turbox/` для чистой, тестируемой логики.
- Вынесены parsing search config, URL filters, hotel config, intermediate IO, форматирование и `sub_id`.
- Пути централизованы.
- Четыре привычных пользовательских BAT entry point сохранены.
- Все активные BAT переписаны в безопасный для Windows `cmd.exe` формат: ASCII + CRLF; русские строки внутри BAT убраны.
- Добавлены 15 unit-тестов без браузера.
- Сохранён golden sample успешного результата от 19.08.2026.
- Credentials/cookies исключены из новой Git-истории и из этого handoff-архива.
- README и техническая документация переписаны.

Полное описание Stage 1: `docs/STAGE1_REFACTORING.md`.

## 5. Что проверено вживую 22.08.2026

### Локальные проверки

`run_stage1_checks.bat` — успешно, 15/15 тестов.

### Travelpayouts

Smoke-конвертация на 5 ссылках прошла нормально. На момент остановки проекта converter не является главным bottleneck и специально не оптимизируется дальше.

### Полный OnlineTours generator ДО ускоряющего патча

- 57 поисковых запросов;
- все 57 дошли до сохранения;
- полный прогон: примерно 60 минут 33 секунды;
- `[ERROR]` и `Traceback` не было;
- 63 WARNING:
  - 57 раз старый алгоритм долго ждал dropdown города, затем успешно выбирал город через Enter;
  - 6 раз не удалось извлечь минимальную цену на комбинациях Кисловодск/Ессентуки для части городов.

Лог: `docs/evidence/full_generator_run_2026-08-22.log`.

### Последний патч OnlineTours parser

В актуальном `collection_url_generator.py` уже сделано:

1. Выбор города через Enter используется первым; старый dropdown оставлен fallback.
2. Часть фиксированных ожиданий заменена ожиданием состояния `PRICE / NO_RESULTS / UNKNOWN`.
3. Добавлены тайминги по этапам каждого запроса.
4. При неоднозначной проблеме с ценой предусмотрено сохранение debug snapshot/screenshot.
5. Формат `collection_urls.txt` и бизнес-логика поиска не менялись.

После этого был живой прогон пяти запросов. Время запросов:

- 41.9 s
- 45.2 s
- 40.2 s
- 44.2 s
- 42.4 s

Среднее: примерно **42.8 s/query**.

Для сравнения полный старый прогон давал около **63.7 s/query по wall-clock**. То есть уже получено примерно 33% ускорения на этом небольшом тесте.

Лог: `docs/evidence/optimized_generator_smoke_2026-08-22.log`.
Результат: `docs/evidence/optimized_generator_smoke_output_2026-08-22.txt`.

## 6. Главный найденный bottleneck

После первого ускорения самым дорогим этапом стал `cheapest_date`.

На пяти тестах он занял примерно:

- 16.6 s
- 21.6 s
- 17.8 s
- 21.9 s
- 18.5 s

Это сейчас **первое место для следующей оптимизации**.

Не надо начинать с параллельных ChromeDriver, multiprocessing или большого архитектурного переписывания. Сначала разобраться, почему поиск блока дешёвых дат ждёт 12–18 секунд до появления кнопок, и заменить оставшиеся фиксированные ожидания на проверку конкретного состояния DOM.

## 7. Вторая проблема — корректная классификация отсутствующей цены

На полном прогоне 6 запросов сохранились без цены. Проблемные комбинации:

- Нижний Новгород → Кисловодск
- Нижний Новгород → Ессентуки
- Пермь → Кисловодск
- Пермь → Ессентуки
- Самара → Кисловодск
- Самара → Ессентуки

Вероятная причина: после фильтров нет подходящих туров, но старый код не отличает это от изменения/ошибки DOM цены.

Следующая версия должна различать минимум два состояния:

```text
NO_RESULTS
PRICE_PARSE_ERROR
```

Не считать отсутствие price-element автоматически поломкой селектора и не считать автоматически отсутствием туров. Использовать сохранённый HTML/screenshot и явные признаки страницы.

## 8. Что НЕ сделано специально

- Travelpayouts Selenium не заменён на API.
- TXT internal transport не заменён на JSON.
- HotelIQ не интегрирован.
- DealScore не реализован.
- Не исправлена legacy-особенность диапазона даты в `sub_id`.
- Не удалён повтор `Екатеринбург` из `configs/departure_cities.txt`.
- Hotel-mode после Stage 1 ещё не прошёл полноценную живую приёмку.

## 9. Travelpayouts API — отложенная задача

Ранее проверялась возможность позже уйти от Selenium-конвертации на официальный Travelpayouts Partner Links API. Это **не нужно делать первым делом**.

Текущая архитектура специально оставляет converter отдельным слоем, чтобы позже добавить API adapter без переделки OnlineTours pipeline.

При будущей работе с API не просить владельца присылать API token в чат; использовать локальную `.env`.

## 10. HotelIQ — будущая интеграция

В TurBox есть старый historical TopHotels parser в `legacy/`. Его не надо развивать.

Правильное направление позже:

```text
TurBox OnlineTours offers
        ↓
HotelIQ Core API
        ↓
качество/аналитика отеля
        ↓
DealScore / публикация
```

HotelIQ должен оставаться отдельным сервисом/ядром, а TurBox — его клиентом.

## 11. Безопасность и локальные секреты

Этот архив намеренно НЕ содержит:

- `configs/travelpayoutsSetup.txt` с реальными credentials;
- `data/travelpayouts_cookies.pkl`;
- `.env` с секретами;
- рабочие `postsCollections/`;
- основной runtime `configs/collection_urls.txt`.

Есть только example-файлы.

На рабочем ПК владельца эти локальные данные надо сохранить отдельно. Не коммитить их в Git.

## 12. Что читать новому аккаунту/разработчику

В таком порядке:

1. `START_HERE_NEW_ACCOUNT.md`
2. `HANDOFF.md` — этот файл
3. `README.md`
4. `docs/NEXT_STEPS.md`
5. `docs/TEST_RESULTS_2026-08-22.md`
6. `docs/ARCHITECTURE.md`
7. `docs/STAGE1_REFACTORING.md`
8. `docs/CODE_REVIEW.md`

После этого смотреть актуальный `collection_url_generator.py`. В `legacy/` заходить только за исторической справкой.

## 13. Правильная первая задача следующей сессии

Не задавать владельцу заново вопросы про архитектуру проекта. Контекст уже здесь.

Первая техническая задача:

> Проанализировать `cheapest_date` в актуальном `collection_url_generator.py` и лог `docs/evidence/optimized_generator_smoke_2026-08-22.log`. Предложить и реализовать минимальный безопасный патч, уменьшающий 16–22 секунд ожидания этого этапа без изменения результата поиска. Затем проверить 5 запросов, сравнить тайминги и только после этого решать, нужен ли полный прогон.

Если одновременно получится воспроизвести один из шести случаев без цены — использовать debug snapshot для введения корректных `NO_RESULTS` / `PRICE_PARSE_ERROR`.
