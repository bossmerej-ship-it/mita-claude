#!/bin/bash
# Добавляет Миту в автозагрузку macOS (LaunchAgent). Убрать: удалить ~/Library/LaunchAgents/com.mita-claude.plist
cd "$(dirname "$0")"
DIR="$(pwd)"
PY="$(command -v python3)"
PLIST="$HOME/Library/LaunchAgents/com.mita-claude.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.mita-claude</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$DIR/mascot_overlay.py</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
</dict></plist>
PL
launchctl unload "$PLIST" 2>/dev/null; launchctl load "$PLIST"
echo "Готово: Мита будет запускаться при входе в систему."
