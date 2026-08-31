"""Stop: chequeo rápido de calidad al terminar una tarea.

Solo lint y formato (rápido, sin BD). Los tests y mypy van en CI y se lanzan a
mano (ver CLAUDE.md). No bloquea: solo muestra un aviso si algo está mal.
"""

import json
import subprocess
import sys

CHECKS = (
    ["-m", "ruff", "check", "."],
    ["-m", "ruff", "format", "--check", "."],
)


def main() -> None:
    problems = []
    for args in CHECKS:
        try:
            r = subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode != 0:
            label = " ".join(args[1:])
            problems.append(f"$ python {label}\n{(r.stdout + r.stderr).strip()}")

    if problems:
        msg = "Calidad (hook Stop) — revisa antes de commitear:\n\n" + "\n\n".join(problems)
        print(json.dumps({"systemMessage": msg[:1800]}))


if __name__ == "__main__":
    main()
