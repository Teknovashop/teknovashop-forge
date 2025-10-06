# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import os, io, uuid, tempfile
import numpy as np
import trimesh as tm

from supabase import create_client, Client

# ========= CORS =========
ALLOWED_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========= Supabase =========
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "forge-stl")
sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ========= Utils =========
def mesh_to_stl_bytes(mesh: tm.Trimesh) -> bytes:
    f = io.BytesIO()
    mesh.export(f, file_type="stl")
    return f.getvalue()

def upload_and_sign(bytes_data: bytes, folder: str, filename: str) -> Dict[str, Any]:
    key = f"{folder}/{filename}"
    # subimos
    sb.storage.from_(SUPABASE_BUCKET).upload(key, bytes_data, {
        "content-type": "model/stl",
        "upsert": True,
    })
    # firmamos 60 min
    signed = sb.storage.from_(SUPABASE_BUCKET).create_signed_url(key, 60*60)
    return {"key": key, "url": signed.get("signedURL")}

# ========= Modelos base =========
class ModelGenerator:
    slug: str = "base"

    def build(self, params: Dict[str, Any]) -> tm.Trimesh:
        raise NotImplementedError

# --- Modelos de ejemplo paramétricos ---

class VesaAdapter(ModelGenerator):
    """
    Placa con patrón de agujeros VESA configurable.
    params:
      width, height, thickness  -> dimensiones placa (mm)
      pattern_from, pattern_to  -> (ej. 75 y 100, o 100 y 200)
      hole_d                    -> diámetro agujero tornillo (mm)
    """
    slug = "vesa-adapter"

    def build(self, params: Dict[str, Any]) -> tm.Trimesh:
        w = float(params.get("width", 120))
        h = float(params.get("height", 120))
        t = float(params.get("thickness", 5))
        p_from = int(params.get("pattern_from", 75))
        p_to   = int(params.get("pattern_to", 100))
        hole_d = float(params.get("hole_d", 5))

        plate = tm.creation.box(extents=(w, h, t))
        plate.apply_translation([0, 0, t/2.0])

        def hole_grid(side):
            # genera 4 agujeros para un cuadrado de lado 'side' (mm)
            r = hole_d/2.0
            # cilindros están alineados en Z. Altura un poco mayor que la placa:
            cyl = tm.creation.cylinder(radius=r, height=t*1.2, sections=64)
            cyl.apply_translation([ side/2,  side/2, t/2])
            c2 = cyl.copy(); c2.apply_translation([-side, 0, 0])
            c3 = cyl.copy(); c3.apply_translation([0, -side, 0])
            c4 = cyl.copy(); c4.apply_translation([-side, -side, 0])
            return tm.util.concatenate([cyl, c2, c3, c4])

        holes_from = hole_grid(p_from)
        holes_to   = hole_grid(p_to)

        # situamos el centro geométrico en (0,0)
        plate.apply_translation([-w/2, -h/2, 0])

        # restamos
        result = plate.difference([holes_from, holes_to], engine="scad" if tm.interfaces.scad.exists else "blender")
        return result

class RouterMount(ModelGenerator):
    """
    Soporte en L (pared/estante).
    params: base_w, base_h, depth, thickness, hole_d
    """
    slug = "router-mount"

    def build(self, params: Dict[str, Any]) -> tm.Trimesh:
        base_w = float(params.get("base_w", 80))
        base_h = float(params.get("base_h", 100))
        depth  = float(params.get("depth", 60))
        t      = float(params.get("thickness", 4))
        hole_d = float(params.get("hole_d", 4))

        plate = tm.creation.box((base_w, base_h, t))
        plate.apply_translation([0, 0, t/2])

        shelf = tm.creation.box((base_w, t, depth))
        shelf.apply_translation([0, (base_h/2+t/2), depth/2])

        bracket = tm.util.concatenate([plate, shelf])
        bracket.apply_translation([-base_w/2, -base_h/2, 0])

        # dos agujeros en placa
        r = hole_d/2
        c1 = tm.creation.cylinder(r, t*1.4, sections=48); c1.apply_translation([  base_w/4, 0, t/2])
        c2 = tm.creation.cylinder(r, t*1.4, sections=48); c2.apply_translation([ -base_w/4, 0, t/2])

        result = bracket.difference([c1, c2], engine="scad" if tm.interfaces.scad.exists else "blender")
        return result

class CableTray(ModelGenerator):
    """
    Bandeja en U simple.
    params: width, depth, wall, height
    """
    slug = "cable-tray"

    def build(self, params: Dict[str, Any]) -> tm.Trimesh:
        w = float(params.get("width", 220))
        d = float(params.get("depth", 80))
        wall = float(params.get("wall", 4))
        h = float(params.get("height", 50))

        outer = tm.creation.box((w, d, h))
        inner = tm.creation.box((w-2*wall, d-wall, h-wall))
        inner.apply_translation([0, wall/2, wall/2])

        outer.apply_translation([-w/2, -d/2, 0])
        inner.apply_translation([-w/2, -d/2, 0])

        tray = outer.difference(inner, engine="scad" if tm.interfaces.scad.exists else "blender")
        return tray

# ========= Registro de modelos =========
REGISTRY: Dict[str, ModelGenerator] = {
    VesaAdapter.slug: VesaAdapter(),
    RouterMount.slug: RouterMount(),
    CableTray.slug:  CableTray(),
    # añade más aquí con el mismo patrón
}

# ========= Schemas =========
class GeneratePayload(BaseModel):
    model: str
    params: Dict[str, Any] = {}

# ========= Endpoints =========
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/generate")
def generate(payload: GeneratePayload):
    slug = payload.model.strip()
    gen = REGISTRY.get(slug)
    if not gen:
        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")

    try:
        mesh = gen.build(payload.params or {})
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Build error: {e}")

    stl_bytes = mesh_to_stl_bytes(mesh)
    custom_id = str(uuid.uuid4())[:8]
    filename = f"custom-{custom_id}.stl"

    # Guardamos en carpeta del modelo dentro del bucket
    uploaded = upload_and_sign(stl_bytes, slug, filename)
    return {"ok": True, "slug": slug, "file": uploaded["key"], "url": uploaded["url"]}
