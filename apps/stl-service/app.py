# apps/stl-service/app.py
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- crea la app antes de incluir routers ---
app = FastAPI(title="STL Service")

# Lee orígenes permitidos desde env (Render → Environment)
raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()

if raw_origins == "*" or raw_origins == "":
    allow_origins = ["*"]
else:
    # admite lista separada por comas
    allow_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

# El middleware CORS DEBE ir antes de montar rutas/routers
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,       # p.ej. ["*"] o ["https://tu-vercel.vercel.app"]
    allow_credentials=True,
    allow_methods=["*"],               # importante para que preflight responda 200
    allow_headers=["*"],               # idem (Content-Type, Authorization, etc.)
    expose_headers=["Content-Disposition"],  # si descargas archivos
)

@app.get("/health")
def health():
    return {"status": "ok"}

# --- tu endpoint real ---
from pydantic import BaseModel
class GeneratePayload(BaseModel):
    order_id: str
    model_slug: str
    params: dict
    license: str

@app.post("/generate")
def generate(payload: GeneratePayload):
    # tu lógica real aquí – devuelvo mínimo válido
    return {"status": "ok", "stl_url": "https://example.com/fake.stl"}

# (opcional) si quieres ser ultra-explícito con preflight:
@app.options("/generate")
def options_generate():
    # Devolver 204 explícito para el preflight en esta ruta
    return {}
