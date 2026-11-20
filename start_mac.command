#!/bin/bash
# Запускает Миту на macOS. Двойной клик по этому файлу.
cd "$(dirname "$0")"
if ! python3 -c "import Quartz, AppKit" 2>/dev/null; then
  echo "Ставлю pyobjc (один раз, бесплатно)..."
  python3 -m pip install --user pyobjc-framework-Quartz pyobjc-framework-Cocoa || exit 1
fi
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "В этом Python нет tkinter. Поставь Python с python.org (или: brew install python-tk)."
  read -n 1 -s -r -p "Нажми любую клавишу..."; exit 1
fi
nohup python3 mascot_overlay.py >/dev/null 2>&1 &
echo "Мита запущена. Это окно можно закрыть."
