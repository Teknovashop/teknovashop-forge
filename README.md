
# Teknovashop Forge (FastAPI @ Render)

Servicio FastAPI que expone:
- `GET /health` → 200 OK
- `POST /generate` → Genera un STL de ejemplo, lo sube a Supabase Storage y devuelve una URL firmada.

## CORS

Se habilita en `apps/stl-service/asgi.py`. Define orígenes permitidos con `CORS_ALLOW_ORIGINS` (lista separada por comas), por ejemplo:

```
CORS_ALLOW_ORIGINS=https://teknovashop-app.vercel.app,https://*.vercel.app
```

## Variables de entorno (Render)

- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY` (service role)
- `SUPABASE_BUCKET` (p.ej. `forge-stl`)
- `WATERMARK_TEXT` (opcional)
- `CORS_ALLOW_ORIGINS` (p.ej. `https://teknovashop-app.vercel.app`)

## Docker

El `Dockerfile` arranca con:

```
CMD ["sh", "-c", "uvicorn asgi:app --host 0.0.0.0 --port ${PORT}"]
```

Asegúrate de que el **Root Directory** del servicio es `apps/stl-service`.
