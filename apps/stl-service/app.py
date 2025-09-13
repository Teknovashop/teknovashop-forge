from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import os
import uuid
from typing import Dict, Any, Optional
from utils.storage import upload_to_supabase

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
app = FastAPI(title="Teknovashop Forge API", version="1.0.0")

# CORS desde env: "https://dominio1,https://dominio2"
raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
origins = [o for o in (raw_origins.split(",") if raw_origins else []) if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],  # si no pones variable, abre para depuración
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
WATERMARK_TEXT = os.getenv("WATERMARK_TEXT", "Teknovashop")


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class GenerateParams(BaseModel):
    width: Optional[int] = Field(default=180, ge=1)
    height: Optional[int] = Field(default=180, ge=1)
    thickness: Optional[int] = Field(default=6, ge=1)
    pattern: Optional[str] = Field(default="100x100")


class GeneratePayload(BaseModel):
    order_id: str
    model_slug: str
    params: GenerateParams = Field(default_factory=GenerateParams)
    license: str = Field(default="personal")


# -----------------------------------------------------------------------------
# Salud
# -----------------------------------------------------------------------------
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# -----------------------------------------------------------------------------
# Simulación/Generación STL (placeholder)
# -----------------------------------------------------------------------------
def generate_stl_locally(model_slug: str, params: Dict[str, Any], out_dir: str) -> str:
    """
    Aquí iría tu generación real de STL. Por ahora creamos un archivo .stl
    mínimo para probar el pipeline de subida a Supabase.
    """
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{model_slug}-{uuid.uuid4().hex}.stl"
    local_path = os.path.join(out_dir, filename)

    # STL ASCII mínimo (triángulo)
    stl = f"""solid {model_slug}
facet normal 0 0 0
  outer loop
    vertex 0 0 0
    vertex {params.get('width',180)} 0 0
    vertex 0 {params.get('height',180)} 0
  endloop
endfacet
endsolid {model_slug}
"""
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(stl)

    return local_path


# -----------------------------------------------------------------------------
# Endpoint principal
# -----------------------------------------------------------------------------
@app.post("/generate")
def generate(payload: GeneratePayload) -> Dict[str, Any]:
    """
    1) Genera STL local (placeholder)
    2) Sube a Supabase Storage
    3) Devuelve signed URL (1h)
    """
    try:
        # 1) Generar STL local
        tmp_dir = "/tmp/stl"
        local_stl_path = generate_stl_locally(
            payload.model_slug,
            payload.params.model_dump(),
            tmp_dir,
        )

        # 2) Clave destino en bucket
        key = f"{payload.order_id}/{payload.model_slug}.stl"

        # 3) Subir + generar signed URL
        signed_url = upload_to_supabase(
            local_path=local_stl_path,
            bucket=SUPABASE_BUCKET,
            key=key,
            content_type="model/stl",
            expires_sec=3600,  # 1 hora
        )

        if not signed_url:
            raise HTTPException(status_code=500, detail="No STL URL generated")

        return {
            "status": "ok",
            "stl_url": signed_url,
            "meta": {
                "watermark": WATERMARK_TEXT,
                "model_slug": payload.model_slug,
                "order_id": payload.order_id,
                "license": payload.license,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
