#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import argparse
from pathlib import Path
from datetime import datetime, date

# ------------------------------------------------------------
# Конфигурация
# ------------------------------------------------------------
TEMPLATE_FILE = Path("configs/post_template.txt")
POSTS_DIR = Path("posts")

# Словарь транслитерации для основных слов (русский -> латиница)
TRANSLIT_MAP = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    ' ': '_', '-': '_', '’': '', "'": '',
}

# Дополнительные слова (города, страны) для кастомной замены (регистронезависимо)
CUSTOM_TRANSLIT = {
    'москва': 'moskva',
    'санкт-петербург': 'spb',
    'египет': 'egipet',
    'турция': 'turkey',
    'шарм-эль-шейх': 'sharm',
    'хургада': 'hurgada',
    'оаэ': 'oae',
    'таиланд': 'tailand',
    'индия': 'indiya',
    'мальдивы': 'maldivy',
}


# ------------------------------------------------------------
# Вспомогательные функции
# ------------------------------------------------------------
def transliterate(text: str) -> str:
    """Упрощённая транслитерация кириллицы в латиницу."""
    text = text.lower()
    # сначала замена целых слов
    for ru, en in CUSTOM_TRANSLIT.items():
        text = re.sub(r'\b' + ru + r'\b', en, text)
    # посимвольная замена
    result = []
    for ch in text:
        result.append(TRANSLIT_MAP.get(ch, ch if ch.isalnum() else '_'))
    # убираем лишние подчёркивания
    cleaned = re.sub(r'_+', '_', ''.join(result)).strip('_')
    return cleaned


def normalize_hotel_name_short(hotel_name: str) -> str:
    """
    Укорачивает название отеля:
    - удаляет слова 'hotel', 'resort', '&'
    - заменяет пробелы на подчёркивания
    - ограничивает до 20 символов
    - оставляет только латиницу, цифры, подчёркивания
    """
    # транслитерация
    latin = transliterate(hotel_name)
    # удаляем лишние слова (можно расширить список)
    for word in ['hotel', 'resort', '&']:
        latin = re.sub(r'\b' + word + r'\b', '', latin)
    # заменяем всё, что не буква/цифра/подчёркивание
    latin = re.sub(r'[^a-z0-9_]', '_', latin)
    # убираем повторяющиеся подчёркивания
    latin = re.sub(r'_+', '_', latin).strip('_')
    # обрезаем до 20 символов
    if len(latin) > 20:
        latin = latin[:20].rstrip('_')
    return latin


def parse_departure_date_iso(date_str: str) -> str:
    """
    Преобразует строку вида "23 май, сб" в YYYY_MM_DD.
    Если не удаётся – возвращает пустую строку.
    """
    months_ru = {
        'янв': '01', 'фев': '02', 'мар': '03', 'апр': '04',
        'май': '05', 'июн': '06', 'июл': '07', 'авг': '08',
        'сен': '09', 'окт': '10', 'ноя': '11', 'дек': '12'
    }
    match = re.match(r'(\d{1,2})\s+([а-я]+)', date_str.strip())
    if not match:
        return ""
    day = int(match.group(1))
    month_name = match.group(2)[:3]
    month = months_ru.get(month_name)
    if not month:
        return ""
    today = date.today()
    year = today.year
    # если месяц уже прошёл в этом году – следующий год (календарь туров обычно вперёд)
    if int(month) < today.month:
        year += 1
    try:
        d = date(year, int(month), day)
        return d.strftime("%Y_%m_%d")
    except ValueError:
        return ""


def generate_sub_id(tour: dict) -> str:
    """
    Генерирует Sub ID для тура.
    Формат: departure_city_arrival_country_hotel_name_short_departure_date_iso_nights
    Все части транслитерированы, в нижнем регистре.
    """
    # Город вылета
    dep_city = transliterate(tour.get("departure_city", ""))
    if not dep_city:
        dep_city = "unknown"

    # Страна прибытия
    arr_country = transliterate(tour.get("arrival_country", ""))
    if not arr_country:
        arr_country = "unknown"

    # Короткое название отеля
    hotel_full = tour.get("hotel_name", "")
    hotel_short = normalize_hotel_name_short(hotel_full) if hotel_full else "hotel"

    # Дата вылета в ISO
    dep_date = tour.get("departure_date", "")
    date_iso = parse_departure_date_iso(dep_date) if dep_date else ""

    # Количество ночей
    nights = tour.get("nights", 0)
    nights_str = str(nights) if nights else "0"

    # Собираем части, заменяя пустые на '0' или 'unknown'
    parts = [dep_city, arr_country, hotel_short]
    if date_iso:
        parts.append(date_iso)
    else:
        parts.append("date_unknown")
    parts.append(nights_str)

    sub_id = "_".join(parts)
    # финальная очистка: только латиница, цифры, подчёркивания
    sub_id = re.sub(r'[^a-z0-9_]', '_', sub_id)
    sub_id = re.sub(r'_+', '_', sub_id).strip('_')
    return sub_id


# ------------------------------------------------------------
# Основные функции (без изменений, кроме generate_post)
# ------------------------------------------------------------
def load_json(input_path: Path) -> dict:
    if not input_path.exists():
        raise FileNotFoundError(f"Файл {input_path} не найден")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "tours" not in data or not isinstance(data["tours"], list):
        raise ValueError("JSON должен содержать поле 'tours' со списком туров")
    return data


def load_template(template_path: Path) -> str:
    if not template_path.exists():
        raise FileNotFoundError(f"Шаблон не найден: {template_path}")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def replace_placeholders(template: str, tour: dict) -> str:
    def replacer(match):
        field = match.group(1)
        value = tour.get(field, "")
        if isinstance(value, (int, float)):
            return str(value)
        elif value is None:
            return ""
        return str(value)
    pattern = r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}"
    return re.sub(pattern, replacer, template)


def generate_post(data: dict, template: str) -> str:
    """
    Генерирует пост: для каждого тура сначала выводит строку-комментарий с Sub ID,
    затем сам блок (с заменёнными плейсхолдерами).
    """
    tours = data["tours"]
    blocks = []
    for tour in tours:
        sub_id = generate_sub_id(tour)
        print(f"Сгенерирован Sub ID для тура {tour.get('hotel_name', '?')}: {sub_id}")
        comment_line = f"<!-- sub_id: {sub_id} -->"
        block = replace_placeholders(template, tour)
        full_block = comment_line + "\n" + block
        blocks.append(full_block)
    return "\n\n".join(blocks)


def save_post(content: str, selection_name: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{selection_name}.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)
    return output_file


def main():
    parser = argparse.ArgumentParser(description="Генерация черновика поста Telegram из подборки туров")
    parser.add_argument("--input", "-i", required=True, help="Путь к JSON-файлу подборки (например, selections/egypt_top_rating.json)")
    args = parser.parse_args()

    input_path = Path(args.input)

    try:
        data = load_json(input_path)
        selection_name = data.get("selection_name")
        if not selection_name:
            selection_name = input_path.stem

        template = load_template(TEMPLATE_FILE)
        post_content = generate_post(data, template)
        output_file = save_post(post_content, selection_name, POSTS_DIR)

        num_tours = len(data["tours"])
        print(f"✅ Сгенерирован пост для подборки '{selection_name}', сохранён в {output_file}, обработано {num_tours} туров.")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
