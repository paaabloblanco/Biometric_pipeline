import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../lib/auth";

function linkClass({ isActive }: { isActive: boolean }) {
  return `rounded-md px-3 py-2 text-sm font-medium ${
    isActive ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"
  }`;
}

export default function Layout() {
  const { logout } = useAuth();
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <nav className="flex gap-1">
            <NavLink to="/" end className={linkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/analisis" className={linkClass}>
              Análisis
            </NavLink>
            <NavLink to="/nevera" className={linkClass}>
              Nevera
            </NavLink>
          </nav>
          <button
            onClick={logout}
            className="text-sm text-slate-500 hover:text-slate-900"
            type="button"
          >
            Salir
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
