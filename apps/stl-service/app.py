# apps/stl-service/app.py
import io, os, math
from typing import List, Optional, Dict, Any, Iterable, Mapping, Callable

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import numpy as np
import trimesh

from supabase_client import upload_and_get_url

# Importar el registro real de modelos paramétricos
from models import REGISTRY as MODEL_REGISTRY  # apps/stl-service/models/__init__.py
from models.cable_tray import make_svg as cable_tray_make_svg

# -------------------------------------------------------
# Config
# -------------------------------------------------------
CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()] or ["*"]
BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
PUBLIC_READ = os.getenv("SUPABASE_PUBLIC_READ", "0") == "1"

# -------------------------------------------------------
# Pydantic
# -------------------------------------------------------
class Hole(BaseModel):
    x_mm: float = 0
    y_mm: float = 0
    d_mm: float = 0

class Params(BaseModel):
    length_mm: float = Field(..., gt=0)
    width_mm: float  = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    thickness_mm: float | None = Field(default=3, gt=0)
    fillet_mm: float | None = Field(default=0, ge=0)

class GenerateReq(BaseModel):
    model: str
    params: Params
    holes: List[Hole] | None = []
    outputs: List[str] | None = None
    operations: List[Dict[str, Any]] | None = None

class GenerateRes(BaseModel):
    stl_url: str
    object_key: str
    thumb_url: str | None = None
    svg_url: str | None = None

# -------------------------------------------------------
# Utils geom (operaciones universales)
# -------------------------------------------------------
def _as_mesh(obj: Any) -> trimesh.Trimesh | None:
    if isinstance(obj, trimesh.Trimesh):
        return obj
    if isinstance(obj, trimesh.Scene):
        return obj.dump(concatenate=True)
    return None

def _boolean_diff(a: trimesh.Trimesh, cutters: List[trimesh.Trimesh]) -> trimesh.Trimesh | None:
    try:
        from trimesh import boolean
        res = boolean.difference([a] + cutters, engine=None)
        m = _as_mesh(res)
        if m is not None:
            return m
    except Exception:
        pass
    # fallback iterativo
    cur = a
    for c in cutters:
        try:
            res = cur.difference(c)
            m = _as_mesh(res)
            if m is None: return None
            cur = m
        except Exception:
            return None
    return cur

def _mk_cutout_rect(x, y, w, h, L, W, depth, zc):
    from trimesh.creation import box
    cx = float(x) - L*0.5
    cy = float(y) - W*0.5
    d = max(depth, 0.1)
    m = box(extents=(max(0.1, float(w)), max(0.1, float(h)), d))
    m.apply_translation((cx, cy, zc))
    return m

def _mk_cutout_circle(x, y, d_mm, L, W, depth, zc):
    from trimesh.creation import cylinder
    r = max(0.05, (float(d_mm or 0.0) * 0.5))
    cx = float(x) - L*0.5
    cy = float(y) - W*0.5
    m = cylinder(radius=r, height=max(depth, 0.1), sections=64)
    m.apply_translation((cx, cy, zc))
    return m

def _text_to_mesh(text: str, size_mm: float, depth_mm: float) -> trimesh.Trimesh | None:
    try:
        from matplotlib.textpath import TextPath
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        from trimesh.creation import extrude_polygon

        tp = TextPath((0,0), text, size=size_mm)
        polys = tp.to_polygons(closed_only=True)
        solids = []
        for poly in polys:
            if len(poly) < 3: continue
            p = Polygon(poly).buffer(0)
            if p.is_empty: continue
            if p.geom_type == "Polygon":
                solids.append(extrude_polygon(p, height=depth_mm))
            else:
                u = unary_union(p)
                if u.geom_type == "Polygon":
                    solids.append(extrude_polygon(u, height=depth_mm))
                else:
                    for g in getattr(u, "geoms", []):
                        if g.geom_type == "Polygon":
                            solids.append(extrude_polygon(g, height=depth_mm))
        if not solids: return None
        try:
            from trimesh import boolean
            res = boolean.union(solids, engine=None)
            m = _as_mesh(res)
            if m is not None: return m
        except Exception:
            pass
        return trimesh.util.concatenate(solids)
    except Exception as e:
        print("[WARN] text_to_mesh:", e)
        return None

def _apply_operations(mesh: trimesh.Trimesh,
                      ops: List[Dict[str, Any]] | None,
                      L: float, W: float, H: float) -> trimesh.Trimesh:
    if not ops: return mesh
    cutters: List[trimesh.Trimesh] = []
    unions: List[trimesh.Trimesh] = []
    topZ = float(mesh.bounds[1][2])

    for op in ops:
        t = (op.get("type") or "").lower()
        if t == "cutout":
            shape = (op.get("shape") or "circle").lower()
            depth = float(op.get("depth_mm") or H)
            zc = topZ - depth * 0.5
            if shape == "rect":
                cutters.append(_mk_cutout_rect(op.get("x_mm",0), op.get("y_mm",0),
                                               op.get("w_mm",6), op.get("h_mm",6),
                                               L,W,depth,zc))
            else:
                cutters.append(_mk_cutout_circle(op.get("x_mm",0), op.get("y_mm",0),
                                                 op.get("d_mm",6), L,W,depth,zc))
        elif t == "array":
            shape = (op.get("shape") or "circle").lower()
            nx = max(1, int(op.get("nx") or 1)); ny=max(1, int(op.get("ny") or 1))
            dx = float(op.get("dx_mm") or 10); dy=float(op.get("dy_mm") or 10)
            start_x=float(op.get("start_x_mm") or 0); start_y=float(op.get("start_y_mm") or 0)
            depth=float(op.get("depth_mm") or H); zc=topZ-depth*0.5
            for ix in range(nx):
                for iy in range(ny):
                    x = start_x + ix*dx; y = start_y + iy*dy
                    if shape == "rect":
                        cutters.append(_mk_cutout_rect(x,y,op.get("w_mm",6),op.get("h_mm",10),L,W,depth,zc))
                    else:
                        cutters.append(_mk_cutout_circle(x,y,op.get("d_mm",6),L,W,depth,zc))
        elif t == "text":
            txt = str(op.get("text") or "").strip()
            if not txt: continue
            size = max(1.0, float(op.get("size_mm") or 10.0))
            depth = max(0.2, float(op.get("depth_mm") or 1.0))
            x = float(op.get("x_mm") or 0.0); y=float(op.get("y_mm") or 0.0)
            engrave = bool(op.get("engrave", True))
            m = _text_to_mesh(txt, size, depth)
            if m is not None:
                bb = m.bounds
                m.apply_translation((x - L*0.5 - bb[0][0], y - W*0.5 - bb[0][1], topZ - depth*0.5))
                if engrave: cutters.append(m)
                else: unions.append(m)

    if unions:
        try:
            from trimesh import boolean
            res = boolean.union([mesh] + unions, engine=None)
            m = _as_mesh(res)
            mesh = m if m is not None else trimesh.util.concatenate([mesh]+unions)
        except Exception:
            mesh = trimesh.util.concatenate([mesh] + unions)

    if cutters:
        diff = _boolean_diff(mesh, cutters)
        if diff is not None:
            mesh = diff

    return mesh

def _export_stl(mesh: trimesh.Trimesh) -> bytes:
    data = mesh.export(file_type="stl")
    return data if isinstance(data,(bytes,bytearray)) else str(data).encode("utf-8")

def _render_thumbnail(mesh: trimesh.Trimesh, width=900, height=600, bg=(245,246,248,255)) -> bytes:
    try:
        scene = trimesh.Scene(mesh)
        cam = trimesh.scene.cameras.Camera(resolution=(width,height), fov=(60,45))
        scene.camera = cam
        bounds = mesh.bounds
        center = bounds.mean(axis=0)
        ext = (bounds[1]-bounds[0]); diag=float(np.linalg.norm(ext)); diag=max(diag,1.0)
        distance = diag*1.8
        from trimesh.transformations import rotation_matrix, translation_matrix
        rot = rotation_matrix(math.radians(25), [1,0,0]) @ rotation_matrix(math.radians(-30), [0,0,1])
        pos = center + np.array([0.0, -distance, distance*0.6])
        view = np.linalg.inv(translation_matrix(pos) @ rot)
        scene.camera_transform = view
        img = scene.save_image(resolution=(width,height), background=bg)
        if isinstance(img,(bytes,bytearray)): return bytes(img)
    except Exception as e:
        print("[WARN] thumbnail:", e)
    return b""

# -------------------------------------------------------
# FastAPI
# -------------------------------------------------------
app = FastAPI(title="Teknovashop Forge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True, "models": list(MODEL_REGISTRY.keys())}

def _normalize_candidates(m: str) -> list[str]:
    m = (m or "").strip()
    return list({m, m.replace("-", "_"), m.replace("_","-"), m.lower(), m.lower().replace("-","_"), m.lower().replace("_","-")})

def _both_keys(canonical: str) -> tuple[str,str]:
    snake = canonical.replace("-","_"); kebab = canonical.replace("_","-")
    return snake, kebab

@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    if not req.model:
        raise HTTPException(status_code=400, detail="Modelo requerido")

    # Encontrar builder real en MODEL_REGISTRY
    builder: Callable[[Mapping[str,float], List[Mapping[str,Any]]], trimesh.Trimesh] | None = None
    chosen = None
    for k in _normalize_candidates(req.model):
        if k in MODEL_REGISTRY:
            builder = MODEL_REGISTRY[k]; chosen = k; break
    if builder is None:
        raise HTTPException(status_code=400, detail=f"Modelo desconocido: {req.model}. Disponibles: {', '.join(MODEL_REGISTRY.keys())}")

    # Adaptar parámetros esperados por los modelos (ellos suelen usar length/width/height/thickness/fillet)
    p = {
        "length": float(req.params.length_mm),
        "width": float(req.params.width_mm),
        "height": float(req.params.height_mm),
        "thickness": float(req.params.thickness_mm or 3.0),
        "fillet": float(req.params.fillet_mm or 0.0),
        # mantener compat por si algún modelo lee *_mm
        "length_mm": float(req.params.length_mm),
        "width_mm": float(req.params.width_mm),
        "height_mm": float(req.params.height_mm),
        "thickness_mm": float(req.params.thickness_mm or 3.0),
        "fillet_mm": float(req.params.fillet_mm or 0.0),
    }

    holes = [h.dict() if hasattr(h,'dict') else h for h in (req.holes or [])]
    mesh = builder(p, holes)

    # Operaciones universales del front
    try:
        mesh = _apply_operations(mesh, req.operations or [], p["length"], p["width"], p["height"])
    except Exception as e:
        print("[WARN] _apply_operations:", e)

    # Exportar STL y subir (snake y kebab)
    stl_bytes = _export_stl(mesh)
    snake, kebab = _both_keys(chosen or req.model)

    stl_key1 = f"{kebab}/forge-output.stl"
    url1 = upload_and_get_url(io.BytesIO(stl_bytes), stl_key1, bucket=BUCKET, public=PUBLIC_READ)
    try:
        stl_key2 = f"{snake}/forge-output.stl"
        _ = upload_and_get_url(io.BytesIO(stl_bytes), stl_key2, bucket=BUCKET, public=PUBLIC_READ)
    except Exception as e:
        print("[WARN] duplicate upload snake:", e)

    thumb_url = None
    try:
        png = _render_thumbnail(mesh)
        if png:
            thumb_key1 = f"{kebab}/thumbnail.png"
            thumb_url = upload_and_get_url(io.BytesIO(png), thumb_key1, bucket=BUCKET, public=PUBLIC_READ)
            try:
                thumb_key2 = f"{snake}/thumbnail.png"
                _ = upload_and_get_url(io.BytesIO(png), thumb_key2, bucket=BUCKET, public=PUBLIC_READ)
            except Exception as e:
                print("[WARN] duplicate thumb snake:", e)
    except Exception as e:
        print("[WARN] thumbnail gen:", e)

    svg_url = None
    try:
        want_svg = bool(req.outputs and any(o.lower()=='svg' for o in req.outputs))
        if want_svg and snake == "cable_tray":
            svg_text = cable_tray_make_svg(p, holes)
            if svg_text:
                svg_key1 = f"{kebab}/outline.svg"
                svg_url = upload_and_get_url(io.BytesIO(svg_text.encode('utf-8')), svg_key1, bucket=BUCKET, public=PUBLIC_READ)
                try:
                    svg_key2 = f"{snake}/outline.svg"
                    _ = upload_and_get_url(io.BytesIO(svg_text.encode('utf-8')), svg_key2, bucket=BUCKET, public=PUBLIC_READ)
                except Exception as e:
                    print("[WARN] duplicate svg snake:", e)
    except Exception as e:
        print("[WARN] svg gen:", e)

    return GenerateRes(stl_url=url1, object_key=stl_key1, thumb_url=thumb_url, svg_url=svg_url)

# Thumbnail endpoint (usa generate y devuelve la PNG)
class ThumbnailReq(BaseModel):
    model: str
    params: Params
    holes: List[Hole] | None = []

class ThumbnailRes(BaseModel):
    thumb_url: str
    object_key: str

@app.post("/thumbnail", response_model=ThumbnailRes)
def thumbnail(req: ThumbnailReq):
    gen = generate(GenerateReq(model=req.model, params=req.params, holes=req.holes))
    if not gen.thumb_url:
        raise HTTPException(status_code=500, detail="No se pudo generar la miniatura.")
    return ThumbnailRes(thumb_url=gen.thumb_url, object_key=gen.object_key.replace("forge-output.stl","thumbnail.png"))
