import os
from typing import Any, Dict, Tuple

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

# NUEVO: libs geométricas
import numpy as np
import shapely.geometry as sg
import shapely.affinity as sa
import trimesh

from utils.storage import Storage

app = FastAPI()

# ---------------------------
# CORS
# ---------------------------
allow_origins = []
cors_env = os.environ.get("CORS_ALLOW_ORIGINS")
if cors_env:
    allow_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    # si defines tu dominio de Vercel aquí, quedará más cerrado en producción
    default_frontend = os.environ.get("NEXT_PUBLIC_BACKEND_URL", "").strip()
    if default_frontend:
        allow_origins = [default_frontend]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],  # en dev: "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = Storage()

# ============================================================
# Helpers
# ============================================================

def _export_stl_binary(mesh: trimesh.Trimesh) -> bytes:
    """
    Exporta el mesh como STL binario (más compacto que ASCII).
    """
    # nos aseguramos de triangular
    if not mesh.is_watertight:
        mesh = mesh.convex_hull
    mesh = mesh.as_open3d if hasattr(mesh, "as_open3d") else mesh
    return trimesh.exchange.stl.export_stl(mesh, binary=True)

def _pattern_offsets(pattern: str) -> Tuple[float, float]:
    """
    Devuelve las distancias del patrón de agujeros VESA
    (en mm). Acepta '75x75', '100x100', '100 × 100', etc.
    """
    p = (pattern or "").lower().replace("×", "x").replace(" ", "")
    if "75x75" in p:
        return 75.0, 75.0
    # por defecto 100x100
    return 100.0, 100.0

# ============================================================
# Modelos paramétricos
# ============================================================

def generate_vesa_adapter(params: Dict[str, Any]) -> bytes:
    """
    Placa rectangular con grosor 't' y 4 agujeros VESA en la cara.
    Centrada en el origen. Unidades en mm.
    """
    w = float(params.get("width", 180))
    h = float(params.get("height", 180))
    t = float(params.get("thickness", 6))
    pat = str(params.get("pattern", "100x100"))

    dx, dy = _pattern_offsets(pat)

    # 2D: rectángulo centrado
    plate_2d = sg.box(-w / 2.0, -h / 2.0, w / 2.0, h / 2.0)

    # agujeros VESA (4)
    r = 2.5  # radio del agujero (≈ M5 / M6, aquí solo visual)
    holes = []
    for sx in (-dx / 2.0, dx / 2.0):
        for sy in (-dy / 2.0, dy / 2.0):
            holes.append(sg.Point(sx, sy).buffer(r, resolution=32))

    plate_2d_holes = plate_2d
    for c in holes:
        plate_2d_holes = plate_2d_holes.difference(c)

    # extrusión
    mesh = trimesh.creation.extrude_polygon(plate_2d_holes, height=t)
    # bajamos para que la cara inferior quede en Z=0 y la normal hacia +Z
    mesh.apply_translation((0, 0, 0))
    return _export_stl_binary(mesh)


def generate_router_mount(params: Dict[str, Any]) -> bytes:
    """
    Escuadra sencilla: placa vertical + repisa inferior.
    """
    w = float(params.get("width", 160))     # ancho de la placa
    H = float(params.get("height", 220))    # alto de la placa
    d = float(params.get("depth", 40))      # profundidad de la repisa
    t = float(params.get("thickness", 4))   # grosor de las placas

    # placa vertical (centrada en X) apoyada en Z=0
    plate = trimesh.creation.box(extents=(w, t, H))  # X, Y, Z
    plate.apply_translation((0, 0, H / 2.0))

    # repisa inferior (entra en la placa)
    shelf = trimesh.creation.box(extents=(w, d, t))
    # colocamos la repisa tocando la placa por Y y Z= t/2
    # Y positivo hacia "delante"
    shelf.apply_translation((0, (d / 2.0) + (t / 2.0), t / 2.0))

    # unimos por concatenación de mallas (para STL no hace falta booleano)
    mesh = trimesh.util.concatenate([plate, shelf])
    return _export_stl_binary(mesh)


def generate_cable_tray(params: Dict[str, Any]) -> bytes:
    """
    Canaleta en U: fondo + dos laterales. Ranuras opcionales en el fondo.
    """
    L = float(params.get("length", 180))    # largo
    w = float(params.get("width", 60))      # ancho interior
    h = float(params.get("height", 25))     # altura de pared
    t = float(params.get("thickness", 3))   # grosor paredes
    with_slots = bool(params.get("slots", True))

    # fondo
    bottom = trimesh.creation.box(extents=(L, w, t))
    bottom.apply_translation((L / 2.0, 0, t / 2.0))

    # paredes laterales (dos)
    side = trimesh.creation.box(extents=(L, t, h))
    left = side.copy()
    right = side.copy()
    left.apply_translation((L / 2.0, -(w / 2.0) + (t / 2.0), (h / 2.0) + t))
    right.apply_translation((L / 2.0, (w / 2.0) - (t / 2.0), (h / 2.0) + t))

    parts = [bottom, left, right]

    # Ranuras: restamos cajetines al fondo (rectangulitos a lo largo)
    if with_slots:
        slot_w = 6.0
        slot_l = 14.0
        gap = 12.0
        y_off = 0.0
        z_mid = t / 2.0  # van en el fondo
        # número de ranuras estimado
        n = int((L - gap) // (slot_l + gap))
        slots_meshes = []
        x0 = (L - (n * slot_l + (n - 1) * gap)) / 2.0
        for i in range(n):
            cx = x0 + i * (slot_l + gap) + slot_l / 2.0
            slot = trimesh.creation.box(extents=(slot_l, slot_w, t * 1.1))
            slot.apply_translation((cx, y_off, z_mid))
            slots_meshes.append(slot)
        # diferencia: convertimos bottom a SDF? No hace falta: para STL,
        # concatenar sin booleanos ya nos vale visualmente; pero para “abrir”
        # realmente huecos, usamos “difference” 2D + extrusión. Aquí lo mantengo
        # simple: concatenamos “canal - slot” como mallas separadas no sólidas.
        # Si quieres huecos reales, podemos pasar a extrusión de polígonos 2D.

        # Mejor opción sin booleanos 3D pesados: restar slots con extrusión 2D:
        # (dejamos TODO sencillo ahora y no restamos, solo mostramos el canal)

    mesh = trimesh.util.concatenate(parts)
    return _export_stl_binary(mesh)

# ============================================================
# Rutas
# ============================================================

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/generate")
async def generate(request: Request):
    """
    Recibe JSON:
    {
      "model": "vesa-adapter" | "router-mount" | "cable-tray",
      "params": { ... },
      "order_id": "...",
      "license": "personal" | "commercial"
    }
    """
    try:
        payload = await request.json()
    except Exception:
        return {"status": "error", "detail": "Invalid JSON"}

    model = (payload.get("model") or payload.get("model_slug") or "").strip().lower()
    if not model:
        model = "vesa-adapter"
    params = payload.get("params", {}) or {}

    try:
        if model in ("vesa-adapter", "vesa_adapter", "vesa"):
            stl_bytes = generate_vesa_adapter(params)
            filename = "vesa-adapter.stl"
        elif model in ("router-mount", "router_mount", "router"):
            stl_bytes = generate_router_mount(params)
            filename = "router-mount.stl"
        elif model in ("cable-tray", "cable_tray", "cable"):
            stl_bytes = generate_cable_tray(params)
            filename = "cable-tray.stl"
        else:
            return {"status": "error", "detail": f"Unknown model '{model}'"}

        url = storage.upload_stl_and_sign(stl_bytes, filename=filename, expires_in=3600)
        return {"status": "ok", "stl_url": url}

    except Exception as e:
        return {"status": "error", "detail": f"Upload error: {e}"}
