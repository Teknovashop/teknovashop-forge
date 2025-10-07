# apps/stl-service/app.py
import io
import os
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import trimesh

from models import MODEL_REGISTRY, available_model_slugs
from supabase_client import upload_and_get_url

# ---------------- Config ----------------
CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()] or ["*"]
BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
PUBLIC_READ = os.getenv("SUPABASE_PUBLIC_READ", "0") in ("1", "true", "True")

app = FastAPI(title="Teknovashop Forge (modular)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Schemas ----------------
class GenerateReq(BaseModel):
    slug: Optional[str] = None   # preferido
    model: Optional[str] = None  # compat antiguo
    params: Optional[Dict[str, Any]] = None
    object_key: Optional[str] = None

class GenerateRes(BaseModel):
    ok: bool
    model: str
    object_key: str
    url: Optional[str] = None
    # aliases (compat con front)
    key: Optional[str] = None
    file: Optional[str] = None
    path: Optional[str] = None

# ---------------- Utils ----------------
def _export_stl_bytes(mesh: trimesh.Trimesh) -> bytes:
    data = mesh.export(file_type="stl")
    return data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")

# ---------------- Endpoints ----------------
@app.get("/health")
def health():
    return {"ok": True, "models": available_model_slugs()}

@app.get("/models")
def list_models():
    return {"models": available_model_slugs()}

@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    slug = (req.slug or req.model or "").strip()
    if not slug:
        raise HTTPException(status_code=400, detail="Missing 'slug' in body")

    if slug not in MODEL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Modelo '{slug}' no disponible")

    entry = MODEL_REGISTRY[slug]
    defaults = entry.get("defaults") or {}
    make_fn = entry.get("make")
    if not callable(make_fn):
        raise HTTPException(status_code=500, detail=f"Modelo '{slug}' sin make()")

    params = {**defaults, **(req.params or {})}

    try:
        mesh = make_fn(params)
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError("El modelo no devolvió trimesh.Trimesh")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Build error: {e}")

    stl = _export_stl_bytes(mesh)
    buf = io.BytesIO(stl); buf.seek(0)

    object_key = req.object_key or f"{slug}/forge-output.stl"
    try:
        url = upload_and_get_url(buf, object_key, bucket=BUCKET, public=PUBLIC_READ)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {e}")

    return GenerateRes(
        ok=True,
        model=slug,
        object_key=object_key,
        url=url,
        key=object_key,
        file=object_key,
        path=object_key,
    )
