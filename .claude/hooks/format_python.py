"""PostToolUse (Write|Edit): formatea el .py editado con ruff y ordena imports.

No bloquea nada: si ruff falla, se ignora en silencio (el chequeo real es el
hook Stop y CI).
"""

import json
import os
import subprocess
import sys


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    tool_input = data.get("tool_input") or {}
    tool_response = data.get("tool_response") or {}
    file_path = tool_input.get("file_path") or tool_response.get("filePath") or ""
    if not file_path.endswith(".py") or not os.path.isfile(file_path):
        return
    for args in (
        ["-m", "ruff", "format", file_path],
        ["-m", "ruff", "check", "--fix", "--select", "I", file_path],
    ):
        try:
            subprocess.run([sys.executable, *args], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass


if __name__ == "__main__":
    main()
