"""PreToolUse (Bash): pide confirmación antes de un `git push` a main.

Devuelve permissionDecision "ask" (no "deny"): el push directo a main sigue
siendo posible cuando de verdad lo quieres (p. ej. el paso final de
rama -> merge --ff-only -> push), pero nunca pasa en silencio por accidente.
Ver CLAUDE.md (regla: nunca push directo a main).
"""

import json
import re
import subprocess
import sys

PUSH_RE = re.compile(r"(^|[;&|\s])git\s+push\b")
MAIN_TARGET_RE = re.compile(r"push\b[^;&|]*\bmain\b|\bmain:")


def current_branch() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    cmd = (data.get("tool_input") or {}).get("command", "")
    if not PUSH_RE.search(cmd):
        return
    if current_branch() == "main" or MAIN_TARGET_RE.search(cmd):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "ask",
                        "permissionDecisionReason": (
                            "Esto hace push a main. Confírmalo solo si es intencionado "
                            "(normalmente: rama -> merge --ff-only -> push)."
                        ),
                    }
                }
            )
        )


if __name__ == "__main__":
    main()
