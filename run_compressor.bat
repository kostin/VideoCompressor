@echo off
chcp 65001 > nul
title Video Compressor
python "%~dp0compress_videos.py"
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Proizoshla oshibka pri zapuske python skripta. Ubedites', chto Python ustanovlen i dobavlen v PATH.
    pause
)
