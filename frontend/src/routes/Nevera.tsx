import { useState } from "react";

import { ApiError } from "../api/client";
import { useBorrarItem, useEditarItem, useNevera } from "../api/hooks";
import type { NeveraItem, NeveraItemUpdate } from "../api/types";

const DIAS_ALERTA = 3;

function diasHasta(fecha: string | null): number | null {
  if (!fecha) return null;
  const ms = new Date(`${fecha}T00:00:00`).getTime() - Date.now();
  return Math.ceil(ms / 86_400_000);
}

/** Campos editables de una fila, ya como texto de formulario. */
interface Borrador {
  nombre: string;
  cantidad: string;
  unidad: string;
  categoria: string;
  fecha_caducidad: string;
  es_basico: boolean;
}

function aBorrador(item: NeveraItem): Borrador {
  return {
    nombre: item.nombre,
    cantidad: item.cantidad,
    unidad: item.unidad,
    categoria: item.categoria ?? "",
    fecha_caducidad: item.fecha_caducidad ?? "",
    es_basico: item.es_basico,
  };
}

/**
 * Solo lo que cambió: el endpoint es PATCH, no PUT.
 *
 * Mandar la fila entera funcionaría, pero pisaría en la BD cualquier cambio
 * que hubiera hecho el bot entre que cargamos la tabla y le damos a guardar.
 * Enviando el delta, esa carrera solo afecta a los campos que tocamos.
 */
function calcularCambios(original: NeveraItem, borrador: Borrador): NeveraItemUpdate {
  const cambios: NeveraItemUpdate = {};
  if (borrador.nombre !== original.nombre) cambios.nombre = borrador.nombre;
  if (borrador.categoria !== (original.categoria ?? "")) cambios.categoria = borrador.categoria;
  if (borrador.fecha_caducidad !== (original.fecha_caducidad ?? "")) {
    cambios.fecha_caducidad = borrador.fecha_caducidad || null;
  }
  if (borrador.es_basico !== original.es_basico) cambios.es_basico = borrador.es_basico;

  // Cantidad y unidad viajan juntas: el backend rechaza la unidad suelta
  // porque tiene que convertirlas a la vez a la unidad base.
  const cambioCantidad = Number(borrador.cantidad) !== Number(original.cantidad);
  const cambioUnidad = borrador.unidad !== original.unidad;
  if (cambioCantidad || cambioUnidad) {
    cambios.cantidad = borrador.cantidad;
    if (cambioUnidad) cambios.unidad = borrador.unidad;
  }
  return cambios;
}

/** Campo de texto sobre fondo oscuro: el relleno sube un escalón de elevación
 *  (--color-raised) en vez de bajar, que es como se lee "hueco" en oscuro. */
const INPUT =
  "w-full rounded border border-line bg-raised px-2 py-1 text-sm text-ink " +
  "focus:border-cyan focus:outline-none";

/** Botón secundario (Editar, Cancelar, No): contorno, sin relleno. */
const BOTON = "rounded border border-line px-2 py-1 text-xs text-ink-soft hover:text-ink";

export default function Nevera() {
  const { data, isLoading, isError } = useNevera();
  const editar = useEditarItem();
  const borrar = useBorrarItem();

  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [borrador, setBorrador] = useState<Borrador | null>(null);
  const [confirmandoId, setConfirmandoId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  function empezarEdicion(item: NeveraItem) {
    setError(null);
    setConfirmandoId(null);
    setEditandoId(item.id);
    setBorrador(aBorrador(item));
  }

  function cancelar() {
    setEditandoId(null);
    setBorrador(null);
    setError(null);
  }

  async function guardar(item: NeveraItem) {
    if (!borrador) return;
    const cambios = calcularCambios(item, borrador);
    if (Object.keys(cambios).length === 0) {
      cancelar();
      return;
    }
    setError(null);
    try {
      await editar.mutateAsync({ id: item.id, cambios });
      cancelar();
    } catch (e) {
      // El 409 de la constraint (nombre + unidad únicos) llega aquí con su
      // mensaje del backend; se enseña en vez de dejar la fila en silencio.
      setError(e instanceof ApiError ? e.message : "No se pudo guardar.");
    }
  }

  async function confirmarBorrado(id: number) {
    setError(null);
    try {
      await borrar.mutateAsync(id);
      setConfirmandoId(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "No se pudo borrar.");
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold tracking-tight text-ink">Nevera</h1>
      {isLoading && <p className="text-sm text-ink-muted">Cargando…</p>}
      {isError && <p className="text-sm text-coral">No se pudo cargar la nevera.</p>}
      {error && <p className="text-sm text-coral">{error}</p>}
      {data && data.length === 0 && <p className="text-sm text-ink-muted">La nevera está vacía.</p>}

      {data && data.length > 0 && (
        <div className="overflow-x-auto rounded-card bg-surface shadow-card">
          <table className="w-full text-sm">
            <thead className="border-b border-line bg-raised text-left text-xs uppercase text-ink-muted">
              <tr>
                <th className="px-3 py-2">Nombre</th>
                <th className="px-3 py-2">Cantidad</th>
                <th className="px-3 py-2">Categoría</th>
                <th className="px-3 py-2">Caduca</th>
                <th className="px-3 py-2">Básico</th>
                <th className="px-3 py-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {data.map((item) => {
                const enEdicion = editandoId === item.id;
                const dias = diasHasta(item.fecha_caducidad);
                const alerta = !item.es_basico && dias !== null && dias <= DIAS_ALERTA;

                if (enEdicion && borrador) {
                  return (
                    <tr key={item.id} className="border-b border-line bg-raised last:border-0">
                      <td className="px-3 py-2">
                        <input
                          className={INPUT}
                          aria-label="Nombre"
                          value={borrador.nombre}
                          onChange={(e) => setBorrador({ ...borrador, nombre: e.target.value })}
                        />
                      </td>
                      <td className="flex gap-1 px-3 py-2">
                        <input
                          className={INPUT}
                          aria-label="Cantidad"
                          type="number"
                          min="0"
                          step="any"
                          value={borrador.cantidad}
                          onChange={(e) => setBorrador({ ...borrador, cantidad: e.target.value })}
                        />
                        <input
                          className={`${INPUT} w-16`}
                          aria-label="Unidad"
                          value={borrador.unidad}
                          onChange={(e) => setBorrador({ ...borrador, unidad: e.target.value })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className={INPUT}
                          aria-label="Categoría"
                          value={borrador.categoria}
                          onChange={(e) => setBorrador({ ...borrador, categoria: e.target.value })}
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          className={INPUT}
                          aria-label="Caducidad"
                          type="date"
                          value={borrador.fecha_caducidad}
                          onChange={(e) =>
                            setBorrador({ ...borrador, fecha_caducidad: e.target.value })
                          }
                        />
                      </td>
                      <td className="px-3 py-2">
                        <input
                          aria-label="Básico de despensa"
                          type="checkbox"
                          checked={borrador.es_basico}
                          onChange={(e) => setBorrador({ ...borrador, es_basico: e.target.checked })}
                        />
                      </td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">
                        <button
                          className="rounded bg-cyan px-2 py-1 text-xs font-semibold text-navbar disabled:opacity-50"
                          onClick={() => void guardar(item)}
                          disabled={editar.isPending}
                        >
                          {editar.isPending ? "Guardando…" : "Guardar"}
                        </button>
                        <button
                          className={`ml-2 ${BOTON}`}
                          onClick={cancelar}
                          disabled={editar.isPending}
                        >
                          Cancelar
                        </button>
                      </td>
                    </tr>
                  );
                }

                return (
                  <tr key={item.id} className="border-b border-line last:border-0">
                    <td className="px-3 py-2">{item.nombre}</td>
                    <td className="px-3 py-2">
                      {item.cantidad} {item.unidad}
                    </td>
                    <td className="px-3 py-2 text-ink-muted">{item.categoria ?? "—"}</td>
                    <td
                      className={`px-3 py-2 ${
                        alerta ? "font-semibold text-coral" : "text-ink-muted"
                      }`}
                    >
                      {item.fecha_caducidad ?? "—"}
                      {alerta && dias !== null && (
                        <span className="ml-1">({dias <= 0 ? "caducado" : `${dias} d`})</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-ink-muted">{item.es_basico ? "Sí" : "—"}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-right">
                      {confirmandoId === item.id ? (
                        <>
                          <span className="mr-2 text-xs text-ink-muted">¿Seguro?</span>
                          <button
                            className="rounded bg-coral px-2 py-1 text-xs font-semibold text-navbar disabled:opacity-50"
                            onClick={() => void confirmarBorrado(item.id)}
                            disabled={borrar.isPending}
                          >
                            Sí, borrar
                          </button>
                          <button
                            className={`ml-2 ${BOTON}`}
                            onClick={() => setConfirmandoId(null)}
                          >
                            No
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            className={BOTON}
                            onClick={() => empezarEdicion(item)}
                          >
                            Editar
                          </button>
                          <button
                            className={`ml-2 ${BOTON} text-coral hover:text-coral`}
                            onClick={() => setConfirmandoId(item.id)}
                          >
                            Borrar
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
