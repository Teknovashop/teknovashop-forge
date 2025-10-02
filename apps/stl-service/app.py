# /app.py
import io
import os
import sys
import math
import traceback
from typing import List, Optional, Callable, Dict, Tuple, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import trimesh
from trimesh.creation import box, cylinder

# ---- Supabase helpers (tuyos) ----
from supabase_client import upload_and_get_url

# ============================================================
#                   Utiles comunes
# ============================================================

def _hole_get(h: Any, key: str, default: float = 0.0) -> float:
    """
    Lee un campo de un 'hole' que puede ser un dict o un BaseModel.
    """
    if isinstance(h, dict):
        v = h.get(key, default)
    else:
        v = getattr(h, key, default)
    try:
        return float(v if v is not None else default)
    except Exception:
        return float(default)


def _boolean_diff(a: trimesh.Trimesh, b: trimesh.Trimesh) -> Optional[trimesh.Trimesh]:
    """
    Boolean difference con distintos motores. Devuelve None si todos fallan.
    """
    # 1) Intento con Manifold si está enlazado a trimesh (algunas builds)
    try:
        res = a.difference(b)
        if isinstance(res, trimesh.Trimesh):
            return res
        # algunas veces devuelven Scene
        if isinstance(res, trimesh.Scene):
            return res.dump(concatenate=True)
    except Exception:
        pass

    # 2) Intento vía trimesh (puede requerir OpenSCAD, pero probamos)
    try:
        from trimesh import boolean
        res = boolean.difference([a, b], engine=None)  # que escoja engine
        if isinstance(res, trimesh.Trimesh):
            return res
        if isinstance(res, list) and len(res) > 0 and isinstance(res[0], trimesh.Trimesh):
            return trimesh.util.concatenate(res)
        if isinstance(res, trimesh.Scene):
            return res.dump(concatenate=True)
    except Exception:
        pass

    # 3) Nada
    return None


def _boolean_union(meshes: List[trimesh.Trimesh]) -> trimesh.Trimesh:
    """
    Union robusto con fallbacks. Si falla, concatena pura.
    """
    meshes = [m for m in meshes if isinstance(m, trimesh.Trimesh)]
    if not meshes:
        return trimesh.Trimesh()
    if len(meshes) == 1:
        return meshes[0]

    # 1) Manifold / trimesh.boolean
    try:
        from trimesh import boolean
        res = boolean.union(meshes, engine=None)
        if isinstance(res, trimesh.Trimesh):
            return res
        if isinstance(res, list) and len(res) > 0:
            return trimesh.util.concatenate(res)
        if isinstance(res, trimesh.Scene):
            return res.dump(concatenate=True)
    except Exception:
        pass

    # 2) Concatena (sin CSG)
    return trimesh.util.concatenate(meshes)


def _apply_top_holes(solid: trimesh.Trimesh, holes: List[Any], L: float, W: float, H: float) -> trimesh.Trimesh:
    """
    Aplica taladros pasantes desde la cara superior (Z+) con diámetro d_mm y
    coordenadas (x_mm, y_mm) en el plano superior (0..L, 0..W).
    Si todos los motores fallan, NO rompe: deja la pieza tal cual.
    """
    current = solid
    for h in holes or []:
        d_mm = _hole_get(h, "d_mm", 0.0)
        if d_mm <= 0:
            continue
        r = max(0.05, d_mm * 0.5)

        x_mm = _hole_get(h, "x_mm", 0.0)  # en el plano superior, de 0..L
        y_mm = _hole_get(h, "y_mm", 0.0)  # 0..W

        # Convertimos a coords centradas del mesh
        cx = x_mm - L * 0.5
        cy = y_mm - W * 0.5

        drill = cylinder(radius=r, height=max(H * 1.5, 20.0), sections=64)
        # En trimesh el cilindro por defecto está centrado en el origen y se extiende a lo largo de Z
        drill.apply_translation((cx, cy, H * 0.5))

        diff = _boolean_diff(current, drill)
        if diff is not None:
            current = diff
        else:
            # No paramos toda la pieza por un taladro fallido
            print("[WARN] No se pudo aplicar un agujero (CSG no disponible). Continuo…")

    return current


def _apply_rounding_if_possible(mesh: trimesh.Trimesh, fillet_mm: float) -> trimesh.Trimesh:
    """
    Intenta un “fillet/chaflán” aproximado. Con Manifold3D se puede simular
    con un pequeño offset negativo y positivo (dilate/erode).
    Si no hay Manifold o falla → deja el mesh sin fillet (pero no rompe).
    """
    r = float(fillet_mm or 0.0)
    if r <= 0.0:
        return mesh

    try:
        import manifold3d as m3d
        # Manifold: dilate(+) y erode(-) suavizan esquinas; con valores pequeños
        # se consigue un redondeo aproximado sin artefactos duros.
        man = m3d.Manifold(mesh)  # manifold acepta arrays o path STL; esta forma suele funcionar
        # estrategia: un “closing” morfológico: erode(-r) y luego dilate(+r)
        smooth = man.Erode(r).Dilate(r)
        out = smooth.to_trimesh()
        if isinstance(out, trimesh.Trimesh):
            return out
    except Exception:
        print("[INFO] Fillet ignorado (manifold3d no disponible o falló).")

    return mesh  # sin fillet, pero estable


def _export_stl(mesh_or_scene: trimesh.Trimesh | trimesh.Scene) -> bytes:
    data = mesh_or_scene.export(file_type="stl")
    return data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")


# ============================================================
#        MODELOS – cada uno DIFERENTE (no el mismo bloque)
# ============================================================

def mdl_cable_tray(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    """
    Bandeja de cables: caja hueca (paredes = thickness), abierta por arriba.
    """
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(1.0, float(p.get("thickness_mm") or 3.0))

    outer = box(extents=(L, W, H))
    outer.apply_translation((0, 0, H * 0.5))

    # “Hueco” interior (abrimos por arriba restando una caja que sobresale por Z+)
    inner = box(extents=(L - 2 * T, W - 2 * T, H + 2.0))
    inner.apply_translation((0, 0, H))  # empujado hacia arriba para abrir la tapa

    hollow = _boolean_diff(outer, inner) or outer

    # Agujeros en la base superior de las paredes (cara superior)
    hollow = _apply_top_holes(hollow, holes, L, W, H)
    return hollow


def mdl_vesa_adapter(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    """
    Placa VESA genérica con grosor y patrón 75/100 opcional por los 'holes'.
    """
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 4.0))
    H = max(H, T)

    plate = box(extents=(L, W, T))
    plate.apply_translation((0, 0, T * 0.5))

    # Agujeros VESA si el usuario los incluye (o cualquiera)
    plate = _apply_top_holes(plate, holes, L, W, T)
    return plate


def mdl_router_mount(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    """
    Soporte de router en L: dos placas unidas (fácil de imprimir).
    """
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 3.0))

    base = box(extents=(L, W, T))
    base.apply_translation((0, 0, T * 0.5))

    vertical = box(extents=(L, T, H))
    vertical.apply_translation((0, (W * 0.5 - T * 0.5), H * 0.5))

    mesh = _boolean_union([base, vertical])
    mesh = _apply_top_holes(mesh, holes, L, W, max(H, T))
    return mesh


def mdl_camera_mount(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    """
    Base rectangular con columna corta. Minimalista y distinto a los demás.
    """
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 3.0))

    base = box(extents=(L, W, T))
    base.apply_translation((0, 0, T * 0.5))

    col_h = min(max(H - T, 10.0), H)
    col = box(extents=(T * 2.0, T * 2.0, col_h))
    col.apply_translation((0, 0, T + col_h * 0.5))

    mesh = _boolean_union([base, col])
    mesh = _apply_top_holes(mesh, holes, L, W, T + col_h)
    return mesh


def mdl_wall_bracket(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    """
    Escuadra de pared: placa vertical + placa horizontal más ancha.
    """
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(3.0, float(p.get("thickness_mm") or 4.0))

    horiz = box(extents=(L, W, T))
    horiz.apply_translation((0, 0, T * 0.5))

    vert = box(extents=(T, W, H))
    vert.apply_translation((L * 0.5 - T * 0.5, 0, H * 0.5))

    mesh = _boolean_union([horiz, vert])
    mesh = _apply_top_holes(mesh, holes, L, W, max(H, T))
    return mesh


def mdl_desk_hook(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    """
    Gancho de escritorio: placa vertical + cilindro en voladizo como gancho.
    length_mm = alto, width_mm = fondo (saliente), height_mm = ancho útil de placa.
    """
    L, W, H = float(p["length_mm"]), float(p["width_mm"]), float(p["height_mm"])
    T = max(3.0, float(p.get("thickness_mm") or 4.0))

    # Placa vertical
    plate = box(extents=(H, T, L))        # (X=ancho, Y=grosor, Z=alto)
    plate.apply_translation((0, 0, L * 0.5))

    # Gancho cilíndrico (sale en Y+)
    r = max(6.0, W * 0.25)                # radio del gancho
    hook = cylinder(radius=r, height=H, sections=64)
    # Lo colocamos a media altura y sobresaliendo desde el centro
    hook.apply_translation((0, r, L * 0.5))

    mesh = _boolean_union([plate, hook])
    mesh = _apply_top_holes(mesh, holes, H, W, L)
    return mesh


def mdl_fan_guard(p: dict, holes: List[Any]) -> trimesh.Trimesh:
    """
    Rejilla de ventilador circular básica:
    - Disco fino (grosor T)
    - Dos barras cruzadas
    - Aro exterior de refuerzo
    length_mm se usa como diámetro.
    """
    D = float(p["length_mm"])
    T = max(2.0, float(p.get("thickness_mm") or 2.0))
    R = D * 0.5

    # Disco base
    disc = cylinder(radius=R * 0.95, height=T, sections=128)  # un pelín más pequeño para dejar aro
    disc.apply_translation((0, 0, T * 0.5))

    # Cruces
    bar_w = max(T * 2.0, D * 0.06)  # ancho de barra
    bar1 = box(extents=(D * 0.9, bar_w, T))
    bar2 = box(extents=(bar_w, D * 0.9, T))
    for b in (bar1, bar2):
        b.apply_translation((0, 0, T * 0.5))

    # Aro exterior
    ring_outer = cylinder(radius=R, height=T, sections=128)
    ring_inner = cylinder(radius=R * 0.85, height=T + 0.5, sections=128)  # hueco
    ring_inner.apply_translation((0, 0, -0.25))  # para evitar coplanares
    ring = _boolean_diff(ring_outer, ring_inner) or ring_outer
    ring.apply_translation((0, 0, T * 0.5))

    mesh = _boolean_union([disc, bar1, bar2, ring])
    # Agujeros opcionales: si el usuario quiere atornillar el guard
    mesh = _apply_top_holes(mesh, holes, D, D, T)
    return mesh


# Registro de modelos
REGISTRY: Dict[str, Callable[[dict, List[Any]], trimesh.Trimesh]] = {
    # originales
    "cable_tray": mdl_cable_tray,
    "vesa_adapter": mdl_vesa_adapter,
    "router_mount": mdl_router_mount,
    # nuevos
    "camera_mount": mdl_camera_mount,
    "wall_bracket": mdl_wall_bracket,
    "desk_hook": mdl_desk_hook,     # ✅ NUEVO
    "fan_guard": mdl_fan_guard,     # ✅ NUEVO
}

# ============================================================
#               FastAPI + modelos de request/response
# ============================================================

CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()] or ["*"]
BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
PUBLIC_READ = os.getenv("SUPABASE_PUBLIC_READ", "0") == "1"
SIGNED_EXPIRES = int(os.getenv("SIGNED_URL_EXPIRES", "3600"))


class Hole(BaseModel):
    x_mm: float = 0
    y_mm: float = 0
    d_mm: float = 0


class Params(BaseModel):
    length_mm: float = Field(..., gt=0)
    width_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    thickness_mm: Optional[float] = Field(default=3, gt=0)
    fillet_mm: Optional[float] = Field(default=0, ge=0)


class GenerateReq(BaseModel):
    model: str = Field(
        ...,
        description="cable_tray | vesa_adapter | router_mount | camera_mount | wall_bracket | desk_hook | fan_guard",
    )
    params: Params
    holes: Optional[List[Hole]] = []


class GenerateRes(BaseModel):
    stl_url: str
    object_key: str


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
    return {"ok": True, "models": list(REGISTRY.keys())}


@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    p = {
        "length_mm": req.params.length_mm,
        "width_mm": req.params.width_mm,
        "height_mm": req.params.height_mm,
        "thickness_mm": req.params.thickness_mm or 3.0,
        "fillet_mm": req.params.fillet_mm or 0.0,
    }

    # normalizamos nombres con guion/underscore/lower
    candidates = {
        req.model,
        req.model.replace("-", "_"),
        req.model.replace("_", "-"),
        req.model.lower(),
        req.model.lower().replace("-", "_"),
        req.model.lower().replace("_", "-"),
    }

    builder: Optional[Callable[[dict, List[Any]], trimesh.Trimesh]] = None
    for k in candidates:
        if k in REGISTRY:
            builder = REGISTRY[k]
            break
    if builder is None:
        raise RuntimeError(f"Modelo desconocido: {req.model}. Disponibles: {', '.join(REGISTRY.keys())}")

    # Construye la malla base
    mesh = builder(p, req.holes or [])

    # Fillet / chaflán aproximado si procede
    f = float(p.get("fillet_mm") or 0.0)
    if f > 0:
        mesh = _apply_rounding_if_possible(mesh, f)

    # Exportar a STL
    stl_bytes = _export_stl(mesh)
    buf = io.BytesIO(stl_bytes)
    buf.seek(0)

    # Guardar en Supabase (firma/ACL las maneja tu helper)
    object_key = f'{req.model.replace("_", "-")}/forge-output.stl'
    url = upload_and_get_url(buf, object_key, bucket=BUCKET, public=PUBLIC_READ)

    return GenerateRes(stl_url=url, object_key=object_key)
