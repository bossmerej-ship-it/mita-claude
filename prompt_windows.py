"""Bounded, hidden Windows UIA worker using the system PowerShell/.NET runtime."""

import atexit
import json
import os
import queue
import subprocess
import threading
from pathlib import Path

from prompt_detection import choose_prompt


class WindowsPromptReader:
    def __init__(self):
        self.process = None
        self.lines = None
        atexit.register(self.close)

    def close(self):
        process, self.process = self.process, None
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=1)
            process.stdin.close()

    def _start(self):
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        self.process = subprocess.Popen(
            [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(Path(__file__).with_suffix(".ps1"))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding="utf-8", creationflags=subprocess.CREATE_NO_WINDOW,
        )
        lines = self.lines = queue.Queue()
        stream = self.process.stdout

        def collect():
            try:
                for line in stream:
                    lines.put(line)
            finally:
                lines.put(None)
                stream.close()

        threading.Thread(target=collect, daemon=True).start()

    def __call__(self, handle):
        try:
            starting = self.process is None or self.process.poll() is not None
            if starting:
                self.close()
                self._start()
            self.process.stdin.write(json.dumps({"hwnd": int(handle)}) + "\n")
            self.process.stdin.flush()
            line = self.lines.get(timeout=8 if starting else 2)
            if line is None:
                raise OSError("UI Automation helper stopped")
            data = json.loads(line)
            window = data.get("window")
            return choose_prompt(data.get("candidates", []), window), window
        except (OSError, ValueError, queue.Empty):
            self.close()
            return None, None
