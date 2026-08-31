import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { login as apiLogin, LOGOUT_EVENT, tokenStore } from "../api/client";

interface AuthValue {
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [access, setAccess] = useState<string | null>(tokenStore.access);

  // El cliente HTTP avisa cuando el refresh caduca: sincronizamos el estado.
  useEffect(() => {
    const alSalir = () => setAccess(null);
    window.addEventListener(LOGOUT_EVENT, alSalir);
    return () => window.removeEventListener(LOGOUT_EVENT, alSalir);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    await apiLogin(username, password);
    setAccess(tokenStore.access);
  }, []);

  const logout = useCallback(() => {
    tokenStore.clear();
    setAccess(null);
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ isAuthenticated: access !== null, login, logout }),
    [access, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth se usó fuera de <AuthProvider>");
  return ctx;
}
