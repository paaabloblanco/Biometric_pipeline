# frontend/ — interfaz web (SPA React)

Segundo cliente del backend, junto al bot de Telegram. Consume la API DRF
(`backend/api/`) del proyecto Django. Ver `docs/SDD-web.md`.

## Stack

Vite · React 18 · TypeScript · React Router · TanStack Query · Recharts ·
Tailwind CSS v4.

## Desarrollo

```bash
cd frontend
npm install
cp .env.example .env        # ajusta VITE_API_BASE_URL si hace falta
npm run dev                 # http://localhost:5173
```

El backend tiene que estar corriendo aparte:

```bash
cd backend && DJANGO_ENV=dev venv/Scripts/python manage.py runserver   # http://localhost:8000
```

`dev.py` ya permite el origen `localhost:5173` en CORS.

## Comandos

```bash
npm run build       # tsc + vite build -> dist/
npm run typecheck   # solo tipos
npm run test        # vitest (lógica del cliente HTTP)
```

## Deploy (Vercel)

Proyecto de Vercel con **Root Directory = `frontend`** (monorepo, decisión §7-A del SDD).
`vercel.json` fija build y el rewrite de SPA. Variable de entorno del proyecto:
`VITE_API_BASE_URL` = URL pública del backend.

> ⚠️ Vite **incrusta** `VITE_API_BASE_URL` en el bundle **en tiempo de build**, no
> la lee en runtime. Cambiar la variable en Vercel **no surte efecto hasta
> redesplegar**. Si el valor queda vacío, `client.ts` cae a `""`, la SPA se llama
> a sí misma y el login devuelve **405** (el hosting estático solo sirve GET).

### Prueba end-to-end con túnel (sin desplegar el backend)

Para validar la SPA ya desplegada contra el backend local, sin hosting todavía.
Es una prueba puntual: la URL del túnel gratuito cambia en cada arranque.

```bash
# 1) Túnel: expone el runserver local en una URL pública temporal
cloudflared tunnel --url http://localhost:8000     # -> https://<algo>.trycloudflare.com

# 2) Backend, autorizando el túnel y el dominio de Vercel (PowerShell)
cd backend
$env:DEV_EXTRA_ALLOWED_HOSTS = ".trycloudflare.com"   # comodín: sirve para cualquier túnel
$env:DEV_EXTRA_CORS_ORIGINS  = "https://<tu-proyecto>.vercel.app"
venv\Scripts\python.exe manage.py runserver
```

3. En Vercel: `VITE_API_BASE_URL` = la URL del túnel (**sin barra final**).
4. **Redesplegar** (ver aviso de arriba). Cada push a `main` despliega solo.

Verificar la cadena antes de tocar el navegador (`curl` no aplica CORS, así que
aísla los fallos de backend de los de navegador):

```bash
curl -i https://<algo>.trycloudflare.com/api/nevera            # 401 => túnel + ALLOWED_HOSTS OK
curl -i -X POST -H "Content-Type: application/json" -d '{}' \
     https://<algo>.trycloudflare.com/api/auth/login           # 400 (no 405) => la ruta acepta POST

# CORS: la cabecera solo debe aparecer con el Origin autorizado
curl -sD - -o /dev/null -H "Origin: https://<tu-proyecto>.vercel.app" \
     https://<algo>.trycloudflare.com/api/nevera | grep -i access-control
```

## Iteración 1: solo lectura

Login + Dashboard (último día + gráficas de FC y sueño) + Análisis (histórico)
+ Nevera (tabla con alerta de caducidad). Las escrituras llegan en la
iteración 2 (SDD-web §8).
