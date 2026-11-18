@echo off
chcp 65001 >nul
rem Добавляет Миту в автозагрузку Windows
set "S=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\mita-claude.vbs"
> "%S%" echo CreateObject("WScript.Shell").Run "pythonw ""%~dp0mascot_overlay.py""", 0, False
echo Готово: Мита будет запускаться вместе с Windows.
pause
