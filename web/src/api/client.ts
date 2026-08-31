// Cliente HTTP: añade el JWT de acceso, y si el backend responde 401 intenta
// renovar con el refresh token una sola vez antes de reintentar (SDD-web §5).

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

const ACCESS_KEY = "salud.access";
const REFRESH_KEY = "salud.refresh";

export const tokenStore = {
  get access(): string | null {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh(): string | null {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

/** Evento que dispara el cliente cuando la sesión deja de ser válida. */
export const LOGOUT_EVENT = "salud:logout";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function request(path: string, init: RequestInit, withAuth: boolean): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (withAuth && tokenStore.access) {
    headers.set("Authorization", `Bearer ${tokenStore.access}`);
  }
  return fetch(`${BASE}${path}`, { ...init, headers });
}

// Una única renovación en vuelo aunque varias peticiones fallen a la vez.
let refreshing: Promise<boolean> | null = null;

function tryRefresh(): Promise<boolean> {
  if (!tokenStore.refresh) return Promise.resolve(false);
  if (!refreshing) {
    refreshing = request(
      "/api/auth/refresh",
      { method: "POST", body: JSON.stringify({ refresh: tokenStore.refresh }) },
      false,
    )
      .then(async (res) => {
        if (!res.ok) return false;
        const data = (await res.json()) as { access: string };
        tokenStore.set(data.access);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res = await request(path, init, true);

  if (res.status === 401 && (await tryRefresh())) {
    res = await request(path, init, true);
  }

  if (res.status === 401) {
    tokenStore.clear();
    window.dispatchEvent(new Event(LOGOUT_EVENT));
    throw new ApiError(401, "Sesión expirada, vuelve a entrar.");
  }

  if (!res.ok) {
    const cuerpo = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(res.status, cuerpo?.detail ?? `Error ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function login(username: string, password: string): Promise<void> {
  const res = await request(
    "/api/auth/login",
    { method: "POST", body: JSON.stringify({ username, password }) },
    false,
  );
  if (!res.ok) {
    throw new ApiError(res.status, "Usuario o contraseña incorrectos.");
  }
  const data = (await res.json()) as { access: string; refresh: string };
  tokenStore.set(data.access, data.refresh);
}
