# Teknovashop Forge (Backend)

Raíz del servicio en Render: `apps/stl-service`

## Variables de entorno (Render)
- `CORS_ALLOW_ORIGINS`: `https://teknovashop-app.vercel.app`
- `SUPABASE_URL`: URL del proyecto Supabase
- `SUPABASE_SERVICE_KEY`: Service key (server only)
- `SUPABASE_BUCKET`: `forge-stl`

## Comprobación
- `GET /health` -> `{ "status": "ok" }`
- `POST /generate` -> `{ "status": "ok", "stl_url": "<signed-url>" }`
