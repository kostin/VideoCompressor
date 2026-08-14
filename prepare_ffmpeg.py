#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вспомогательный скрипт для загрузки и подготовки бинарников ffmpeg и ffprobe перед сборкой.
Используется как локально, так и в GitHub Actions CI.
"""

import os
import sys
import shutil
import urllib.request
import zipfile
from pathlib import Path

# Включение UTF-8 вывода в Windows консоли во избежание UnicodeEncodeError (cp1251/cp1252)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def prepare_ffmpeg():
    workspace = Path(__file__).parent.resolve()
    ffmpeg_exe = workspace / "ffmpeg.exe"
    ffprobe_exe = workspace / "ffprobe.exe"

    if ffmpeg_exe.is_file() and ffprobe_exe.is_file():
        try:
            sz_m = ffmpeg_exe.stat().st_size
            sz_p = ffprobe_exe.stat().st_size
            if sz_m > 1024 * 1024 and sz_p > 1024 * 1024:
                print(f"[OK] FFmpeg бинарники уже присутствуют в {workspace}")
                print(f"  ffmpeg.exe: {sz_m / (1024*1024):.1f} МБ")
                print(f"  ffprobe.exe: {sz_p / (1024*1024):.1f} МБ")
                return
        except Exception:
            pass

    # Проверка системного PATH
    sys_ffmpeg = shutil.which("ffmpeg")
    sys_ffprobe = shutil.which("ffprobe")
    if sys_ffmpeg and sys_ffprobe:
        try:
            ffmpeg_p = Path(sys_ffmpeg)
            ffprobe_p = Path(sys_ffprobe)
            if ffmpeg_p.stat().st_size > 1024 * 1024 and ffprobe_p.stat().st_size > 1024 * 1024:
                if str(ffmpeg_p.resolve()) != str(ffmpeg_exe.resolve()):
                    print(f"[OK] Копирование системных бинарников из PATH ({sys_ffmpeg})...")
                    shutil.copy2(sys_ffmpeg, ffmpeg_exe)
                    shutil.copy2(sys_ffprobe, ffprobe_exe)
                return
        except Exception as err:
            print(f"[WARN] Не удалось скопировать из PATH: {err}")

    # Загрузка архива из надёжных источников
    urls = [
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    ]

    zip_file = workspace / "ffmpeg_temp.zip"
    downloaded = False
    for url in urls:
        print(f"Попытка загрузки FFmpeg с: {url} ...")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=120) as resp, open(zip_file, "wb") as f:
                shutil.copyfileobj(resp, f)
            print("[OK] Архив успешно загружен!")
            downloaded = True
            break
        except Exception as e:
            print(f"[WARN] Не удалось загрузить с {url}: {e}")
            if zip_file.exists():
                zip_file.unlink()

    if not downloaded:
        print("[ERROR] Не удалось загрузить FFmpeg ни из одного источника!")
        sys.exit(1)

    print("Распаковка ffmpeg.exe и ffprobe.exe...")
    extracted_ffmpeg = False
    extracted_ffprobe = False
    with zipfile.ZipFile(zip_file, "r") as z:
        for member in z.namelist():
            base = os.path.basename(member)
            if base == "ffmpeg.exe":
                print(f"  Извлечение {member} -> {ffmpeg_exe.name}...")
                with z.open(member) as src, open(ffmpeg_exe, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted_ffmpeg = True
            elif base == "ffprobe.exe":
                print(f"  Извлечение {member} -> {ffprobe_exe.name}...")
                with z.open(member) as src, open(ffprobe_exe, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted_ffprobe = True

    if zip_file.exists():
        try:
            zip_file.unlink()
        except Exception:
            pass

    if not (extracted_ffmpeg and extracted_ffprobe):
        print(f"[ERROR] Не удалось извлечь бинарники из архива (ffmpeg={extracted_ffmpeg}, ffprobe={extracted_ffprobe})")
        sys.exit(1)

    print(f"[OK] FFmpeg успешно подготовлен!")
    print(f"  ffmpeg.exe: {ffmpeg_exe.stat().st_size / (1024*1024):.1f} МБ")
    print(f"  ffprobe.exe: {ffprobe_exe.stat().st_size / (1024*1024):.1f} МБ")

if __name__ == "__main__":
    prepare_ffmpeg()
