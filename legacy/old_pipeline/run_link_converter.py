#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
from pathlib import Path

POSTS_DIR = Path("posts")

def main():
    if not POSTS_DIR.exists():
        print(f"Папка {POSTS_DIR} не найдена.")
        input("Нажмите Enter для выхода...")
        return

    txt_files = sorted(POSTS_DIR.glob("*.txt"))
    txt_files = [f for f in txt_files if not f.stem.endswith("_PARTNERS")]
    if not txt_files:
        print("Нет текстовых файлов постов в папке posts (или все уже обработаны).")
        input("Нажмите Enter для выхода...")
        return

    print("Доступные посты:")
    for i, file in enumerate(txt_files, 1):
        print(f"{i}. {file.name}")
    print("0. Обработать все посты")

    choice = input("\nВведите номер поста (или 0 для всех): ").strip()
    if not choice.isdigit():
        print("Некорректный ввод.")
        input("Нажмите Enter для выхода...")
        return
    choice = int(choice)

    force_login = input("Принудительный вход (--force-login)? (y/n, по умолчанию n): ").strip().lower()
    force_flag = ["--force-login"] if force_login == 'y' else []

    if choice == 0:
        for file in txt_files:
            print(f"\nОбработка {file}...")
            cmd = [sys.executable, "-u", "link_converter.py", "--input", str(file)] + force_flag
            # Запускаем с выводом в реальном времени
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                print(line, end='')
            proc.wait()
    elif 1 <= choice <= len(txt_files):
        selected = txt_files[choice-1]
        print(f"\nОбработка {selected}...")
        cmd = [sys.executable, "-u", "link_converter.py", "--input", str(selected)] + force_flag
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            print(line, end='')
        proc.wait()
    else:
        print("Неверный номер.")
        input("Нажмите Enter для выхода...")
        return

    print("\nГотово.")
    input("Нажмите Enter для выхода...")

if __name__ == "__main__":
    main()
