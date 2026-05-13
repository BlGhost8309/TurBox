#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для генерации черновика поста Telegram на основе JSON-подборки (selection_builder.py).
Использует шаблон post_template.txt, заменяет плейсхолдеры {field} на значения из туров.
"""

import json
import re
import argparse
from pathlib import Path

# Константы
TEMPLATE_FILE = Path("post_template.txt")
POSTS_DIR = Path("posts")


def load_json(input_path: Path) -> dict:
    """Загружает JSON-файл подборки."""
    if not input_path.exists():
        raise FileNotFoundError(f"Файл {input_path} не найден")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "tours" not in data or not isinstance(data["tours"], list):
        raise ValueError("JSON должен содержать поле 'tours' со списком туров")
    return data


def load_template(template_path: Path) -> str:
    """Загружает шаблон поста из текстового файла."""
    if not template_path.exists():
        raise FileNotFoundError(f"Шаблон не найден: {template_path}")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


def replace_placeholders(template: str, tour: dict) -> str:
    """
    Заменяет все плейсхолдеры {field} в шаблоне на значения из тура.
    Если поля нет – заменяет на пустую строку.
    """
    def replacer(match):
        field = match.group(1)
        value = tour.get(field, "")
        # Преобразуем в строку (числа, списки – но списков в турах нет)
        if isinstance(value, (int, float)):
            # Оставляем как есть, но можно форматировать
            return str(value)
        elif value is None:
            return ""
        return str(value)

    # Ищем все вхождения {слово_или_цифры_или_подчёркивание}
    pattern = r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}"
    return re.sub(pattern, replacer, template)


def generate_post(data: dict, template: str) -> str:
    """
    Генерирует итоговый текст поста: для каждого тура применяет шаблон,
    склеивает блоки с разделителем в две пустые строки (можно менять).
    """
    tours = data["tours"]
    blocks = []
    for tour in tours:
        block = replace_placeholders(template, tour)
        blocks.append(block)
    # Разделяем блоки двумя переносами строк (можно задать в конфиге, но для простоты так)
    return "\n\n".join(blocks)


def save_post(content: str, selection_name: str, output_dir: Path) -> Path:
    """Сохраняет пост в файл posts/{selection_name}.txt."""
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
            # Пытаемся взять из имени файла
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
