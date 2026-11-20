#!/bin/bash
# Запускает Миту на macOS. Двойной клик по этому файлу (или: bash start_mac.command).
cd "$(dirname "$0")"
if ! python3 -c "import Quartz, AppKit" 2>/dev/null; then
  echo "Ставлю pyobjc (один раз, бесплатно)..."
  python3 -m pip install --user pyobjc-framework-Quartz pyobjc-framework-Cocoa || exit 1
fi
if ! python3 -c "import tkinter" 2>/dev/null; then
  echo "В этом Python нет tkinter. Поставь Python с python.org (или: brew install python-tk)."
  read -n 1 -s -r -p "Нажми любую клавишу..."; exit 1
fi
pkill -f "mascot_overlay.py" 2>/dev/null
nohup python3 mascot_overlay.py >>mita.log 2>&1 &
sleep 6
echo "----- mita.log -----"
tail -n 25 mita.log
echo "--------------------"
if kill -0 $! 2>/dev/null; then
  echo "Мита работает. Открой Claude или ChatGPT/Codex. Это окно можно закрыть."
else
  echo "Мита не запустилась. Сфоткай текст выше и пришли."
fi
read -n 1 -s -r -p "Нажми любую клавишу, чтобы закрыть..."
