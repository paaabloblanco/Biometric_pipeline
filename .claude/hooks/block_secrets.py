"""PreToolUse (Write|Edit): bloquea escrituras a ficheros de secretos.

Permite .env.example. Ver docs/SDD-web.md y CLAUDE.md (regla: nunca subir .env).
"""

import json
import os
import sys

PROTECTED_NAMES = {"credentials.json", "service_account.json"}
PROTECTED_SUFFIXES = (".pem", ".key")


def is_protected(basename: str) -> bool:
    if basename == ".env":
        return True
    if basename.startswith(".env.") and basename != ".env.example":
        return True
    if basename in PROTECTED_NAMES:
        return True
    return basename.endswith(PROTECTED_SUFFIXES)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    file_path = (data.get("tool_input") or {}).get("file_path", "")
    if file_path and is_protected(os.path.basename(file_path)):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            f"{os.path.basename(file_path)} está protegido por hook "
                            "(.claude/hooks/block_secrets.py). No se edita desde Claude; "
                            "usa .env.example para plantillas."
                        ),
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
