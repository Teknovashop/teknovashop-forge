# app/app.py
import io
import os
import sys
import traceback
from typing import List, Optional, Callable, Dict, Any, Iterable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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


# ============================================================
#           Normalización robusta de agujeros
# ============================================================

def _hole_to_dict(h: Any) -> Dict[str, float]:
    """
    Normaliza un agujero a dict con claves x_mm, z_mm, d_mm.
    Acepta:
      - Objetos Pydantic v2 (model_dump)
      - Objetos Pydantic v1 (dict)
      - dicts
      - objetos con atributos x_mm / z_mm / d_mm
    """
    # Pydantic v2
    if hasattr(h, "model_dump"):
        d = h.model_dump()
    # Pydantic v1
    elif hasattr(h, "dict"):
        d = h.dict()
    elif isinstance(h, dict):
        d = h
    else:
        d = {
            "x_mm": getattr(h, "x_mm", 0),
            "z_mm": getattr(h, "z_mm", 0),
            "d_mm": getattr(h, "d_mm", 0),
        }

    return {
        "x_mm": float(d.get("x_mm", 0) or 0),
        "z_mm": float(d.get("z_mm", 0) or 0),
        "d_mm": float(d.get("d_mm", 0) or 0),
    }


def _normalize_holes(holes: Optional[Iterable[Any]]) -> List[Dict[str, float]]:
    if not holes:
        return []
    return [_hole_to_dict(h) for h in holes]


# ============================================================
#            Booleans: taladros a la pieza
# ============================================================

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

        # Si tu UI te da x_mm en coordenadas [0..L], centramos respecto al origen
        cx = float(h.get("x_mm", 0.0)) - (L / 2.0)

        # Perforamos hacia abajo desde la tapa superior (Z positiva)
        cz = H
        drill_height = max(H * 2.0, 50.0)

        drill = cylinder(radius=r, height=drill_height, sections=48)
        # El cilindro de trimesh va a lo largo de Z y centrado en el origen -> lo subimos
        drill.apply_translation((cx, 0.0, cz))

        try:
            if use_manifold and hasattr(solid, "difference"):
                solid = solid.difference(drill)
            else:
                # Fallback puro de trimesh
                if hasattr(trimesh.interfaces, "scad") and trimesh.interfaces.scad.exists:
                    solid = solid.difference(drill, engine="scad")
                else:
                    solid = solid.difference(drill)
        except Exception:
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


# Modelos de entrada/salida (ligeros)
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
    # Acepta objetos Hole o dicts, y evita lista mutable por defecto
    holes: Optional[List[Hole | Dict[str, Any]]] = Field(default_factory=list)


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

    # <<< ARREGLO CLAVE: normalizamos los agujeros venga lo que venga >>>
    holes_norm = _normalize_holes(req.holes)

    mesh = builder(p, holes_norm)  # se espera un trimesh.Trimesh

    stl_bytes = _export_stl(mesh)
    buf = io.BytesIO(stl_bytes)
    buf.seek(0)

    # ruta en bucket: {model}/forge-output-{hash|timestamp}.stl (aquí simple y estable)
    object_key = f"{req.model}/forge-output.stl"
    url = upload_and_get_url(buf, object_key, bucket=BUCKET, public=PUBLIC_READ)

    return GenerateRes(stl_url=url, object_key=object_key)
