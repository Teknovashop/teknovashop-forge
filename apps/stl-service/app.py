from __future__ import annotations

import io
import os
import inspect
import importlib
import sys
import traceback
import types
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple, List, Callable, Literal

import trimesh
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models import REGISTRY, ALIASES  # registro dinámico + alias para slugs
from supabase_client import upload_and_get_url  # subida + URL firmada

# -------------------------------------------------------------------
# Parches de compatibilidad (evitan errores en modelos antiguos)
# -------------------------------------------------------------------

# 1) Algunos modelos llaman .apply_rotation(matrix) (no existe en últimas versiones)
if not hasattr(trimesh.Trimesh, "apply_rotation"):
    def _apply_rotation(self, matrix):
        import numpy as _np
        M = _np.eye(4, dtype=float)
        mat = _np.asarray(matrix, dtype=float)
        try:
            if mat.shape == (4, 4):
                M = mat
            elif mat.shape == (3, 3):
                M[:3, :3] = mat
            else:
                M[:3, :3] = mat
        except Exception:
            pass
        self.apply_transform(M)
    trimesh.Trimesh.apply_rotation = _apply_rotation  # monkey-patch


# 2) Algunos modelos usan trimesh.interfaces.scad. En contenedores suele no estar.
#    Inyectamos un shim que usa trimesh.boolean o degradamos a concat.
def _normalize_mesh_list(args):
    lst = []
    for a in args:
        if a is None:
            continue
        if isinstance(a, (list, tuple)):
            for x in a:
                if isinstance(x, trimesh.Trimesh):
                    lst.append(x)
        elif isinstance(a, trimesh.Trimesh):
            lst.append(a)
    return lst

def _scad_union(*args):
    meshes = _normalize_mesh_list(args)
    if not meshes:
        return None
    try:
        from trimesh.boolean import union as _U
        res = _U(meshes, engine=None)
        return res
    except Exception:
        return trimesh.util.concatenate(meshes)

def _scad_difference(a, *rest):
    A = _normalize_mesh_list([a])
    B = _normalize_mesh_list(rest)
    if not A:
        return None
    try:
        from trimesh.boolean import difference as _D
        return _D(A, B, engine=None)
    except Exception:
        return None

def _scad_intersection(*args):
    meshes = _normalize_mesh_list(args)
    if len(meshes) < 2:
        return None
    try:
        from trimesh.boolean import intersection as _I
        return _I(meshes, engine=None)
    except Exception:
        return None

def _scad_boolean(meshes, operation='union'):
    op = (operation or 'union').lower()
    if op.startswith('u'):
        return _scad_union(meshes)
    if op.startswith('d'):
        if isinstance(meshes, (list, tuple)) and len(meshes) >= 2:
            return _scad_difference(meshes[0], meshes[1:])
        return None
    if op.startswith('i'):
        return _scad_intersection(meshes)
    return None

try:
    import trimesh.interfaces as _ifc
    if not hasattr(_ifc, "scad"):
        _ifc.scad = types.SimpleNamespace(
            boolean=_scad_boolean,
            union=_scad_union,
            difference=_scad_difference,
            intersection=_scad_intersection,
        )
except Exception:
    pass

# -------------------------- Config & App --------------------------

def _split_origins(s: Optional[str]) -> list[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]

CORS_ALLOW = os.getenv("CORS_ALLOW_ORIGINS", "")
origins = _split_origins(CORS_ALLOW) or ["*"]

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")
CLEANUP_TOKEN = os.getenv("CLEANUP_TOKEN", "")  # para endpoint de mantenimiento

# -------- Gate de negocio (env) ----------
REQUIRE_ENTITLEMENT = os.getenv("FORGE_REQUIRE_ENTITLEMENT", "0") == "1"
FORGE_FREE_SLUGS = {
    s.strip().lower().replace("_", "-")
    for s in (os.getenv("FORGE_FREE_SLUGS", "") or "").split(",")
    if s.strip()
}

app = FastAPI(title="Teknovashop FORGE — STL Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------- Schemas --------------------------

class TextOp(BaseModel):
    text: str
    size: float = 6.0
    depth: float = 1.2
    mode: str = "engrave"        # "engrave" | "emboss"
    pos: list[float] = Field(default_factory=lambda: [0, 0, 0])
    rot: list[float] = Field(default_factory=lambda: [0, 0, 0])
    font: Optional[str] = None
    anchor: Optional[Literal["top", "bottom", "front", "back", "left", "right"]] = "front"

class GenerateBody(BaseModel):
    slug: str                     # requerido por los builders (snake o kebab)
    params: Dict[str, Any] = Field(default_factory=dict)
    holes: Optional[Iterable[Dict[str, Any]]] = None
    text_ops: Optional[list[TextOp]] = None
    model: Optional[str] = None   # compat
    user_id: Optional[str] = None # <-- para el gate

# -------------------------- Helpers --------------------------

def _norm_slug_for_builder(s: str) -> str:
    if not s:
        return s
    raw = s.strip().lower()
    snake = raw.replace("-", "_")
    return ALIASES.get(raw, ALIASES.get(snake, snake))

def _slug_for_storage(s: str) -> str:
    return (s or "").strip().lower().replace("_", "-")

def _as_stl_bytes(obj: Any) -> Tuple[bytes, Optional[str]]:
    if isinstance(obj, (bytes, bytearray)):
        return (bytes(obj), None)
    if hasattr(obj, "read"):
        return (obj.read(), None)
    if isinstance(obj, str):
        if os.path.exists(obj):
            with open(obj, "rb") as f:
                return (f.read(), os.path.basename(obj))
        if obj.strip().startswith("solid"):
            return (obj.encode("utf-8"), None)
    if hasattr(obj, "export"):
        buf = io.BytesIO()
        try:
            obj.export(buf, file_type="stl")
        except TypeError:
            obj.export(file_obj=buf, file_type="stl")
        return (buf.getvalue(), None)
    if isinstance(obj, (list, tuple)):
        for it in obj:
            try:
                data, name = _as_stl_bytes(it)
                return (data, name)
            except Exception:
                continue
    raise TypeError("Builder returned unsupported type for STL export")

def _num(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return None

def _normalize_holes(holes: Optional[Iterable[Dict[str, Any]]]) -> List[tuple]:
    out: List[tuple] = []
    if not holes:
        return out
    for h in holes:
        if not isinstance(h, dict):
            continue
        x = _num(h.get("x"))
        y = _num(h.get("y"))
        d = _num(h.get("diam_mm") or h.get("diameter_mm") or h.get("diameter") or h.get("d"))
        if x is None or y is None or d is None or d <= 0:
            continue
        out.append((x, y, d))
    return out

_ALIAS_KEYS: Dict[str, List[str]] = {
    "L": ["length_mm", "length", "l"],
    "W": ["width_mm", "width", "w"],
    "H": ["height_mm", "height", "h"],
    "T": ["thickness_mm", "thickness", "t"],
    "R": ["fillet_mm", "fillet", "round_mm", "r"],
    "holes": ["holes"],
    "text": ["text", "label", "text_ops"],
}

def _get_param_from_aliases(params: Dict[str, Any], name: str) -> Any:
    if name in params:
        return params[name]
    nlow = name.lower()
    if nlow in params:
        return params[nlow]
    nup = name.upper()
    if nup in params:
        return params[nup]
    for alias in _ALIAS_KEYS.get(name, []):
        if alias in params:
            return params[alias]
    for alias in _ALIAS_KEYS.get(nlow, []):
        if alias in params:
            return params[alias]
    for alias in _ALIAS_KEYS.get(nup, []):
        if alias in params:
            return params[alias]
    return None

def _call_builder_compat(fn: Any, params: Dict[str, Any]) -> Any:
    try:
        sig = inspect.signature(fn)
    except Exception:
        sig = None

    if sig:
        kwargs: Dict[str, Any] = {}
        for name, p in sig.parameters.items():
            val = _get_param_from_aliases(params, name)
            if isinstance(val, (dict, list, tuple)) and name.lower() != "holes":
                pass
            else:
                vnum = _num(val)
                if vnum is not None:
                    val = vnum
            if name.lower() == "holes":
                val = params.get("holes", [])
            if val is None:
                if p.default is not inspect._empty:
                    continue
                if name in ("R", "r", "fillet", "fillet_mm", "round_mm"):
                    val = 0.0
            kwargs[name] = val
        try:
            return fn(**kwargs)
        except TypeError:
            order = ["L", "W", "H", "T", "R"]
            args: List[Any] = []
            for k in order:
                v = _get_param_from_aliases(params, k)
                vnum = _num(v)
                args.append(vnum if vnum is not None else v)
            return fn(*args)
    return fn(params)

# ------------ Auto-carga de builders ------------

def _lazy_load_builder(slug_snake: str) -> None:
    if not slug_snake or slug_snake in REGISTRY:
        return
    try:
        mod = importlib.import_module(f"models.{slug_snake}")
        cand = None
        for name in ("build", "make", "make_model"):
            f = getattr(mod, name, None)
            if callable(f):
                cand = f
                break
        if cand is None and isinstance(getattr(mod, "BUILD", None), dict):
            for key in ("make", "build"):
                f = mod.BUILD.get(key)
                if callable(f):
                    cand = f
                    break
        if not callable(cand):
            raise RuntimeError(f"models.{slug_snake} no expone builder válido")

        REGISTRY[slug_snake] = cand
        ALIASES.setdefault(slug_snake.replace("_", "-"), slug_snake)
        ALIASES.setdefault(slug_snake, slug_snake)
    except Exception:
        print(f"[FORGE][lazy] ERROR autocargando builder '{slug_snake}'", file=sys.stderr)
        traceback.print_exc()

# ------------ Adaptadores de slugs ------------

def _val(params: Dict[str, Any], *keys: str, default: Optional[float] = None) -> Optional[float]:
    for k in keys:
        v = _num(params.get(k))
        if v is not None:
            return v
    return default

ParamAdapter = Callable[[Dict[str, Any]], Tuple[str, Dict[str, Any]]]

def _adapt_tablet_stand(p: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    return (
        "laptop_stand",
        {
            "length_mm": _val(p, "length_mm", "length", default=160),
            "width_mm":  _val(p, "width_mm",  "width",  default=140),
            "height_mm": _val(p, "height_mm", "height", default=110),
            "thickness_mm": _val(p, "thickness_mm", "thickness", default=4),
        },
    )

def _adapt_monitor_stand(p: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    # Defaults "realistas" para bandeja: 400x200x70, pared 4mm
    return (
        "cable_tray",
        {
            "width":  _val(p, "length_mm", "length", default=400),
            "depth":  _val(p, "width_mm",  "width",  default=200),
            "height": _val(p, "height_mm", "height", default=70),
            "wall":   _val(p, "thickness_mm", "thickness", default=4),
        },
    )

def _adapt_phone_dock(p: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    return (
        "phone_stand",
        {
            "base_w":      _val(p, "length_mm", "length", default=90),
            "base_d":      _val(p, "width_mm",  "width",  default=110),
            "angle_deg":   _val(p, "angle_deg", default=62),
            "slot_w":      _val(p, "slot_w",    default=12),
            "slot_d":      _val(p, "slot_d",    default=12),
            "usb_clear_h": _val(p, "usb_clear_h", default=6),
            "wall":        _val(p, "thickness_mm", "thickness", default=4),
        },
    )

ADAPTERS: Dict[str, ParamAdapter] = {
    "tablet_stand":  _adapt_tablet_stand,
    "monitor_stand": _adapt_monitor_stand,
    "phone_dock":    _adapt_phone_dock,
}

# ---------------- Licencias / Entitlements ----------------

_supabase_db = None
def _db():
    global _supabase_db
    if _supabase_db is None:
        from supabase import create_client
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("Supabase ENV vars missing")
        _supabase_db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _supabase_db

def _is_entitled(user_id: str, slug_like: str) -> bool:
    if not user_id or not slug_like:
        return False

    snake = _norm_slug_for_builder(slug_like)
    kebab = _slug_for_storage(snake)

    for col in ("model_slug", "slug"):
        try:
            sel = f"id,{col},kind,expires_at"
            q = (
                _db()
                .table("entitlements")
                .select(sel)
                .eq("user_id", user_id)
                .in_(col, [snake, kebab, "*"])
                .limit(1)
                .execute()
            )
            rows = (q.data or []) if hasattr(q, "data") else (q or [])
        except Exception:
            rows = []
        if rows:
            expires = rows[0].get("expires_at")
            if not expires:
                return True
            try:
                dt = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
                return dt.replace(tzinfo=dt.tzinfo or timezone.utc) > datetime.now(timezone.utc)
            except Exception:
                return True
    return False

def _require_entitlement_or_402(user_id: Optional[str], slug: str):
    kebab = _slug_for_storage(_norm_slug_for_builder(slug))
    if kebab in FORGE_FREE_SLUGS:
        return
    if not REQUIRE_ENTITLEMENT:
        return
    if not user_id or not _is_entitled(user_id, slug):
        raise HTTPException(
            status_code=402,
            detail=f"Payment required for model '{kebab}'. Inicia sesión y compra/activa tu licencia."
        )

# -------------------------- Endpoints --------------------------

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "forge-stl",
        "origins": origins,
        "loaded_models": sorted(list(REGISTRY.keys())),
        "aliases_count": len(ALIASES),
        "adapters": sorted(list(ADAPTERS.keys())),
        "require_entitlement": REQUIRE_ENTITLEMENT,
        "free_slugs": sorted(list(FORGE_FREE_SLUGS)),
    }

@app.get("/debug/models")
def debug_models():
    sample = {}
    for i, (k, v) in enumerate(ALIASES.items()):
        if i >= 50:
            break
        sample[k] = v
    return {
        "models": sorted(list(REGISTRY.keys())),
        "aliases_count": len(ALIASES),
        "sample_aliases": sample,
        "adapters": sorted(list(ADAPTERS.keys())),
    }

@app.post("/generate")
def generate(body: GenerateBody, request: Request):
    hdr_uid = request.headers.get("x-user-id") or request.headers.get("x-user")
    user_id = (hdr_uid or body.user_id or "").strip() or None

    raw_slug = (body.slug or body.model or "").strip()
    incoming_params = dict(body.params or {})

    base_slug = _norm_slug_for_builder(raw_slug)
    adapter = ADAPTERS.get(base_slug)

    if adapter:
        builder_slug, adapted = adapter(incoming_params)
        params = dict(adapted)
    else:
        builder_slug = base_slug
        params = dict(incoming_params)

    if builder_slug and builder_slug not in REGISTRY:
        _lazy_load_builder(builder_slug)
    if not builder_slug or builder_slug not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Model '{builder_slug}' not found")

    _require_entitlement_or_402(user_id, builder_slug)

    storage_slug = _slug_for_storage(builder_slug)
    builder = REGISTRY[builder_slug]

    if "round_mm" in params and "fillet_mm" not in params:
        try:
            params["fillet_mm"] = float(params["round_mm"])
        except Exception:
            pass
    params["holes"] = _normalize_holes(body.holes)

    try:
        result = builder(params)
    except TypeError:
        try:
            result = _call_builder_compat(builder, params)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Model build error: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Model build error: {e}")

    # --------- PREVIEW A COLOR (GLB) ---------
    fmt = (request.query_params.get("fmt") or "").strip().lower()
    if fmt == "glb":
        try:
            place_layers = None
            try:
                from models.text_ops import place_text_layers as place_layers
            except Exception:
                try:
                    from models import place_text_layers as place_layers
                except Exception:
                    place_layers = None

            texts = []
            if place_layers and body.text_ops:
                texts = place_layers(result, [op.dict() for op in (body.text_ops or [])])

            from trimesh.visual import ColorVisuals
            base = result.copy()
            base.visual = ColorVisuals(base, face_colors=[210, 210, 210, 255])  # gris claro

            for t in texts:
                t.visual = ColorVisuals(t, face_colors=[0, 120, 255, 255])       # azul

            scene = trimesh.Scene()
            scene.add_geometry(base, node_name="base")
            for i, t in enumerate(texts):
                scene.add_geometry(t, node_name=f"text_{i}")

            buf = io.BytesIO()
            scene.export(file_obj=buf, file_type="glb")
            glb_bytes = buf.getvalue()

            filename = "forge-preview.glb"
            object_path = f"{storage_slug}/{filename}"
            out = upload_and_get_url(glb_bytes, object_path)
            return {"ok": True, "slug": builder_slug, "path": object_path, **(out or {})}
        except Exception as e:
            print("[FORGE][GLB] error:", e)  # fallback a STL normal

    # --------- STL final (con booleanos de texto) ---------
    _applier = None
    try:
        from models import apply_text_ops as _applier
    except Exception:
        try:
            from models.text import apply_text_ops as _applier
        except Exception:
            try:
                from models.text_ops import apply_text_ops as _applier
            except Exception:
                _applier = None
    if _applier and body.text_ops:
        try:
            result = _applier(result, [op.dict() for op in body.text_ops])
        except Exception:
            pass

    stl_bytes, maybe_name = _as_stl_bytes(result)
    filename = maybe_name or "forge-output.stl"
    object_path = f"{storage_slug}/{filename}"

    try:
        out = upload_and_get_url(stl_bytes, object_path)
        return {"ok": True, "slug": builder_slug, "path": object_path, **(out or {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {e}")

@app.post("/admin/cleanup-underscore")
def cleanup_underscore(request: Request):
    token = request.headers.get("x-cleanup-token", "")
    if not CLEANUP_TOKEN or token != CLEANUP_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        from supabase import create_client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase client not available: {e}")

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

        removed: List[str] = []
        page = 0
        page_size = 1000
        while True:
            listing = supabase.storage.from_(SUPABASE_BUCKET).list(
                "",
                {
                    "limit": page_size,
                    "offset": page * page_size,
                    "sortBy": {"column": "name", "order": "asc"},
                },
            )
            items = listing or []
            if not items:
                break
            to_remove: List[str] = []
            for it in items:
                name = it.get("name") or ""
                top = name.split("/", 1)[0]
                if "_" in top:
                    to_remove.append(name)
            if to_remove:
                supabase.storage.from_(SUPABASE_BUCKET).remove(to_remove)
                removed.extend(to_remove)
            if len(items) < page_size:
                break
            page += 1

        return {"ok": True, "removed": removed, "count": len(removed)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup error: {e}")
