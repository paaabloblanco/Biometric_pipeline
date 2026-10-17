import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth";

/** Campo de texto sobre fondo oscuro: el relleno sube un escalón de elevación
 *  (--color-raised) en vez de bajar, que es como se lee "hueco" en oscuro. */
const INPUT =
  "w-full rounded-md border border-line bg-raised px-3 py-2 text-sm text-ink " +
  "placeholder:text-ink-muted focus:border-cyan focus:outline-none";

export default function Login() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo entrar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4 font-sans text-ink">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-card bg-surface p-6 shadow-card"
      >
        <h1 className="text-lg font-semibold text-ink">Entrar</h1>
        <input
          className={INPUT}
          placeholder="Usuario"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
        />
        <input
          className={INPUT}
          placeholder="Contraseña"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error && <p className="text-sm text-coral">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-cyan py-2 text-sm font-semibold text-navbar transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </div>
  );
}
