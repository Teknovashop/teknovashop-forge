# apps/stl-service/app.py
import io
import os
import inspect
import importlib
import sys
import traceback
from typing import Any, Dict, Iterable, Optional, Tuple, List, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models import REGISTRY, ALIASES  # registro dinámico + alias para slugs
from supabase_client import upload_and_get_url  # subida + URL firmada

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

class GenerateBody(BaseModel):
    slug: str                     # requerido por los builders (snake o kebab admitidos)
    params: Dict[str, Any] = Field(default_factory=dict)
    holes: Optional[Iterable[Dict[str, Any]]] = None
    text_ops: Optional[list[TextOp]] = None
    model: Optional[str] = None   # compat: algunos clientes siguen enviando "model"

# -------------------------- Helpers --------------------------

def _norm_slug_for_builder(s: str) -> str:
    """
    Normaliza el slug para el REGISTRY (builders):
    - minúsculas
    - kebab->snake
    - aplica ALIASES si existen
    """
    if not s:
        return s
    raw = s.strip().lower()
    snake = raw.replace("-", "_")
    return ALIASES.get(raw, ALIASES.get(snake, snake))

def _slug_for_storage(s: str) -> str:
    """
    Slug para el STORAGE (bucket):
    - minúsculas
    - snake->kebab (queremos carpetas tipo 'cable-tray')
    """
    return (s or "").strip().lower().replace("_", "-")

def _as_stl_bytes(obj: Any) -> Tuple[bytes, Optional[str]]:
    # bytes/bytearray
    if isinstance(obj, (bytes, bytearray)):
        return (bytes(obj), None)
    # file-like
    if hasattr(obj, "read"):
        return (obj.read(), None)
    # string: ruta física o ASCII STL
    if isinstance(obj, str):
        if os.path.exists(obj):
            with open(obj, "rb") as f:
                return (f.read(), os.path.basename(obj))
        if obj.strip().startswith("solid"):
            return (obj.encode("utf-8"), None)
    # trimesh u objeto con .export
    if hasattr(obj, "export"):
        buf = io.BytesIO()
        try:
            obj.export(buf, file_type="stl")
        except TypeError:
            obj.export(file_obj=buf, file_type="stl")
        return (buf.getvalue(), None)
    # colecciones: toma el primero convertible
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
    """
    Convierte [{x,y,diam_mm}] en [(x,y,diam)] descartando entradas inválidas.
    """
    out: List[tuple] = []
    if not holes:
        return out
    for h in holes:
        if not isinstance(h, dict):
            continue
        x = _num(h.get("x"))
        y = _num(h.get("y"))
        # 👇 Añadido: diameter_mm (además de diam_mm/diameter/d)
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
    """
    Llama a un builder que NO acepta un dict; hace mapping por nombre/posición.
    Soporta funciones tipo plate_with_holes(L,W,H,T,R,holes=...).
    """
    sig = None
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

# ------------ Fallback: autocargar builder si no está en REGISTRY ------------

def _lazy_load_builder(slug_snake: str) -> None:
    if not slug_snake:
        return
    if slug_snake in REGISTRY:
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

# ------------ Adaptadores de slugs del UI a builders reales ------------------

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
            "width":     _val(p, "length_mm", "length", default=160),
            "depth":     _val(p, "width_mm",  "width",  default=140),
            "angle_deg": _val(p, "angle_deg", default=65),
            "lip_h":     _val(p, "lip_h",     default=10),
            "vent_slot": _val(p, "vent_slot", default=12),
            "wall":      _val(p, "thickness_mm", "thickness", default=4),
        },
    )

def _adapt_monitor_stand(p: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
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
def generate(body: GenerateBody):
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

# -------------------------- Mantenimiento (opcional) --------------------------

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
