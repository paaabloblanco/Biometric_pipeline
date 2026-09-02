import { useState } from "react";

import { ApiError } from "../api/client";
import { useAltaItems, useParseCompra } from "../api/hooks";
import type { ItemPropuesto } from "../api/types";
import { BOTON, BOTON_PRIMARIO, INPUT } from "../lib/ui";
import Card from "./Card";

/** Mismo tope que `MAX_COMPRA_CHARS` en el backend (nevera/parsing.py). */
const MAX_TEXTO = 4000;

/** Unidades que entiende `nevera/units.py`. Se ofrecen como desplegable en vez
 *  de campo libre: es la única lista cerrada del formulario, y una unidad que
 *  el backend no conozca es un 400 seguro. */
const UNIDADES = ["g", "kg", "ml", "l", "ud"];

function mensajeDeError(e: unknown, porDefecto: string): string {
  if (e instanceof ApiError) return e.message;
  return porDefecto;
}

/**
 * Alta de nevera con IA, en dos pasos (SDD-web fase 6.b).
 *
 * El flujo es el mismo que `/anadir` + `/confirmar` en Telegram, pero el
 * estado intermedio vive aquí, en React, y no en el servidor: `parse` no
 * guarda nada, así que las propuestas solo existen en esta pantalla hasta que
 * se confirman. Consecuencias buenas de eso: se pueden editar antes de
 * guardar, cerrar la pestaña no deja nada a medias, y dos pestañas abiertas no
 * se pisan la una a la otra.
 */
export default function AltaConIA() {
  const [texto, setTexto] = useState("");
  const [propuestas, setPropuestas] = useState<ItemPropuesto[] | null>(null);
  const parse = useParseCompra();
  const alta = useAltaItems();

  function interpretar() {
    alta.reset();
    parse.mutate(texto, { onSuccess: setPropuestas });
  }

  function descartar() {
    setPropuestas(null);
    parse.reset();
  }

  function editar(i: number, cambios: Partial<ItemPropuesto>) {
    setPropuestas((actual) =>
      actual!.map((item, idx) => (idx === i ? { ...item, ...cambios } : item)),
    );
  }

  function quitar(i: number) {
    setPropuestas((actual) => actual!.filter((_, idx) => idx !== i));
  }

  function confirmar() {
    alta.mutate(propuestas!, {
      onSuccess: () => {
        // Solo se limpia si el guardado fue bien: si falla, las propuestas
        // siguen en pantalla y no hay que volver a gastar una llamada a Gemini.
        setPropuestas(null);
        setTexto("");
        parse.reset();
      },
    });
  }

  return (
    <Card className="space-y-3 p-5">
      <div>
        <h2 className="text-sm font-semibold text-ink">Añadir con IA</h2>
        <p className="text-xs text-ink-muted">
          Pega la lista de la compra tal cual. Gemini la interpreta y te la enseña antes de guardar
          nada. Equivale a <code>/anadir</code> + <code>/confirmar</code> en Telegram.
        </p>
      </div>

      <textarea
        className={`${INPUT} font-mono`}
        rows={4}
        maxLength={MAX_TEXTO}
        placeholder="2 kg de pollo, leche entera 1L, tomates, aceite de oliva…"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        disabled={parse.isPending || alta.isPending}
      />

      <div className="flex items-center gap-3">
        <button
          className={BOTON_PRIMARIO}
          onClick={interpretar}
          disabled={parse.isPending || alta.isPending || !texto.trim()}
        >
          {parse.isPending ? "Interpretando…" : "Interpretar"}
        </button>
        {parse.isPending && (
          <span className="text-xs text-ink-muted">Gemini está leyendo la lista…</span>
        )}
        <span className="ml-auto text-xs text-ink-muted">
          {texto.length}/{MAX_TEXTO}
        </span>
      </div>

      {parse.isError && (
        <p className="text-sm text-coral">
          {mensajeDeError(parse.error, "No se pudo interpretar el texto.")}
        </p>
      )}
      {alta.isError && (
        <p className="text-sm text-coral">{mensajeDeError(alta.error, "No se pudo guardar.")}</p>
      )}
      {alta.isSuccess && !propuestas && (
        <p className="text-sm text-cyan">Añadido a la nevera. Lo tienes en la tabla de abajo.</p>
      )}

      {propuestas && (
        <div className="space-y-3 border-t border-line pt-3">
          <p className="text-xs text-ink-soft">
            Esto es lo que ha entendido. Corrige lo que haga falta antes de confirmar: las
            cantidades y las unidades se convierten al guardar (1 kg se guarda como 1000 g).
          </p>

          {propuestas.length === 0 ? (
            <p className="text-sm text-ink-muted">No queda ningún item que añadir.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-line text-left text-xs uppercase text-ink-muted">
                  <tr>
                    <th className="px-2 py-1">Nombre</th>
                    <th className="px-2 py-1">Cantidad</th>
                    <th className="px-2 py-1">Categoría</th>
                    <th className="px-2 py-1">Caduca</th>
                    <th className="px-2 py-1">Básico</th>
                    <th className="px-2 py-1" />
                  </tr>
                </thead>
                <tbody>
                  {propuestas.map((item, i) => (
                    // El índice como key es correcto aquí y no en general: esta
                    // lista solo se acorta (quitar una fila), nunca se reordena
                    // ni se inserta en medio, y los items no tienen id todavía
                    // porque no existen en la BD.
                    <tr key={i} className="border-b border-line last:border-0">
                      <td className="px-2 py-1">
                        <input
                          className={INPUT}
                          aria-label="Nombre"
                          value={item.nombre}
                          onChange={(e) => editar(i, { nombre: e.target.value })}
                        />
                      </td>
                      <td className="flex gap-1 px-2 py-1">
                        <input
                          className={INPUT}
                          aria-label="Cantidad"
                          type="number"
                          min="0"
                          step="any"
                          value={item.cantidad}
                          onChange={(e) => editar(i, { cantidad: e.target.value })}
                        />
                        <select
                          className={`${INPUT} w-20`}
                          aria-label="Unidad"
                          value={item.unidad}
                          onChange={(e) => editar(i, { unidad: e.target.value })}
                        >
                          {UNIDADES.map((u) => (
                            <option key={u} value={u}>
                              {u}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-2 py-1">
                        <input
                          className={INPUT}
                          aria-label="Categoría"
                          value={item.categoria ?? ""}
                          onChange={(e) => editar(i, { categoria: e.target.value || null })}
                        />
                      </td>
                      <td className="px-2 py-1">
                        <input
                          className={INPUT}
                          aria-label="Caducidad"
                          type="date"
                          value={item.fecha_caducidad ?? ""}
                          onChange={(e) => editar(i, { fecha_caducidad: e.target.value || null })}
                        />
                      </td>
                      <td className="px-2 py-1">
                        <input
                          aria-label="Básico de despensa"
                          type="checkbox"
                          checked={item.es_basico}
                          onChange={(e) => editar(i, { es_basico: e.target.checked })}
                        />
                      </td>
                      <td className="px-2 py-1 text-right">
                        <button className={BOTON} onClick={() => quitar(i)} title="Quitar del alta">
                          Quitar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex items-center gap-2">
            <button
              className={BOTON_PRIMARIO}
              onClick={confirmar}
              disabled={alta.isPending || propuestas.length === 0}
            >
              {alta.isPending ? "Guardando…" : `Confirmar (${propuestas.length})`}
            </button>
            <button className={BOTON} onClick={descartar} disabled={alta.isPending}>
              Descartar
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
