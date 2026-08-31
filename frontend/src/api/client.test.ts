import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, LOGOUT_EVENT, tokenStore } from "./client";

describe("apiFetch", () => {
  beforeEach(() => {
    tokenStore.set("access-viejo", "refresh-1");
  });

  afterEach(() => {
    tokenStore.clear();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("renueva el access y reintenta cuando la primera respuesta es 401", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("", { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access: "access-nuevo" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const data = await apiFetch<{ ok: boolean }>("/api/nevera");

    expect(data).toEqual({ ok: true });
    expect(tokenStore.access).toBe("access-nuevo");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("limpia los tokens, avisa y lanza ApiError 401 si el refresh también falla", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("", { status: 401 }))
      .mockResolvedValueOnce(new Response("", { status: 401 }));
    vi.stubGlobal("fetch", fetchMock);

    const alSalir = vi.fn();
    window.addEventListener(LOGOUT_EVENT, alSalir);

    await expect(apiFetch("/api/nevera")).rejects.toBeInstanceOf(ApiError);
    expect(tokenStore.access).toBeNull();
    expect(alSalir).toHaveBeenCalledOnce();

    window.removeEventListener(LOGOUT_EVENT, alSalir);
  });

  it("propaga el 'detail' del backend en errores que no son 401", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Métrica desconocida." }), { status: 400 }),
      ),
    );

    await expect(apiFetch("/api/health/series?metric=x")).rejects.toMatchObject({
      status: 400,
      message: "Métrica desconocida.",
    });
  });
});
