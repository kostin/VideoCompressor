#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт сборки автономного EXE-файла VideoCompressor с вкомпилированными ffmpeg и ffprobe.
"""

import sys
import subprocess
import shutil
from pathlib import Path
import prepare_ffmpeg

def build():
    workspace = Path(__file__).parent.resolve()
    ffmpeg_exe = workspace / "ffmpeg.exe"
    ffprobe_exe = workspace / "ffprobe.exe"

    if not ffmpeg_exe.exists() or not ffprobe_exe.exists():
        print("Подготовка ffmpeg и ffprobe перед сборкой...")
        prepare_ffmpeg.prepare_ffmpeg()

    if not ffmpeg_exe.exists() or not ffprobe_exe.exists():
        print("❌ ОШИБКА: ffmpeg.exe или ffprobe.exe не найдены перед запуском PyInstaller!")
        sys.exit(1)

    print("Запуск PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name=VideoCompressor",
        "--clean",
        "--add-binary", f"{ffmpeg_exe.name};.",
        "--add-binary", f"{ffprobe_exe.name};.",
        "compress_videos.py"
    ]
    
    res = subprocess.run(cmd, cwd=str(workspace))
    if res.returncode != 0:
        print(f"\n❌ Ошибка при сборке PyInstaller (код {res.returncode})")
        sys.exit(res.returncode)

    dist_exe = workspace / "dist" / "VideoCompressor.exe"
    target_exe = workspace / "VideoCompressor.exe"
    if not dist_exe.exists():
        print(f"❌ ОШИБКА: Собранный файл {dist_exe} не найден!")
        sys.exit(1)

    shutil.copy2(dist_exe, target_exe)
    print(f"\n=======================================================")
    print(f"✔ Сборка успешно завершена!")
    print(f"Готовый файл: {target_exe}")
    print(f"Размер: {target_exe.stat().st_size / (1024*1024):.1f} МБ")
    print(f"=======================================================\n")

if __name__ == "__main__":
    build()
