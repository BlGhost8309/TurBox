# TurBox

TurBox — локальный Python-инструмент для поиска туристических офферов на OnlineTours и преобразования найденных ссылок в партнёрские ссылки Travelpayouts для публикации в Telegram-канале.

**Текущий статус:** `Stage 1 refactoring`, 21.08.2026.  
Главная цель этого этапа — привести рабочий прототип в понятное и безопасно сопровождаемое состояние **без переписывания работающей Selenium-логики OnlineTours и Travelpayouts**.

---

## Самое важное: что запускать

В ежедневной работе используются четыре BAT-файла в корне проекта.

### 1. Обычный поиск подборок

1. Настроить:
   `configs/url_generation_config.txt`
2. Запустить:
   `run_collection_url_generator.bat`
3. Получить промежуточный файл:
   `configs/collection_urls.txt`
4. Запустить:
   `run_collection_link_converter.bat`
5. Получить готовый файл с партнёрскими ссылками:
   `postsCollections/collection_YYYY-MM-DD_HH-MM-SS.txt`

### 2. Один отель из разных городов вылета

1. Добавить ссылку/ссылки OnlineTours в:
   `configs/hotel_urls.txt`
2. Указать города в:
   `configs/departure_cities.txt`
3. Запустить:
   `run_collection_url_generator_hotel.bat`
4. Получить:
   `postsCollections/hotel_cities_YYYY-MM-DD_HH-MM-SS.txt`
5. Запустить:
   `run_collection_link_converter_hotel.bat`
6. Получить:
   `postsCollections/hotel_cities_PARTNERS_YYYY-MM-DD_HH-MM-SS.txt`

> Старые файлы из предыдущих экспериментов больше не лежат вперемешку с рабочим конвейером. Они сохранены в `legacy/` и ничего не потеряно.

---

## Перед первым запуском после Stage 1

Запусти:

```text
run_stage1_checks.bat
```

Этот тест **не открывает Chrome и не ходит на сайты**. Он:

- проверяет текущие конфиги;
- проверяет разбор поисковых запросов;
- проверяет фильтры OnlineTours;
- проверяет формат промежуточных строк;
- проверяет генерацию `sub_id`;
- проверяет hotel-mode parsing;
- запускает unit-тесты.

На момент подготовки Stage 1 проходит **15 тестов**.

Подробный живой сценарий проверки: `docs/TEST_PLAN.md`.

Для быстрого live-smoke без обработки всех запросов можно запустить:

```text
run_smoke_collection.bat
```

Он берёт только **первый запрос** из основного конфига и пишет результат отдельно в `smoke_output/`, не портя `configs/collection_urls.txt`. После успешного поиска запусти `run_smoke_link_converter.bat` — он проверит Travelpayouts только на этом одном результате.

---

# Рабочая архитектура

```text
TurBox/
│
├── run_collection_url_generator.bat
├── run_collection_link_converter.bat
├── run_collection_url_generator_hotel.bat
├── run_collection_link_converter_hotel.bat
├── run_stage1_checks.bat
├── run_smoke_collection.bat          # один live-запрос OnlineTours
├── run_smoke_link_converter.bat      # одна live-конвертация Travelpayouts
│
├── collection_url_generator.py       # Selenium: OnlineTours
├── collection_link_converter.py      # orchestration: affiliate conversion
├── link_converter.py                 # Selenium adapter: Travelpayouts
├── browser.py                        # единая точка создания ChromeDriver
│
├── turbox/
│   ├── paths.py                      # единые абсолютные пути проекта
│   ├── search_config.py              # разбор поискового конфига + URL filters
│   ├── hotel_config.py               # чистая логика hotel-mode
│   └── affiliate_formatting.py       # форматирование + sub_id
│
├── configs/
│   ├── url_generation_config.txt
│   ├── hotel_urls.txt
│   ├── departure_cities.txt
│   ├── collection_urls.txt           # генерируемый промежуточный файл
│   └── travelpayoutsSetup.txt        # legacy credentials, НЕ для Git
│
├── data/
│   └── travelpayouts_cookies.pkl     # сессия Travelpayouts, НЕ для Git
│
├── postsCollections/                 # рабочие результаты, НЕ для Git
├── samples/golden/                   # контрольный успешный результат
├── tests/                            # unit-тесты без браузера
├── scripts/validate_stage1.py        # быстрая диагностика
├── docs/                             # архитектура, аудит, тест-план
└── legacy/                           # старый конвейер и резервные копии
```

Подробная схема: `docs/ARCHITECTURE.md`.

---

# Почему Stage 1 сделан именно так

До рефакторинга `collection_url_generator.py` содержал 1227 строк и одновременно отвечал за конфиг, фильтры, URL, Selenium, hotel-mode и сохранение результатов. `collection_link_converter.py` одновременно содержал форматирование, транслитерацию, `sub_id`, парсинг TXT и Selenium-конвертацию Travelpayouts.

На Stage 1 вынесена только **детерминированная логика**, которую можно проверить без сайтов:

- конфиг и фильтры → `turbox/search_config.py`;
- параметры hotel-mode → `turbox/hotel_config.py`;
- формат результата и `sub_id` → `turbox/affiliate_formatting.py`;
- пути → `turbox/paths.py`.

Selenium оставлен там, где результат зависит от текущего HTML/JS сайтов. Это сознательное решение: сначала живой smoke-test на твоём ПК, потом более глубокая переработка.

После Stage 1:

- `collection_url_generator.py`: примерно **1227 → 956 строк**;
- `collection_link_converter.py`: примерно **477 → 259 строк**;
- чистая логика покрыта автоматическими тестами;
- старые файлы отделены от production-конвейера.

---

# Конфигурация обычного поиска

Пример строки из `configs/url_generation_config.txt`:

```text
Москва|Турция|27.08.2026|ночей:7-8|взрослых:2|цена:40000-120000|рейтинг:5|питание:(Всё включено|Ультра всё включено)|сортировка:цена
```

Значения:

- `Москва` — город вылета;
- `Турция` — направление;
- `27.08.2026` — исходная дата поиска;
- `ночей:7-8` — диапазон ночей;
- `взрослых:2` — туристы;
- `цена:40000-120000` — диапазон цены;
- `рейтинг:5` — текущий фильтр OnlineTours;
- `питание:(...)` — варианты питания;
- `сортировка:цена` — сортировка по цене.

Параметр:

```text
searchMinPriceData=true
```

включает существующую логику поиска более выгодной даты.

### Почему конфиг пока не переведён в YAML

Текущий текстовый формат уже используется и работает. На первом этапе его замена дала бы мало практической пользы и одновременно увеличила риск сломать привычный процесс. Парсер теперь вынесен в отдельный модуль и покрыт тестами; поэтому формат можно спокойно заменить позже, если это действительно понадобится.

---

# Travelpayouts

На Stage 1 **не заменена** рабочая Selenium-конвертация на API.

Сейчас схема остаётся:

```text
OnlineTours URL
    ↓
collection_link_converter.py
    ↓
link_converter.py
    ↓
Travelpayouts через браузер
    ↓
партнёрная ссылка + sub_id
```

Но граница теперь подготовлена так, чтобы позже заменить Selenium-реализацию на API-клиент, не переписывая разбор поисковых результатов и `sub_id`.

Это запланировано только после отдельной проверки, что API Travelpayouts корректно работает именно с программой OnlineTours и сохраняет нужный `sub_id`.

---

# Credentials и безопасность

## Рекомендуемый вариант: `.env`

Есть шаблон:

```text
.env.example
```

Скопируй его в `.env` и укажи данные:

```text
TRAVELPAYOUTS_EMAIL=...
TRAVELPAYOUTS_PASSWORD=...
TRAVELPAYOUTS_HUMAN_INPUT=false
```

`link_converter.py` теперь пытается загрузить `.env`, если установлен `python-dotenv`.

## Legacy-вариант

Старый файл всё ещё поддерживается:

```text
configs/travelpayoutsSetup.txt
```

Он оставлен, чтобы Stage 1 не сломал твою текущую авторизацию.

**Этот файл нельзя коммитить или публиковать.** Он находится в `.gitignore`.

Так же не публиковать:

```text
data/travelpayouts_cookies.pkl
```

### Важно про старую Git-историю

В исходном архиве `configs/travelpayoutsSetup.txt` уже был когда-то tracked Git-файлом, несмотря на `.gitignore`. Поэтому старая `.git`-история потенциально могла содержать credentials.

Stage 1 поставляется с **новой чистой Git-историей**, без этого файла. Исходный `TurBox.zip` остаётся у тебя как архив старой истории.

Если старый репозиторий когда-либо был публичным или доступным посторонним, безопаснее сменить пароль/credentials Travelpayouts.

---

# Что такое `samples/golden`

```text
samples/golden/collection_2026-08-19_21-30-42.txt
```

Это копия успешного результата от 19.08.2026, полученного до Stage 1.

Она используется как **контрольная точка поведения**: мы знаем, что исходная версия на тот момент реально дошла от поиска до готовых партнёрских ссылок.

---

# Что пока специально НЕ исправлялось

Stage 1 не должен превращаться в рискованный rewrite. Поэтому пока оставлены:

1. Selenium OnlineTours.
2. Selenium Travelpayouts.
3. Значительная часть `time.sleep()` в site-dependent коде.
4. Некоторые широкие `except` в Selenium-ветках.
5. TXT как промежуточный формат между генератором и конвертером.
6. Два последовательных пользовательских запуска: генерация → конвертация.
7. Текущая логика `sub_id`.
8. Текущие OnlineTours selectors.

Это кандидаты на Stage 2 после живого тестирования.

---

# Известные особенности, найденные тестами

## 1. Диапазон даты в `sub_id`

Старая функция получает строку вроде:

```text
5 - 13 авг
```

и первая часть `5` не содержит название месяца. Поэтому текущая legacy-логика `sub_id` кодирует такую дату не идеально.

На Stage 1 **поведение сохранено намеренно**, чтобы не менять существующую аналитику Travelpayouts незаметно. Исправление стоит сделать отдельным изменением после решения, какой формат `sub_id` считать новым стандартом.

## 2. Повтор города в hotel-mode

В текущем `configs/departure_cities.txt` город `Екатеринбург` указан дважды.

Диагностика выводит предупреждение, но Stage 1 ничего автоматически не удаляет: это пользовательский конфиг.

---

# Legacy

В `legacy/` перемещены старые компоненты, которые не вызываются четырьмя рабочими BAT-файлами:

- старый parser pipeline;
- selection/post generation pipeline;
- старая реализация TopHotels;
- backup-файлы;
- старые конфиги и результаты.

**Они не удалены.** Если выяснится, что оттуда нужна функция, её можно спокойно вернуть или перенести в новое ядро.

TopHotels в дальнейшем логичнее интегрировать через более зрелое ядро HotelIQ, а не развивать старый `legacy/old_pipeline/top_hotels_parser.py`.

---

# Установка

Рекомендуемый Python: **3.10+**.

```text
pip install -r requirements.txt
```

Основные зависимости:

- Selenium;
- webdriver-manager;
- python-dotenv.

Chrome должен быть установлен в системе.

---

# Если что-то упало

1. Не начинай сразу менять код.
2. Сохрани весь текст консоли.
3. Посмотри `debug_logs/`.
4. Не удаляй последний корректный входной/выходной файл.
5. Если ошибка в OnlineTours — пришли лог и, если создан, debug-пак нужного шага.
6. Если ошибка в Travelpayouts — пришли лог **без пароля и cookies**.

Перед живой диагностикой сначала запусти:

```text
run_stage1_checks.bat
```

Если локальные тесты зелёные, а живой поиск падает, почти наверняка проблема находится в site-dependent Selenium-слое, а не в конфиге/форматировании Stage 1.

---

# Что делать дальше

Порядок после подтверждения Stage 1:

1. Живой smoke-test обычной цепочки.
2. Живой smoke-test hotel-mode.
3. Исправить только реальные ошибки, если они проявятся.
4. Stage 2:
   - уменьшение `sleep()` и переход на ожидания состояний;
   - типизированные модели результата вместо Tuple;
   - JSON как внутренний транспорт при сохранении красивого TXT;
   - единый pipeline «нашёл → конвертировал»;
   - проверка Travelpayouts API;
   - интеграция HotelIQ;
   - затем DealScore/маркетинговая аналитика.

Для продолжения в другом аккаунте/чате используй `HANDOFF.md` вместе с архивом проекта.
