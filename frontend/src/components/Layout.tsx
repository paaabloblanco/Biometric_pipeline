import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../lib/auth";

/* El subrayado turquesa es un pseudo-elemento del propio enlace: así el
   indicador acompaña al ancho del texto sin medir nada en JS. */
function linkClass({ isActive }: { isActive: boolean }) {
  return [
    "relative px-1 py-4 text-sm font-medium transition-colors",
    "after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:rounded-full",
    isActive ? "text-white after:bg-cyan" : "text-white/55 hover:text-white after:bg-transparent",
  ].join(" ");
}

export default function Layout() {
  const { logout } = useAuth();
  // /dia/:fecha es el detalle de lo que resume el dashboard, así que la
  // pestaña sigue marcada: si no, la barra se queda sin ninguna activa y
  // pierdes la referencia de dónde estás.
  const enDetalleDeDia = useLocation().pathname.startsWith("/dia/");
  return (
    <div className="min-h-screen bg-canvas font-sans text-ink">
      <header className="bg-navbar">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6">
          <nav className="flex gap-7">
            <NavLink
              to="/"
              end
              className={({ isActive }) => linkClass({ isActive: isActive || enDetalleDeDia })}
            >
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
            className="rounded-lg px-3 py-1.5 text-sm text-white/55 transition-colors hover:bg-white/10 hover:text-white"
            type="button"
          >
            Salir
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">
        <Outlet />
      </main>
    </div>
  );
}
