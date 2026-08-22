# TurBox — результаты реальных тестов 22.08.2026

Этот файл фиксирует факты, полученные на пользовательском Windows/Chrome, а не только локальные unit-тесты.

## 1. Local Stage 1 checks

`run_stage1_checks.bat` после исправления кодировки BAT:

- запускается в Windows cmd;
- 15/15 unit-тестов проходят;
- Stage 1 local checks — OK.

## 2. Smoke OnlineTours

`run_smoke_collection.bat` — успешно.

## 3. Smoke Travelpayouts

Converter проверен на 5 ссылках — пользователь подтвердил корректную работу. Дальнейшая оптимизация converter отложена, потому что parser важнее.

## 4. Full OnlineTours run до performance patch

Время:

```text
start 13:35:28
finish 14:36:02
≈ 60m33s
```

Обработано 57 поисковых запросов. Все дошли до записи результата.

Ошибки:

- `[ERROR]`: 0;
- `Traceback`: 0;
- WARNING: 63.

Структура WARNING:

- 57 × старый поиск dropdown города не находил список и переходил к Enter;
- 6 × price element не найден после фильтров.

Шесть записей без цены:

1. Нижний Новгород → Кисловодск
2. Нижний Новгород → Ессентуки
3. Пермь → Кисловодск
4. Пермь → Ессентуки
5. Самара → Кисловодск
6. Самара → Ессентуки

Важно: URL при этом формировался и сохранялся. Нужно определить, означает ли страница реальное отсутствие офферов или изменение DOM цены.

Полный лог: `evidence/full_generator_run_2026-08-22.log`.

## 5. Performance patch parser

Актуальный `collection_url_generator.py` изменён точечно:

- город: Enter-first, dropdown fallback;
- ожидание price/no-results по состоянию;
- stage timings;
- debug capture для проблемной цены.

## 6. Five-request smoke после patch

Результаты:

| Город | Total | City | Cheapest date | Price state |
|---|---:|---:|---:|---:|
| Москва | 41.9s | 0.7s | 16.6s | 3.4s |
| Санкт-Петербург | 45.2s | 0.8s | 21.6s | 1.2s |
| Екатеринбург | 40.2s | 0.6s | 17.8s | 1.0s |
| Казань | 44.2s | 0.5s | 21.9s | 1.2s |
| Нижний Новгород | 42.4s | 4.1s | 18.5s | 1.8s |

Средний total: ~42.8s.

Старый полный wall-clock baseline: ~63.7s/query.

Вывод: Enter-first убрал типичные 6–10 секунд бесполезного ожидания dropdown, а динамическое ожидание цены также сократило часть задержки. Главный новый bottleneck — `cheapest_date`.

Лог: `evidence/optimized_generator_smoke_2026-08-22.log`.

Output smoke содержит 10 строк-результатов, потому что в файле уже было 5 старых записей и новый тест дописал №6–10. Сам последний запуск обработал именно 5 новых запросов.

## 7. Что считается текущей рабочей версией

Актуальный файл:

`collection_url_generator.py` из корня этого handoff archive.

Не откатывать его на версию Stage 1 до performance patch.

Все active BAT в этом архиве уже исправлены под Windows cmd (ASCII + CRLF).
