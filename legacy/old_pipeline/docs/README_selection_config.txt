Файл selection_config.json определяет наборы подборок для модуля selection_builder.py.

Структура:
{
  "selections": [ ... ]   // массив подборок
}

Каждая подборка – объект с полями (все необязательны, кроме source_mask):

- name (string) – короткое имя подборки, используется для логирования и имени выходного файла по умолчанию.
- source_mask (string или массив строк) – glob-маска для поиска result_*.json, например "results/result_Москва-Египет.json".
- filters (object) – критерии фильтрации туров.
    - arrival_country (string или массив) – страна прибытия.
    - departure_cities (массив строк) – города вылета.
    - price_min, price_max (number) – диапазон цены.
    - nights_min, nights_max (number) – диапазон ночей.
    - meal_type (массив строк) – типы питания, например ["Всё включено"].
    - min_top_hotel_rating (number) – минимальный рейтинг на TopHotels.
    - min_rating (number) – минимальный рейтинг onlinetours.
    - stars (массив чисел) – звёздность отеля, например [5] или [4,5].
- sort (object) – сортировка: {"field": "price", "order": "asc"} или "desc".
    Допустимые поля: price, nights, price_per_night, price_per_night_per_person, top_hotel_rating, rating, stars, departure_date.
- limit (integer) – максимальное количество туров в подборке.
- output_file (string) – путь для сохранения JSON результата (по умолчанию selections/{name}.json).

Пример конфигурации:

{
  "selections": [
    {
      "name": "egypt_top_rating",
      "source_mask": "results/result_Москва-Египет.json",
      "filters": {
        "arrival_country": "Египет",
        "price_max": 120000,
        "min_top_hotel_rating": 4.5,
        "meal_type": ["Всё включено", "Ультра всё включено"],
        "nights_min": 7
      },
      "sort": {"field": "top_hotel_rating", "order": "desc"},
      "limit": 10,
      "output_file": "selections/egypt_top_rating.json"
    },
    {
      "name": "cheapest_turkey",
      "source_mask": "results/result_*Турция*.json",
      "filters": {
        "arrival_country": "Турция",
        "price_max": 80000
      },
      "sort": {"field": "price", "order": "asc"},
      "limit": 15
    }
  ]
}

Примечание: все поля filters опциональны. Если поле не указано – фильтрация по нему не применяется.
