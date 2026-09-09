"""SessionStart: recuerda al usuario qué toca estudiar al empezar la sesión.

Lee `aprendizaje/` y muestra dos sugerencias: una sesión de recuperación
(`/recordar`) y el siguiente fichero de la lista de repaso (`/revisar`).

Muestra un mensaje al usuario (`systemMessage`) e inyecta el mismo estado en
el contexto del modelo (`additionalContext`) para que abra la sesión con esa
sugerencia en vez de esperar a que se la pidan. No bloquea nunca: si algo
falla, sale en silencio (un hook roto no debe impedir trabajar).
"""

import json
import os
import re
import sys

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
APRENDIZAJE = os.path.join(RAIZ, "aprendizaje")

# Las plantillas usan AAAA-MM-DD / YYYY-MM-DD como marcador; una entrada real
# lleva una fecha de verdad. Así distinguimos registro vacío de registro usado.
ENTRADA_REAL = re.compile(r"^##\s+\d{4}-\d{2}-\d{2}", re.MULTILINE)


def _leer(nombre: str) -> str:
    try:
        with open(os.path.join(APRENDIZAJE, nombre), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _contar_entradas(nombre: str) -> int:
    return len(ENTRADA_REAL.findall(_leer(nombre)))


def _siguiente_repaso() -> tuple[str | None, int, int]:
    """Devuelve (primera línea sin marcar, hechos, total) de repaso.md."""
    pendiente, hechos, total = None, 0, 0
    for linea in _leer("repaso.md").splitlines():
        marca = linea.strip()[:5]
        if marca == "- [ ]":
            total += 1
            if pendiente is None:
                pendiente = linea.strip()[5:].strip()
        elif marca == "- [x]":
            total += 1
            hechos += 1
    return pendiente, hechos, total


def main() -> None:
    conceptos = _contar_entradas("conceptos.md")
    errores = _contar_entradas("errores.md")
    pendiente, hechos, total = _siguiente_repaso()

    if not os.path.isdir(APRENDIZAJE):
        return

    lineas = ["📚 Aprendizaje"]
    if conceptos or errores:
        lineas.append(
            f"  /recordar  — repaso ({conceptos} conceptos, {errores} errores registrados)"
        )
    else:
        lineas.append("  /recordar  — registro vacío aún: hará el repaso sobre el repo")
    if pendiente:
        lineas.append(f"  /revisar   — siguiente ({hechos}/{total}): {pendiente}")
    else:
        lineas.append("  /revisar   — lista de repaso completa 🎉")

    mensaje = "\n".join(lineas)
    contexto = (
        "Estado del registro de aprendizaje al arrancar la sesión "
        f"(entradas: {conceptos} conceptos, {errores} errores; "
        f"repaso de ficheros: {hechos}/{total} hechos"
        + (f"; siguiente pendiente: {pendiente}" if pendiente else "; lista completa")
        + "). Si el usuario no trae una tarea concreta, ofrécele en UNA línea "
        "empezar por ahí (/recordar o /revisar). Si trae tarea, no insistas: "
        "no interrumpas su trabajo con esto."
    )

    print(
        json.dumps(
            {
                "systemMessage": mensaje,
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": contexto,
                },
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - un aviso roto no debe impedir arrancar
        sys.exit(0)
