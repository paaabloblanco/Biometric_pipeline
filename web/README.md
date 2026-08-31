# web/ — interfaz web (SPA React)

Segundo cliente del backend, junto al bot de Telegram. Consume la API DRF
(`api/`) del proyecto Django. Ver `docs/SDD-web.md`.

## Stack

Vite · React 18 · TypeScript · React Router · TanStack Query · Recharts ·
Tailwind CSS v4.

## Desarrollo

```bash
cd web
npm install
cp .env.example .env        # ajusta VITE_API_BASE_URL si hace falta
npm run dev                 # http://localhost:5173
```

El backend tiene que estar corriendo aparte:

```bash
DJANGO_ENV=dev venv/Scripts/python manage.py runserver   # http://localhost:8000
```

`dev.py` ya permite el origen `localhost:5173` en CORS.

## Comandos

```bash
npm run build       # tsc + vite build -> dist/
npm run typecheck   # solo tipos
npm run test        # vitest (lógica del cliente HTTP)
```

## Deploy (Vercel)

Proyecto de Vercel apuntando a `web/` (monorepo, decisión §7-A del SDD).
`vercel.json` fija build y el rewrite de SPA. Variable de entorno del proyecto:
`VITE_API_BASE_URL` = URL pública del backend.

## Iteración 1: solo lectura

Login + Dashboard (último día + gráficas de FC y sueño) + Análisis (histórico)
+ Nevera (tabla con alerta de caducidad). Las escrituras llegan en la
iteración 2 (SDD-web §8).
