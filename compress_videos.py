#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Compressor for Windows
Скрипт для сжатия видеофайлов в текущей папке до заданного размера и разрешения.
Автоматически проверяет наличие ffmpeg/кодеков и при необходимости скачивает их.
"""

import os
import sys
import shutil
import subprocess
import urllib.request
import zipfile
import json
import time
import math
from pathlib import Path

# Поддерживаемые расширения видео
SUPPORTED_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv",
    ".webm", ".m4v", ".ts", ".mts", ".m2ts", ".3gp"
}

# Ссылка на стабильную сборку FFmpeg для Windows (essentials release)
FFMPEG_WINDOWS_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_BACKUP_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"


class Colors:
    """ANSI цветовое оформление для Windows терминала"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    GRAY = "\033[90m"


def enable_windows_ansi():
    """Включение поддержки UTF-8 и ANSI escape-кодов в Windows cmd/powershell"""
    if sys.platform == "win32":
        try:
            # Настройка UTF-8 для вывода в консоль
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


# Активируем UTF-8 и цвета при загрузке модуля
enable_windows_ansi()


def format_size(bytes_val: int) -> str:
    """Форматирование байтов в читаемый вид (КБ, МБ, ГБ)"""
    for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']:
        if bytes_val < 1024.0 or unit == 'ТБ':
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.2f} Б"


def format_seconds(seconds: float) -> str:
    """Форматирование секунд в ЧЧ:ММ:СС или ММ:СС"""
    if seconds is None or math.isnan(seconds) or seconds < 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def print_progress_bar(percent: float, prefix="", suffix="", length=30):
    """Вывод красивого прогресс-бара"""
    filled_len = int(length * percent // 100)
    bar = "█" * filled_len + "░" * (length - filled_len)
    percent_str = f"{percent:5.1f}%"
    sys.stdout.write(f"\r{prefix} |{Colors.CYAN}{bar}{Colors.RESET}| {Colors.BOLD}{percent_str}{Colors.RESET} {suffix}")
    sys.stdout.flush()


def download_with_progress(url: str, dest_path: Path):
    """Скачивание файла с отображением прогресса"""
    print(f"{Colors.CYAN}Скачивание:{Colors.RESET} {url}")
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
            total_length = response.getheader('content-length')
            if total_length is None:
                out_file.write(response.read())
            else:
                total_length = int(total_length)
                downloaded = 0
                block_size = 1024 * 64
                start_time = time.time()
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    downloaded += len(buffer)
                    out_file.write(buffer)
                    percent = (downloaded / total_length) * 100
                    elapsed = time.time() - start_time
                    speed = (downloaded / (elapsed + 1e-5)) / (1024 * 1024)
                    suffix = f"{format_size(downloaded)} / {format_size(total_length)} ({speed:.1f} МБ/с)"
                    print_progress_bar(percent, prefix=f"{Colors.YELLOW}Загрузка{Colors.RESET}", suffix=suffix)
        print()
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink()
        raise e


def check_and_setup_ffmpeg() -> tuple[str, str]:
    """
    Проверяет наличие ffmpeg и ffprobe:
    1. Внутри вкомпилированного EXE (через PyInstaller _MEIPASS)
    2. В директории рядом с исполняемым файлом/скриптом
    3. В системном PATH
    Если не найдены — скачивает и распаковывает Windows-сборку.
    Возвращает пути (ffmpeg_path, ffprobe_path).
    """
    # 1. Проверка вкомпилированных бинарников (PyInstaller bundle)
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        bundle_ffmpeg = Path(meipass) / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        bundle_ffprobe = Path(meipass) / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe")
        if bundle_ffmpeg.is_file() and bundle_ffprobe.is_file():
            return str(bundle_ffmpeg), str(bundle_ffprobe)

    # 2. Проверка рядом с исполняемым файлом / скриптом
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent.resolve()
    else:
        app_dir = Path(__file__).parent.resolve()

    local_ffmpeg = app_dir / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    local_ffprobe = app_dir / ("ffprobe.exe" if sys.platform == "win32" else "ffprobe")

    ffmpeg_bin = None
    ffprobe_bin = None

    if local_ffmpeg.is_file() and local_ffprobe.is_file():
        ffmpeg_bin = str(local_ffmpeg)
        ffprobe_bin = str(local_ffprobe)
    else:
        sys_ffmpeg = shutil.which("ffmpeg")
        sys_ffprobe = shutil.which("ffprobe")
        if sys_ffmpeg and sys_ffprobe:
            ffmpeg_bin = sys_ffmpeg
            ffprobe_bin = sys_ffprobe

    # Проверка поддержки кодеков h264/h265
    codecs_ok = False
    if ffmpeg_bin:
        try:
            res = subprocess.run(
                [ffmpeg_bin, "-encoders"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )
            out = res.stdout
            if "libx264" in out or "h264" in out:
                codecs_ok = True
        except Exception:
            codecs_ok = False

    if ffmpeg_bin and ffprobe_bin and codecs_ok:
        print(f"{Colors.GREEN}✔ FFmpeg найден:{Colors.RESET} {ffmpeg_bin}")
        return ffmpeg_bin, ffprobe_bin

    print(f"{Colors.YELLOW}⚠ FFmpeg с необходимыми кодеками не найден в системе.{Colors.RESET}")
    print(f"{Colors.CYAN}Начинается автоматическая загрузка FFmpeg для Windows...{Colors.RESET}")

    zip_path = app_dir / "ffmpeg_download.zip"
    try:
        try:
            download_with_progress(FFMPEG_WINDOWS_URL, zip_path)
        except Exception as err:
            print(f"{Colors.YELLOW}Основной источник недоступен ({err}), пробуем запасной...{Colors.RESET}")
            download_with_progress(FFMPEG_BACKUP_URL, zip_path)

        print(f"{Colors.CYAN}Распаковка архива...{Colors.RESET}")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                filename = os.path.basename(member)
                if filename in ("ffmpeg.exe", "ffprobe.exe"):
                    source = zip_ref.open(member)
                    target_file = app_dir / filename
                    with open(target_file, "wb") as target:
                        shutil.copyfileobj(source, target)
                    print(f"  {Colors.GREEN}✔ Извлечен:{Colors.RESET} {filename}")

        if zip_path.exists():
            zip_path.unlink()

        if local_ffmpeg.is_file() and local_ffprobe.is_file():
            print(f"{Colors.GREEN}✔ FFmpeg успешно установлен в папку со скриптом!{Colors.RESET}\n")
            return str(local_ffmpeg), str(local_ffprobe)
        else:
            raise RuntimeError("Не удалось найти ffmpeg.exe/ffprobe.exe внутри скачанного архива.")
    except Exception as e:
        if zip_path.exists():
            zip_path.unlink()
        print(f"\n{Colors.RED}❌ Ошибка при автоматической загрузке FFmpeg: {e}{Colors.RESET}")
        print("Пожалуйста, установите FFmpeg вручную или поместите ffmpeg.exe и ffprobe.exe рядом со скриптом.")
        sys.exit(1)


def get_video_info(ffprobe_path: str, file_path: Path) -> dict:
    """Получение метаданных о видеофайле через ffprobe (JSON)"""
    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path)
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True
        )
        data = json.loads(result.stdout)
        
        duration = float(data.get("format", {}).get("duration", 0))
        size = int(data.get("format", {}).get("size", file_path.stat().st_size))

        video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)

        width = int(video_stream.get("width", 0)) if video_stream else 0
        height = int(video_stream.get("height", 0)) if video_stream else 0
        fps = 30.0
        if video_stream and "r_frame_rate" in video_stream:
            try:
                num, den = video_stream["r_frame_rate"].split("/")
                fps = float(num) / float(den) if float(den) != 0 else 30.0
            except Exception:
                fps = 30.0

        has_audio = audio_stream is not None

        return {
            "duration": duration,
            "size": size,
            "width": width,
            "height": height,
            "fps": fps,
            "has_audio": has_audio
        }
    except Exception as e:
        return {
            "duration": 0,
            "size": file_path.stat().st_size if file_path.exists() else 0,
            "width": 0,
            "height": 0,
            "fps": 30.0,
            "has_audio": True,
            "error": str(e)
        }


def create_subtitles_file(text: str, duration: float, srt_path: Path):
    """
    Создает временный .srt файл субтитров из имени файла.
    Символ '@' заменяется на перенос строки.
    """
    lines = text.replace("@", "\n").strip()
    dur = max(1.0, duration)
    h = int(dur // 3600)
    m = int((dur % 3600) // 60)
    s = int(dur % 60)
    ms = int((dur - int(dur)) * 1000)
    end_time_str = f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    srt_content = f"1\n00:00:00,000 --> {end_time_str}\n{lines}\n"
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)


def compress_video(
    ffmpeg_path: str,
    input_file: Path,
    output_file: Path,
    target_size_mb: float,
    target_short_side: int,
    codec: str,
    passes_count: int,
    subtitles_mode: bool,
    remove_audio: bool,
    file_index: int,
    total_files: int,
    info: dict
) -> bool:
    """
    Сжатие одного видеофайла (в 1 или 2 прохода) под целевой размер, разрешение, субтитры и звук.
    """
    duration = info["duration"]
    orig_size = info["size"]
    target_size_bytes = int(target_size_mb * 1024 * 1024)

    print(f"\n{Colors.BOLD}══════════════════════════════════════════════════════════════════{Colors.RESET}")
    print(f"[{file_index}/{total_files}] {Colors.CYAN}{Colors.BOLD}{input_file.name}{Colors.RESET}")
    print(f"  Исходный размер: {Colors.YELLOW}{format_size(orig_size)}{Colors.RESET} | Длительность: {Colors.YELLOW}{format_seconds(duration)}{Colors.RESET} | Разрешение: {Colors.YELLOW}{info['width']}x{info['height']}{Colors.RESET}")

    # Проверка: если размер и разрешение уже не превышают целевые, не включены субтитры и не требуется удалять звук
    orig_shorter_side = min(info["width"], info["height"]) if (info["width"] > 0 and info["height"] > 0) else 0
    size_ok = orig_size <= target_size_bytes
    res_ok = (orig_shorter_side <= target_short_side) if orig_shorter_side > 0 else True
    needs_audio_removal = remove_audio and info["has_audio"]

    if size_ok and res_ok and not subtitles_mode and not needs_audio_removal:
        print(f"  {Colors.GREEN}✔ Видео уже соответствует целевым параметрам{Colors.RESET} (размер {format_size(orig_size)} <= {target_size_mb:.1f} МБ, {info['width']}x{info['height']} <= {target_short_side}p).")
        print(f"  {Colors.CYAN}➜ Пережатие не требуется. Копирование оригинала в папку 'compressed'...{Colors.RESET}")
        try:
            shutil.copy2(input_file, output_file)
            print(f"  {Colors.GREEN}✔ Файл сохранен без потери качества.{Colors.RESET}")
            return True
        except Exception as e:
            print(f"  {Colors.RED}❌ Ошибка копирования: {e}{Colors.RESET}")
            return False

    if duration <= 0:
        print(f"  {Colors.RED}❌ Не удалось определить длительность видео. Пропуск.{Colors.RESET}")
        return False

    # Расчет целевого битрейта
    if remove_audio or not info["has_audio"]:
        audio_bitrate_kbps = 0
        audio_args = ["-an"]
    else:
        audio_bitrate_kbps = 128 if target_size_mb >= 50 else 96
        audio_args = ["-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k"]

    # Общий битрейт (в килобитах/сек): target_bits / duration
    total_bitrate_kbps = (target_size_bytes * 8) / (duration * 1000)
    video_bitrate_kbps = total_bitrate_kbps - audio_bitrate_kbps

    # Минимальный порог битрейта для стабильности кодирования
    if video_bitrate_kbps < 50:
        print(f"  {Colors.YELLOW}⚠ Внимание: целевой размер слишком мал для длительности ({format_seconds(duration)}). Установлен мин. битрейт 50 kbps.{Colors.RESET}")
        video_bitrate_kbps = 50

    print(f"  Целевой размер: {Colors.GREEN}{target_size_mb:.1f} МБ{Colors.RESET} | Расчетный видео-битрейт: {Colors.GREEN}{int(video_bitrate_kbps)} kbps{Colors.RESET} | Режим: {Colors.GREEN}{passes_count} проход(а){Colors.RESET}")
    if subtitles_mode:
        print(f"  Субтитры: {Colors.CYAN}Включены (текст из имени файла){Colors.RESET}")
    if remove_audio and info["has_audio"]:
        print(f"  Звук: {Colors.YELLOW}Удаление звуковой дорожки{Colors.RESET}")

    # Фильтр масштабирования: меньшая сторона = min(оригинальная_меньшая_сторона, target_short_side)
    scale_filter = (
        f"scale='if(lt(iw,ih),min(iw,{target_short_side}),-2)':"
        f"'if(lt(iw,ih),-2,min(ih,{target_short_side}))'"
    )

    # Подготовка субтитров
    srt_path = input_file.parent / f"_temp_sub_{file_index}.srt"
    if subtitles_mode:
        create_subtitles_file(input_file.stem, duration, srt_path)
        escaped_srt = str(srt_path.resolve()).replace("\\", "/").replace(":", "\\:")
        video_filter = (
            f"{scale_filter},subtitles=filename='{escaped_srt}':"
            f"force_style='FontSize=14,Alignment=1,MarginL=14,MarginV=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=1,Shadow=0'"
        )
    else:
        video_filter = scale_filter

    # Выбор энкодера
    v_encoder = "libx264" if codec == "h264" else "libx265"
    passlog_prefix = str((input_file.parent / f"_temp_pass_{file_index}").resolve()).replace("\\", "/")

    if passes_count == 1:
        # Однопроходное кодирование (быстрее)
        pass_cmd = [
            ffmpeg_path, "-y",
            "-nostats", "-loglevel", "error",
            "-i", str(input_file),
            "-c:v", v_encoder,
            "-b:v", f"{int(video_bitrate_kbps)}k",
            "-maxrate", f"{int(video_bitrate_kbps * 1.4)}k",
            "-bufsize", f"{int(video_bitrate_kbps * 2)}k",
            *audio_args,
            "-vf", video_filter,
            "-preset", "medium",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            str(output_file)
        ]
        passes = [("Сжатие (1 проход)", pass_cmd)]
    else:
        # Двухпроходное кодирование (точнее)
        null_sink = "NUL" if sys.platform == "win32" else "/dev/null"
        pass1_cmd = [
            ffmpeg_path, "-y",
            "-nostats", "-loglevel", "error",
            "-i", str(input_file),
            "-c:v", v_encoder,
            "-b:v", f"{int(video_bitrate_kbps)}k",
            "-pass", "1",
            "-passlogfile", passlog_prefix,
            "-an",
            "-vf", video_filter,
            "-preset", "medium",
            "-f", "null",
            "-progress", "pipe:1",
            null_sink
        ]

        pass2_cmd = [
            ffmpeg_path, "-y",
            "-nostats", "-loglevel", "error",
            "-i", str(input_file),
            "-c:v", v_encoder,
            "-b:v", f"{int(video_bitrate_kbps)}k",
            "-pass", "2",
            "-passlogfile", passlog_prefix,
            *audio_args,
            "-vf", video_filter,
            "-preset", "medium",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            str(output_file)
        ]
        passes = [
            ("Проход 1/2 (Анализ)", pass1_cmd),
            ("Проход 2/2 (Сжатие)", pass2_cmd)
        ]

    for pass_name, cmd in passes:
        start_time = time.time()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            bufsize=1
        )

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            line = line.strip()
            if not line:
                continue

            if "=" in line:
                key, _, value = line.partition("=")
                if key == "out_time_ms":
                    try:
                        time_ms = int(value)
                        cur_sec = time_ms / 1_000_000.0
                        percent = min(100.0, max(0.0, (cur_sec / duration) * 100.0))
                        elapsed = time.time() - start_time
                        
                        # Расчет ETA
                        if percent > 0.5:
                            estimated_total = (elapsed / percent) * 100.0
                            eta = max(0.0, estimated_total - elapsed)
                            eta_str = format_seconds(eta)
                        else:
                            eta_str = "--:--"

                        speed_str = f"Прошло: {format_seconds(elapsed)} | ETA: {eta_str}"
                        prefix = f"  {Colors.BOLD}{pass_name}{Colors.RESET}"
                        print_progress_bar(percent, prefix=prefix, suffix=speed_str)
                    except Exception:
                        pass

        _, stderr_data = process.communicate()
        print_progress_bar(100.0, prefix=f"  {Colors.BOLD}{pass_name}{Colors.RESET}", suffix=f"Готово за {format_seconds(time.time() - start_time)}   \n")

        if process.returncode != 0:
            print(f"  {Colors.RED}❌ Ошибка выполнения FFmpeg ({pass_name}):{Colors.RESET}\n{stderr_data[:500] if stderr_data else 'Код ошибки: ' + str(process.returncode)}")
            _cleanup_temp_files(input_file.parent, file_index)
            return False

    # Удаление временных файлов passlog и srt
    _cleanup_temp_files(input_file.parent, file_index)

    if output_file.exists():
        final_size = output_file.stat().st_size
        diff_pct = ((final_size - orig_size) / orig_size) * 100
        print(f"  {Colors.GREEN}✔ Готово!{Colors.RESET} Итоговый размер: {Colors.GREEN}{format_size(final_size)}{Colors.RESET} ({diff_pct:+.1f}%)")
        return True
    return False


def _cleanup_temp_files(directory: Path, file_index: int):
    """Удаление временных файлов (passlog, srt)"""
    for file in directory.glob(f"_temp_pass_{file_index}*"):
        try:
            file.unlink()
        except Exception:
            pass
    srt_file = directory / f"_temp_sub_{file_index}.srt"
    if srt_file.exists():
        try:
            srt_file.unlink()
        except Exception:
            pass


def prompt_user_settings() -> tuple[float, int, str, int, bool, bool]:
    """Интерактивный опрос пользователя о параметрах сжатия"""
    print(f"{Colors.BOLD}{Colors.CYAN}══════════════════════════════════════════════════════════════════{Colors.RESET}")
    print(f"{Colors.BOLD}             НАСТРОЙКИ СЖАТИЯ ВИДЕО (Video Compressor)            {Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}══════════════════════════════════════════════════════════════════{Colors.RESET}\n")

    # 1. Целевой размер
    while True:
        raw_size = input(f"1) Введите целевой размер видео в МБ [{Colors.GREEN}300{Colors.RESET}]: ").strip()
        if not raw_size:
            target_size_mb = 300.0
            break
        try:
            target_size_mb = float(raw_size.replace(",", "."))
            if target_size_mb <= 0:
                print(f"{Colors.RED}Размер должен быть больше 0!{Colors.RESET}")
                continue
            break
        except ValueError:
            print(f"{Colors.RED}Пожалуйста, введите корректное число.{Colors.RESET}")

    # 2. Целевое разрешение
    print()
    while True:
        raw_res = input(f"2) Введите целевое разрешение по меньшей стороне в px [{Colors.GREEN}1080{Colors.RESET}]: ").strip()
        if not raw_res:
            target_short_side = 1080
            break
        try:
            target_short_side = int(raw_res)
            if target_short_side < 144:
                print(f"{Colors.RED}Разрешение слишком мало (минимум 144px)!{Colors.RESET}")
                continue
            break
        except ValueError:
            print(f"{Colors.RED}Пожалуйста, введите целое число (например, 1080, 720, 480).{Colors.RESET}")

    # 3. Выбор кодека
    print(f"\n3) Выберите кодек сжатия:")
    print(f"   {Colors.GREEN}{Colors.BOLD}[1] H.264 (AVC){Colors.RESET} — максимальная совместимость с любыми плеерами/телевизорами {Colors.GREEN}[По умолчанию]{Colors.RESET}")
    print(f"   [2] H.265 (HEVC) — лучшее качество при сильном сжатии (требует больше времени)")
    codec_choice = input(f"Ваш выбор [{Colors.GREEN}1{Colors.RESET}/2]: ").strip()
    codec = "h265" if codec_choice == "2" else "h264"

    # 4. Выбор количества проходов
    print(f"\n4) Режим кодирования:")
    print(f"   [1] 1 проход  — в ~2 раза быстрее (размер может незначительно отклоняться)")
    print(f"   {Colors.GREEN}{Colors.BOLD}[2] 2 прохода{Colors.RESET} — максимальная точность размера и оптимальное качество {Colors.GREEN}[По умолчанию]{Colors.RESET}")
    passes_choice = input(f"Ваш выбор [1/{Colors.GREEN}2{Colors.RESET}]: ").strip()
    passes_count = 1 if passes_choice == "1" else 2

    # 5. Наложение субтитров
    print(f"\n5) Наложение субтитров:")
    print(f"   {Colors.GREEN}{Colors.BOLD}[1] Не накладывать{Colors.RESET} {Colors.GREEN}[По умолчанию]{Colors.RESET}")
    print(f"   [2] Наложить субтитры. Текст для субтитров будет взят из имени файла. Если в имени встретятся символы @, то вместо каждого такого символа будет сделан переход на новую строку в субтитрах")
    sub_choice = input(f"Ваш выбор [{Colors.GREEN}1{Colors.RESET}/2]: ").strip()
    subtitles_mode = (sub_choice == "2")

    # 6. Удаление звука
    print(f"\n6) Убрать звук:")
    print(f"   {Colors.GREEN}{Colors.BOLD}[1] Не убирать{Colors.RESET} {Colors.GREEN}[По умолчанию]{Colors.RESET}")
    print(f"   [2] Убрать. В этом случае из видео будет полностью удалена звуковая дорожка")
    audio_choice = input(f"Ваш выбор [{Colors.GREEN}1{Colors.RESET}/2]: ").strip()
    remove_audio = (audio_choice == "2")

    print(f"\n{Colors.GREEN}Параметры сжатия приняты:{Colors.RESET}")
    print(f"  • Целевой размер: {target_size_mb} МБ")
    print(f"  • Разрешение (меньшая сторона): {target_short_side}p")
    print(f"  • Кодек: {codec.upper()}")
    print(f"  • Режим: {passes_count} проход(а)")
    print(f"  • Субтитры: {'Да (из имени файла)' if subtitles_mode else 'Нет'}")
    print(f"  • Звук: {'Удалить' if remove_audio else 'Сохранить'}\n")

    return target_size_mb, target_short_side, codec, passes_count, subtitles_mode, remove_audio


def main():
    enable_windows_ansi()
    script_dir = Path.cwd()

    print(f"{Colors.BOLD}{Colors.CYAN}Запуск Video Compressor в папке:{Colors.RESET} {script_dir}\n")

    # 1. Проверка и подготовка FFmpeg
    ffmpeg_bin, ffprobe_bin = check_and_setup_ffmpeg()

    # 2. Поиск видеофайлов в текущей папке
    output_dir = script_dir / "compressed"
    video_files = [
        f for f in script_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not video_files:
        print(f"{Colors.YELLOW}В текущей папке ({script_dir}) не найдено поддерживаемых видеофайлов.{Colors.RESET}")
        print(f"Поддерживаемые форматы: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        input("\nНажмите Enter для выхода...")
        return

    print(f"{Colors.GREEN}Найдено видеофайлов для обработки:{Colors.RESET} {len(video_files)}")
    for i, vf in enumerate(video_files, 1):
        print(f"  {i}. {vf.name} ({format_size(vf.stat().st_size)})")
    print()

    # 3. Интерактивные настройки
    target_size_mb, target_short_side, codec, passes_count, subtitles_mode, remove_audio = prompt_user_settings()

    # 4. Создание папки для сжатых видео
    output_dir.mkdir(exist_ok=True)
    print(f"Сжатые файлы будут сохранены в: {Colors.CYAN}{output_dir}{Colors.RESET}")

    # 5. Обработка файлов
    successful = 0
    total_start_time = time.time()

    for idx, video_path in enumerate(video_files, 1):
        out_name = f"{video_path.stem}_compressed.mp4"
        out_path = output_dir / out_name

        info = get_video_info(ffprobe_bin, video_path)
        ok = compress_video(
            ffmpeg_path=ffmpeg_bin,
            input_file=video_path,
            output_file=out_path,
            target_size_mb=target_size_mb,
            target_short_side=target_short_side,
            codec=codec,
            passes_count=passes_count,
            subtitles_mode=subtitles_mode,
            remove_audio=remove_audio,
            file_index=idx,
            total_files=len(video_files),
            info=info
        )
        if ok:
            successful += 1

    total_elapsed = time.time() - total_start_time
    print(f"\n{Colors.BOLD}{Colors.GREEN}══════════════════════════════════════════════════════════════════{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}                     ОБРАБОТКА ЗАВЕРШЕНА!                        {Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}══════════════════════════════════════════════════════════════════{Colors.RESET}")
    print(f"Успешно сжато файлов: {Colors.BOLD}{successful} из {len(video_files)}{Colors.RESET}")
    print(f"Общее затраченное время: {Colors.BOLD}{format_seconds(total_elapsed)}{Colors.RESET}")
    print(f"Папка с результатами: {Colors.CYAN}{output_dir}{Colors.RESET}\n")

    input("Нажмите Enter для завершения...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Операция прервана пользователем.{Colors.RESET}")
        sys.exit(0)
