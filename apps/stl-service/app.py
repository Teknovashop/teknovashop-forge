# app/app.py
import io
import os
import sys
import traceback
from typing import List, Optional, Callable, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

import trimesh
from trimesh.creation import box, cylinder

# ---- Supabase helpers (tuyos) ----
from supabase_client import upload_and_get_url

# ============================================================
#  Carga tolerante de REGISTRY desde apps/stl-service/models.py
#  (sin renombrar la carpeta con guion)
# ============================================================

def _load_registry() -> Dict[str, Callable]:
    """
    Intenta importar REGISTRY de:
      1) apps.stl_service.models (por si también existe)
      2) apps/stl-service/models.py mediante import por ruta
    Si falla, devuelve un REGISTRY local mínimo.
    """
    # 1) Intento normal (por si existe un espejo con underscore)
    try:
        from apps.stl_service.models import REGISTRY as REG_UNDERSCORE  # type: ignore
        return REG_UNDERSCORE
    except Exception:
        pass

    # 2) Importar por ruta absoluta sin depender del nombre del paquete
    try:
        import importlib.util
        base_dir = os.path.dirname(os.path.abspath(__file__))
        models_path = os.path.join(base_dir, "apps", "stl-service", "models.py")
        if os.path.isfile(models_path):
            spec = importlib.util.spec_from_file_location("stl_service_models", models_path)
            assert spec and spec.loader, "spec inválida al cargar models.py"
            mod = importlib.util.module_from_spec(spec)
            sys.modules["stl_service_models"] = mod
            spec.loader.exec_module(mod)  # type: ignore[attr-defined]
            if hasattr(mod, "REGISTRY") and isinstance(mod.REGISTRY, dict):
                return mod.REGISTRY  # type: ignore
    except Exception:
        # Logueamos, pero seguimos vivos
        print("[WARN] No se pudo importar REGISTRY de apps/stl-service/models.py")
        traceback.print_exc()

    # 3) REGISTRY local por defecto (tres modelos básicos)
    def _build_cable_tray(p: dict, holes: List[dict]) -> trimesh.Trimesh:
        L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
        solid = box(extents=(L, W, H))
        solid.apply_translation((0, 0, H / 2.0))
        return _apply_holes(solid, holes, L, H)

    def _build_vesa_adapter(p: dict, holes: List[dict]) -> trimesh.Trimesh:
        # Bloque más fino + taladros
        L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
        H = max(H, 5.0)
        solid = box(extents=(L, W, H))
        solid.apply_translation((0, 0, H / 2.0))
        return _apply_holes(solid, holes, L, H)

    def _build_router_mount(p: dict, holes: List[dict]) -> trimesh.Trimesh:
        # Base simple; luego taladros
        L, W, H = p["length_mm"], p["width_mm"], p["height_mm"]
        solid = box(extents=(L, W, H))
        solid.apply_translation((0, 0, H / 2.0))
        return _apply_holes(solid, holes, L, H)

    return {
        "cable_tray": _build_cable_tray,
        "vesa_adapter": _build_vesa_adapter,
        "router_mount": _build_router_mount,
    }

def _apply_holes(solid: trimesh.Trimesh, holes: List[dict], L: float, H: float) -> trimesh.Trimesh:
    """
    Aplica taladros verticales (desde la tapa superior). Usa boolean difference.
    Si Manifold3D no está, intentamos con trimesh; si tampoco, devolvemos la pieza sin taladrar.
    """
    # Intento con manifold3d si existe
    try:
        import manifold3d  # noqa: F401  # solo comprobación
        use_manifold = True
    except Exception:
        use_manifold = False
        print("[WARN] Boolean difference no disponible: No module named 'manifold3d'")

    for h in holes or []:
        d_mm = float(h.get("d_mm", 0) or 0)
        if d_mm <= 0:
            continue
        r = max(0.1, d_mm / 2.0)
        # UI manda x_mm en [0..L]; lo convertimos a coordenada centrada
        cx = float(h.get("x_mm", 0.0)) - (L / 2.0)
        cz = H  # perforando hacia abajo
        drill = cylinder(radius=r, height=max(H * 2.0, 50.0), sections=48)
        # Trimesh: cilindro a lo largo de Z y centrado en origen -> lo subimos
        drill.apply_translation((cx, 0.0, cz))

        try:
            if use_manifold and hasattr(solid, "difference"):
                # Si la lib Manifold está conectada a trimesh en tu entorno
                solid = solid.difference(drill)
            else:
                # Fallback de trimesh (puede requerir CGAL/SCAD; si falla seguimos)
                if hasattr(trimesh.interfaces, "scad") and trimesh.interfaces.scad.exists:
                    solid = solid.difference(drill, engine="scad")
                else:
                    solid = solid.difference(drill)
        except Exception:
            # No rompemos la generación por un taladro que falle
            print("[WARN] Falló un boolean difference; seguimos sin ese agujero.")
            traceback.print_exc()
    return solid

REGISTRY: Dict[str, Callable] = _load_registry()

# ============================================================
#               Config FastAPI + CORS
# ============================================================

CORS_ALLOW_ORIGINS = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o.strip()] or ["*"]
BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
PUBLIC_READ = os.getenv("SUPABASE_PUBLIC_READ", "0") == "1"
SIGNED_EXPIRES = int(os.getenv("SIGNED_URL_EXPIRES", "3600"))

class Hole(BaseModel):
    x_mm: float
    z_mm: float | None = 0
    d_mm: float

class Params(BaseModel):
    length_mm: float = Field(..., gt=0)
    width_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    thickness_mm: Optional[float] = Field(default=3, gt=0)

class GenerateReq(BaseModel):
    model: str = Field(..., description="cable_tray | vesa_adapter | router_mount | ...")
    params: Params
    holes: Optional[List[Hole]] = []

    @validator("holes", pre=True)
    def _coerce(cls, v):
        if v is None:
            return []
        out = []
        for h in v:
            out.append(
                {
                    "x_mm": float(h.get("x_mm", 0.0)),
                    "z_mm": float(h.get("z_mm", 0.0)),
                    "d_mm": float(h.get("d_mm", 0.0)),
                }
            )
        return out

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

def _export_stl(mesh_or_scene: trimesh.Trimesh | trimesh.Scene) -> bytes:
    data = mesh_or_scene.export(file_type="stl")
    return data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")

@app.post("/generate", response_model=GenerateRes)
def generate(req: GenerateReq):
    p = {
        "length_mm": req.params.length_mm,
        "width_mm": req.params.width_mm,
        "height_mm": req.params.height_mm,
        "thickness_mm": req.params.thickness_mm or 3.0,
    }

    # normalizamos nombres con guion/underscore
    model_key_variants = {
        req.model,
        req.model.replace("-", "_"),
        req.model.replace("_", "-"),
    }

    builder = None
    for k in model_key_variants:
        if k in REGISTRY:
            builder = REGISTRY[k]
            break
    if builder is None:
        # último intento: claves en lower
        for k in model_key_variants:
            kk = k.lower()
            if kk in REGISTRY:
                builder = REGISTRY[kk]
                break

    if builder is None:
        raise RuntimeError(f"Modelo desconocido: {req.model}. Disponibles: {', '.join(REGISTRY.keys())}")

    mesh = builder(p, req.holes or [])  # se espera un trimesh.Trimesh

    stl_bytes = _export_stl(mesh)
    buf = io.BytesIO(stl_bytes)
    buf.seek(0)

    # ruta en bucket: {model}/forge-output-{hash|timestamp}.stl (aquí simple y estable)
    object_key = f"{req.model}/forge-output.stl"
    url = upload_and_get_url(buf, object_key, bucket=BUCKET, public=PUBLIC_READ)

    return GenerateRes(stl_url=url, object_key=object_key)
