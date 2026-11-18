@echo off
chcp 65001 >nul
rem Запускает Миту без окна консоли
start "" pythonw "%~dp0mascot_overlay.py"
