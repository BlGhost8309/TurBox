#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import logging
from pathlib import Path

SELECTIONS_DIR = Path("selections")

def main():
    if not SELECTIONS_DIR.exists():
        print(f"Папка {SELECTIONS_DIR} не найдена.")
        return

    # Ищем все JSON-файлы подборок
    json_files = sorted(SELECTIONS_DIR.glob("*.json"))
    if not json_files:
        print("Нет JSON-файлов подборок в папке selections.")
        return

    print("Доступные подборки:")
    for i, file in enumerate(json_files, 1):
        # Пытаемся извлечь имя подборки из JSON
        try:
            import json
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                name = data.get("selection_name", file.stem)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.debug(f"Не удалось прочитать имя из {file}: {e}")
            name = file.stem
        print(f"{i}. {name} ({file})")
    print("0. Обработать все подборки")

    choice = input("\nВведите номер подборки (или 0 для всех): ").strip()
    if not choice.isdigit():
        print("Некорректный ввод.")
        return
    choice = int(choice)

    if choice == 0:
        # Обрабатываем все файлы
        for file in json_files:
            print(f"\nГенерация поста для {file}...")
            cmd = [sys.executable, "post_generator.py", "--input", str(file)]
            subprocess.run(cmd)
    elif 1 <= choice <= len(json_files):
        selected = json_files[choice-1]
        print(f"\nГенерация поста для {selected}...")
        cmd = [sys.executable, "post_generator.py", "--input", str(selected)]
        subprocess.run(cmd)
    else:
        print("Неверный номер.")

if __name__ == "__main__":
    main()
