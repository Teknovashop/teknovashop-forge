# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, Optional
import os, uuid

import trimesh as tm
from trimesh.creation import box

from supabase import create_client, Client

# ---------- Config ----------
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl").strip()
CORS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()] or ["*"]

os.environ.setdefault("TRIMESH_NO_NETWORK", "1")
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")

app = FastAPI(title="Teknovashop Forge API")
app.add_middleware(CORSMiddleware, allow_origins=CORS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ---------- Supabase ----------
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
  supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def upload_and_sign(stl_bytes: bytes, folder: str, filename: str):
  if not supabase:
    raise RuntimeError("Supabase client not configured")
  key = f"{folder}/{filename}"
  supabase.storage.from_(SUPABASE_BUCKET).upload(key, stl_bytes, {"content-type": "model/stl", "upsert": True})
  public_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(key)
  return {"key": key, "url": public_url}

# ---------- Models ----------
def build_vesa_adapter(p: Dict[str, Any]) -> tm.Trimesh:
  L = float(p.get("length_mm", 120))
  W = float(p.get("width_mm", 100))
  T = float(p.get("thickness_mm", 3))
  plate = box(extents=(L, W, T)); plate.apply_translation((0, 0, T/2.0))
  return plate

def build_cable_tray(p: Dict[str, Any]) -> tm.Trimesh:
  L = float(p.get("length_mm", 120))
  W = float(p.get("width_mm", 60))
  H = float(p.get("height_mm", 40))
  T = float(p.get("thickness_mm", 2))
  outer = box(extents=(L, W, H)); outer.apply_translation((0, 0, H/2))
  inner = box(extents=(L-2*T, W-2*T, H)); inner.apply_translation((0, 0, H/2 + 0.01))
  try:
    return outer.difference(inner)
  except Exception:
    return outer

MODEL_REGISTRY = { "vesa_adapter": build_vesa_adapter, "cable_tray": build_cable_tray }
def mesh_to_stl_bytes(mesh: tm.Trimesh) -> bytes: return mesh.export(file_type="stl")

class GeneratePayload(BaseModel):
  model: str
  params: Dict[str, Any] = {}

@app.get("/health")
def health(): return {"ok": True}

@app.post("/generate")
def generate(payload: GeneratePayload):
  slug = payload.model.replace("-", "_")
  builder = MODEL_REGISTRY.get(slug)
  if not builder: raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")
  try:
    mesh = builder(payload.params or {})
  except Exception as e:
    raise HTTPException(status_code=400, detail=f"Build error: {e}")
  stl = mesh_to_stl_bytes(mesh)
  filename = f"{slug}-{uuid.uuid4().hex[:8]}.stl"
  uploaded = upload_and_sign(stl, slug, filename)
  return {"ok": True, "slug": slug, "file": uploaded["key"], "url": uploaded["url"]}
