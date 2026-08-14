@echo off
chcp 65001 > nul
title Build VideoCompressor.exe
python "%~dp0build_exe.py"
pause
