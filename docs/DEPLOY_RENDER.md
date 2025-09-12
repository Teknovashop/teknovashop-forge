# Deploy in Render (Web Service + Background Worker)

## 0) Prereqs
- Repo en GitHub con esta estructura.
- Supabase listo (DB + bucket `forge-stl`).

## 1) Web Service: stl-service (FastAPI)
- Render → New → Web Service → Connect repo.
- Root Directory: `apps/stl-service`
- Build Command: *(vacío; se usa Dockerfile por defecto)*
- Start Command: *(vacío; el Dockerfile ya ejecuta uvicorn con $PORT)*
- Environment:
  - SUPABASE_URL = https://<your-ref>.supabase.co
  - SUPABASE_SERVICE_KEY = <service role key>
  - SUPABASE_BUCKET = forge-stl
  - WATERMARK_TEXT = Teknovashop
- Health Check Path: `/health`
- Deploy → Render te dará una URL pública.

## 2) Background Worker: job processor
- Render → New → Background Worker → Connect el mismo repo.
- Root Directory: `apps/stl-service`
- Build Command: *(vacío)*
- Start Command: `python worker.py`
- Environment: (las mismas que el Web Service)
- Deploy.

## 3) Flujo asíncrono (sin Stripe, para test)
- Tu frontend crea un `order` y una fila en `stl_jobs` con `status='queued'`.
- El Worker detecta la fila, genera el STL y sube a Storage. Marca `status='done'` y guarda `stl_path` (signed url).
- El frontend hace polling a `/api/job-status?id=<job_id>` o escucha Supabase Realtime sobre `stl_jobs` y cuando pase a `done` muestra botón “Descargar”.

## 4) Seguridad
- Bucket privado; entregas por Signed URL.
- Stripe webhook: valida firma HMAC y marca `orders.status='paid'` antes de encolar el job.

## 5) Optimización Three.js
- Usa `BufferGeometry` y evita recrear materiales/escena en cada change; actualiza solo vértices.
- Debounce 150–250ms en sliders.
- Para modelos pesados, genera preview a partir de parámetros (low-poly) y STL final en backend.