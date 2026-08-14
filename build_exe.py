#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт сборки автономного EXE-файла VideoCompressor с вкомпилированными ffmpeg и ffprobe.
"""

import sys
import subprocess
import shutil
from pathlib import Path

def build():
    workspace = Path(__file__).parent.resolve()
    ffmpeg_exe = workspace / "ffmpeg.exe"
    ffprobe_exe = workspace / "ffprobe.exe"

    if not ffmpeg_exe.exists() or not ffprobe_exe.exists():
        print("Копирование ffmpeg и ffprobe в директорию сборщика...")
        sys_ffmpeg = shutil.which("ffmpeg")
        sys_ffprobe = shutil.which("ffprobe")
        if sys_ffmpeg and sys_ffprobe:
            shutil.copy(sys_ffmpeg, ffmpeg_exe)
            shutil.copy(sys_ffprobe, ffprobe_exe)
        else:
            import compress_videos
            compress_videos.check_and_setup_ffmpeg()

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
    if res.returncode == 0:
        dist_exe = workspace / "dist" / "VideoCompressor.exe"
        target_exe = workspace / "VideoCompressor.exe"
        if dist_exe.exists():
            shutil.copy2(dist_exe, target_exe)
            print(f"\n=======================================================")
            print(f"Сборка успешно завершена!")
            print(f"Готовый файл: {target_exe}")
            print(f"Размер: {target_exe.stat().st_size / (1024*1024):.1f} МБ")
            print(f"=======================================================\n")
    else:
        print(f"\nОшибка при сборке PyInstaller (код {res.returncode})")

if __name__ == "__main__":
    build()
