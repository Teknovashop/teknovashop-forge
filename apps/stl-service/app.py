from __future__ import annotations

import io
import os
import json
import hashlib
import inspect
import importlib
import sys
import traceback
import types
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple, List, Callable, Literal

import trimesh
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from models import REGISTRY, ALIASES  # registro dinámico + alias para slugs
from model_contracts import PRODUCTS
from supabase_client import upload_and_get_url  # subida + URL firmada

# -------------------------------------------------------------------
# Parches de compatibilidad (evitan errores en modelos antiguos)
# -------------------------------------------------------------------

# 1) Compat: algunos modelos usan .apply_rotation(matrix)
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

# 2) Compat: shim para trimesh.interfaces.scad (degrada a boolean nativo o concat)
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
CLEANUP_TOKEN = os.getenv("CLEANUP_TOKEN", "")  # mantenimiento
DIAGNOSTICS_TOKEN = os.getenv("FORGE_DIAGNOSTICS_TOKEN", "")

# -------- Gate de negocio (env) ----------
REQUIRE_ENTITLEMENT = os.getenv("FORGE_REQUIRE_ENTITLEMENT", "0") == "1"
FORGE_FREE_SLUGS = {
    s.strip().lower().replace("_", "-")
    for s in (os.getenv("FORGE_FREE_SLUGS", "") or "").split(",")
    if s.strip()
}

# -------- Catálogo/whitelist por entorno ----------
def _whitelist() -> Optional[List[str]]:
    raw = (os.getenv("FORGE_MODEL_WHITELIST", "") or "").strip()
    if not raw:
        return None
    return [s.strip().lower().replace("-", "_") for s in raw.split(",") if s.strip()]

def _is_enabled_by_whitelist(snake_slug: str) -> bool:
    wl = _whitelist()
    return True if wl is None else (snake_slug in wl)

app = FastAPI(title="Teknovashop FORGE — STL Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _require_diagnostics(request: Request) -> None:
    if not DIAGNOSTICS_TOKEN:
        raise HTTPException(status_code=404, detail="Not found")
    if request.headers.get("x-diagnostics-token", "") != DIAGNOSTICS_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


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
    operations: Optional[list[Dict[str, Any]]] = None
    engine_version: str = "mesh-v1"
    schema_version: int = 1
    model: Optional[str] = None   # compat
    user_id: Optional[str] = None # gate

# -------------------------- Helpers --------------------------

def _norm_slug_for_builder(s: str) -> str:
    if not s:
        return s
    raw = s.strip().lower()
    snake = raw.replace("-", "_")
    return ALIASES.get(raw, ALIASES.get(snake, snake))

def _slug_for_storage(s: str) -> str:
    return (s or "").strip().lower().replace("_", "-")

def _new_object_path(storage_slug: str, extension: str) -> str:
    """Ruta única e inmutable para una generación."""
    now = datetime.now(timezone.utc)
    ext = extension.lstrip(".").lower()
    return (
        f"{storage_slug}/"
        f"{now:%Y/%m/%d}/"
        f"{now:%H%M%S}-{uuid4().hex}.{ext}"
    )

def _new_design_location(storage_slug: str) -> Tuple[str, datetime, str]:
    """Crea un ID y prefijo compartido para STL + manifiesto."""
    generated_at = datetime.now(timezone.utc)
    design_id = uuid4().hex
    base_path = (
        f"{storage_slug}/"
        f"{generated_at:%Y/%m/%d}/"
        f"{generated_at:%H%M%S}-{design_id}"
    )
    return design_id, generated_at, base_path

def _text_ops_for_manifest(body: "GenerateBody") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for op in body.text_ops or []:
        if hasattr(op, "model_dump"):
            out.append(op.model_dump())
        else:
            out.append(op.dict())
    return out

def _make_design_manifest(
    *,
    design_id: str,
    generated_at: datetime,
    storage_slug: str,
    builder_slug: str,
    params: Dict[str, Any],
    holes: List[Any],
    text_ops: List[Dict[str, Any]],
    object_path: str,
    stl_bytes: bytes,
    engine_version: str = "mesh-v1",
    schema_version: int = 1,
    operations: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Construye el manifiesto reproducible de una generación sin I/O."""
    product = PRODUCTS.get(storage_slug, {})
    return {
        "schema": "teknovashop.design.v2" if schema_version == 2 else "teknovashop.design.v1",
        "engine_version": engine_version,
        "schema_version": schema_version,
        "design_id": design_id,
        "generated_at": generated_at.isoformat(),
        "product": {
            "slug": storage_slug,
            "builder": builder_slug,
            "name": str(product.get("name", storage_slug)),
            "version": str(product.get("version", "unversioned")),
            "stage": str(product.get("stage", "unversioned")),
        },
        "parameters": dict(params),
        "holes": list(holes),
        "text_ops": list(text_ops),
        "operations": list(operations or []),
        "artifact": {
            "format": "stl",
            "units": "mm",
            "path": object_path,
            "sha256": hashlib.sha256(stl_bytes).hexdigest(),
            "bytes": len(stl_bytes),
        },
    }

def _make_preview_stl_bytes(stl_bytes: bytes) -> Tuple[bytes, float]:
    """Create a precision-degraded STL for browser preview.

    The preview intentionally snaps vertices to a coarse grid. It preserves the
    overall shape for visual validation while making the browser asset unsuitable
    as the authoritative manufacturing file.
    """
    import numpy as np

    loaded = trimesh.load(
        io.BytesIO(stl_bytes),
        file_type="stl",
        force="mesh",
        process=False,
    )
    if not isinstance(loaded, trimesh.Trimesh):
        raise TypeError("Preview source is not a mesh")
    if len(loaded.vertices) == 0 or len(loaded.faces) == 0:
        raise ValueError("Preview source mesh is empty")

    mesh = loaded.copy()
    max_dim = float(max(mesh.extents)) if len(mesh.extents) else 1.0
    precision_mm = max(0.8, min(2.0, max_dim / 120.0))

    snapped = np.round(np.asarray(mesh.vertices, dtype=float) / precision_mm) * precision_mm
    preview = trimesh.Trimesh(
        vertices=snapped,
        faces=np.asarray(mesh.faces, dtype=int).copy(),
        process=True,
        validate=False,
    )
    preview.remove_unreferenced_vertices()

    out = preview.export(file_type="stl")
    if isinstance(out, str):
        out = out.encode("utf-8")
    return bytes(out), round(precision_mm, 3)


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
    # Defaults realistas para una bandeja: 400x200x70, pared 4mm
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

def _authenticated_user_id(request: Request) -> Optional[str]:
    """Return the authenticated Supabase user id from a verified bearer token.

    Caller-supplied identity headers/body fields are intentionally ignored.
    The access token is validated against Supabase Auth before its user id is
    trusted for entitlement checks.
    """
    auth = (request.headers.get("authorization") or "").strip()
    if not auth.lower().startswith("bearer "):
        return None

    token = auth.split(None, 1)[1].strip() if " " in auth else ""
    if not token:
        raise HTTPException(status_code=401, detail="Invalid authorization token")

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise HTTPException(status_code=503, detail="Supabase auth verification is not configured")

    try:
        import httpx

        response = httpx.get(
            f"{SUPABASE_URL.rstrip('/')}/auth/v1/user",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {token}",
            },
            timeout=10.0,
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Supabase auth verification unavailable")

    if response.status_code in (401, 403):
        raise HTTPException(status_code=401, detail="Invalid or expired authorization token")
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="Supabase auth verification failed")

    try:
        payload = response.json()
    except Exception:
        raise HTTPException(status_code=503, detail="Supabase auth verification returned invalid data")

    user_id = str((payload or {}).get("id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Authenticated user id missing")

    return user_id


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


@app.get("/catalog/thumbnail/{slug}.png")
def catalogue_thumbnail(slug: str):
    storage_slug = _slug_for_storage(_norm_slug_for_builder(slug))
    if storage_slug not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        from catalog_thumbnail import render_product_thumbnail
        data = render_product_thumbnail(storage_slug)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Thumbnail render failed: {exc}")
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/catalog/mesh/{slug}.stl")
def catalogue_mesh(slug: str):
    """Public, canonical STL preview used only by catalogue/WebGL cards.

    This endpoint is intentionally limited to PRODUCTS and always builds the
    contract defaults. It does not expose purchased/customized customer files.
    """
    storage_slug = _slug_for_storage(_norm_slug_for_builder(slug))
    contract = PRODUCTS.get(storage_slug)
    if not contract:
        raise HTTPException(status_code=404, detail="Product not found")

    builder = REGISTRY.get(contract["builder"])
    if builder is None:
        raise HTTPException(status_code=500, detail="Canonical builder missing")

    try:
        value = builder(dict(contract["default"]))
        if isinstance(value, trimesh.Trimesh):
            mesh = value
        elif isinstance(value, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(value.geometry.values()))
        elif isinstance(value, (list, tuple)):
            meshes = [item for item in value if isinstance(item, trimesh.Trimesh)]
            if not meshes:
                raise TypeError("Builder returned no mesh")
            mesh = trimesh.util.concatenate(meshes)
        else:
            raise TypeError(f"Unsupported builder output: {type(value).__name__}")

        payload = mesh.export(file_type="stl")
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        payload = bytes(payload)
        if len(payload) <= 84:
            raise ValueError("Generated STL is empty")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Catalogue mesh failed: {exc}")

    return Response(
        content=payload,
        media_type="model/stl",
        headers={
            "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'inline; filename="{storage_slug}.stl"',
        },
    )


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "forge-stl",
        "catalog_count": len(PRODUCTS),
    }

@app.get("/debug/storage")
def debug_storage(request: Request):
    _require_diagnostics(request)
    """Diagnóstico seguro de conectividad con Supabase Storage.

    No expone ninguna clave. Solo informa del host, resolución DNS
    y acceso de lectura al bucket configurado.
    """
    import socket
    from urllib.parse import urlparse

    raw_url = (SUPABASE_URL or "").strip()
    host = urlparse(raw_url).hostname if raw_url else None

    result: Dict[str, Any] = {
        "ok": False,
        "supabase_configured": bool(raw_url),
        "service_key_configured": bool(SUPABASE_SERVICE_KEY),
        "bucket": SUPABASE_BUCKET,
        "host": host,
        "dns_ok": False,
        "storage_ok": False,
    }

    if not raw_url:
        result["error"] = "SUPABASE_URL is missing"
        return result
    if not SUPABASE_SERVICE_KEY:
        result["error"] = "SUPABASE_SERVICE_KEY / SERVICE_ROLE_KEY is missing"
        return result
    if not host:
        result["error"] = "SUPABASE_URL has no valid hostname"
        return result

    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        result["dns_ok"] = bool(infos)
        result["resolved_ips"] = sorted({x[4][0] for x in infos})[:4]
    except Exception as e:
        result["error"] = f"DNS resolution failed: {e}"
        return result

    try:
        from supabase import create_client
        client = create_client(raw_url.rstrip("/"), SUPABASE_SERVICE_KEY)
        bucket = client.storage.from_(SUPABASE_BUCKET)
        listing = bucket.list("", {"limit": 1, "offset": 0})
        result["storage_ok"] = True
        result["sample_count"] = len(listing or [])
        result["ok"] = True
        return result
    except Exception as e:
        result["error"] = f"Storage access failed: {e}"
        return result


STUDIO_ENGINEERING_DIR = Path(__file__).resolve().parent / "static" / "studio" / "engineering"


def _engineering_studio_asset(slug: str) -> Optional[Path]:
    path = STUDIO_ENGINEERING_DIR / f"{slug}.webp"
    try:
        return path if path.is_file() and path.stat().st_size > 1000 else None
    except OSError:
        return None


@app.get("/catalog/studio/{slug}.webp")
def catalog_studio_asset(slug: str):
    storage_slug = _slug_for_storage(_norm_slug_for_builder(slug))
    if storage_slug not in PRODUCTS:
        raise HTTPException(status_code=404, detail="Product not found")
    path = _engineering_studio_asset(storage_slug)
    if path is None:
        raise HTTPException(status_code=404, detail="Studio asset not ready")
    return Response(
        content=path.read_bytes(),
        media_type="image/webp",
        headers={
            "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/catalog/products")
def catalog_products(stage: Optional[str] = None, public_only: bool = False):
    """Canonical product feed for storefront, Forge V2 and release QA.

    Geometry/contracts and commercial metadata are joined here so clients do
    not maintain a second independent product registry.
    """
    try:
        from v2_operations import PRODUCT_CAPABILITIES
    except Exception:
        PRODUCT_CAPABILITIES = {}

    try:
        from product_catalog import PRODUCT_METADATA, PUBLIC_STAGES
    except Exception:
        PRODUCT_METADATA = {}
        PUBLIC_STAGES = {"production"}

    products = []
    for slug, contract in PRODUCTS.items():
        metadata = PRODUCT_METADATA.get(slug, {})
        release_stage = str(contract.get("stage") or metadata.get("stage") or "engineering")
        if public_only and release_stage not in PUBLIC_STAGES:
            continue
        if stage and release_stage != stage:
            continue

        studio_asset = _engineering_studio_asset(slug)
        products.append(
            {
                "slug": slug,
                "name": metadata.get("name") or contract["name"],
                "family": metadata.get("family") or "Forge",
                "description": metadata.get("description") or "",
                "tips": metadata.get("tips") or [],
                "marketing_image": (
                    metadata.get("marketing_image")
                    or (f"/catalog/studio/{slug}.webp" if studio_asset else None)
                ),
                "visual_source": (
                    metadata.get("visual_source")
                    if metadata.get("marketing_image")
                    else ("studio_asset" if studio_asset else "generated_preview")
                ),
                "version": contract["version"],
                "stage": release_stage,
                "public": release_stage in PUBLIC_STAGES,
                "builder": contract.get("builder"),
                "capabilities": contract.get("capabilities", {}),
                "v2_capabilities": sorted(PRODUCT_CAPABILITIES.get(slug, set())),
                "defaults": contract["default"],
                "variant": contract.get("variant", {}),
                "min_extents": contract.get("min_extents"),
            }
        )

    return {
        "count": len(products),
        "total": len(PRODUCTS),
        "products": products,
        "stages": {
            "production": sum(1 for p in products if p["stage"] == "production"),
            "visual_qa": sum(1 for p in products if p["stage"] == "visual_qa"),
            "engineering": sum(1 for p in products if p["stage"] == "engineering"),
        },
    }


@app.get("/catalog/products/{slug}")
def catalog_product(slug: str):
    storage_slug = _slug_for_storage(_norm_slug_for_builder(slug))
    contract = PRODUCTS.get(storage_slug)
    if not contract:
        raise HTTPException(status_code=404, detail="Product not found")

    try:
        from v2_operations import PRODUCT_CAPABILITIES
    except Exception:
        PRODUCT_CAPABILITIES = {}

    try:
        from product_catalog import PRODUCT_METADATA, PUBLIC_STAGES
    except Exception:
        PRODUCT_METADATA = {}
        PUBLIC_STAGES = {"production"}

    metadata = PRODUCT_METADATA.get(storage_slug, {})
    release_stage = str(
        contract.get("stage") or metadata.get("stage") or "engineering"
    )

    studio_asset = _engineering_studio_asset(storage_slug)

    return {
        "slug": storage_slug,
        "name": metadata.get("name") or contract["name"],
        "family": metadata.get("family") or "Forge",
        "description": metadata.get("description") or "",
        "tips": metadata.get("tips") or [],
        "marketing_image": (
            metadata.get("marketing_image")
            or (f"/catalog/studio/{storage_slug}.webp" if studio_asset else None)
        ),
        "visual_source": (
            metadata.get("visual_source")
            if metadata.get("marketing_image")
            else ("studio_asset" if studio_asset else "generated_preview")
        ),
        "version": contract["version"],
        "stage": release_stage,
        "public": release_stage in PUBLIC_STAGES,
        "builder": contract.get("builder"),
        "capabilities": contract.get("capabilities", {}),
        "v2_capabilities": sorted(PRODUCT_CAPABILITIES.get(storage_slug, set())),
        "defaults": contract["default"],
        "variant": contract.get("variant", {}),
        "min_extents": contract.get("min_extents"),
    }


@app.get("/debug/models")
def debug_models(request: Request):
    _require_diagnostics(request)
    wl = _whitelist()
    keys = list(REGISTRY.keys())
    if wl:
        keys = [k for k in keys if k in wl]
    # Responder en kebab-case para el front
    return {"models": sorted([k.replace("_", "-") for k in keys])}

@app.get("/debug/model-audit")
def debug_model_audit(request: Request, slug: Optional[str] = None):
    _require_diagnostics(request)
    """Genera modelos en memoria y devuelve métricas geométricas seguras.

    No sube archivos ni expone secretos. Sirve para comprobar que cada
    builder produce una malla utilizable con sus valores por defecto.
    """
    import numpy as np

    def _audit_one(name: str) -> Dict[str, Any]:
        builder = REGISTRY.get(name)
        if not builder:
            return {"slug": name.replace("_", "-"), "ok": False, "error": "builder missing"}

        try:
            try:
                mesh = builder({})
            except TypeError:
                mesh = _call_builder_compat(builder, {})

            if isinstance(mesh, (list, tuple)):
                meshes = [m for m in mesh if isinstance(m, trimesh.Trimesh)]
                mesh = trimesh.util.concatenate(meshes) if meshes else None

            if not isinstance(mesh, trimesh.Trimesh):
                return {
                    "slug": name.replace("_", "-"),
                    "ok": False,
                    "error": f"builder returned {type(mesh).__name__}",
                }

            if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
                return {
                    "slug": name.replace("_", "-"),
                    "ok": False,
                    "error": "empty mesh",
                }

            extents = np.asarray(mesh.extents, dtype=float)
            bounds = np.asarray(mesh.bounds, dtype=float)
            components = mesh.split(only_watertight=False)

            return {
                "slug": name.replace("_", "-"),
                "ok": bool(np.all(np.isfinite(extents)) and np.all(extents > 0)),
                "vertices": int(len(mesh.vertices)),
                "faces": int(len(mesh.faces)),
                "extents_mm": [round(float(x), 3) for x in extents.tolist()],
                "bounds_mm": [
                    [round(float(x), 3) for x in bounds[0].tolist()],
                    [round(float(x), 3) for x in bounds[1].tolist()],
                ],
                "watertight": bool(mesh.is_watertight),
                "components": int(len(components)),
                "volume_mm3": round(float(abs(mesh.volume)), 3) if np.isfinite(mesh.volume) else None,
            }
        except Exception as e:
            return {
                "slug": name.replace("_", "-"),
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
            }

    if slug:
        name = _norm_slug_for_builder(slug)
        if name not in REGISTRY:
            _lazy_load_builder(name)
        if name not in REGISTRY:
            raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")
        return _audit_one(name)

    results = [_audit_one(name) for name in sorted(REGISTRY.keys())]
    return {
        "ok": all(item.get("ok") for item in results),
        "count": len(results),
        "passed": sum(1 for item in results if item.get("ok")),
        "failed": sum(1 for item in results if not item.get("ok")),
        "models": results,
    }



@app.post("/v2/validate")
def validate_v2(body: GenerateBody):
    storage_slug = _slug_for_storage(_norm_slug_for_builder(body.slug or body.model or ""))
    if body.engine_version != "mesh-v2" or body.schema_version != 2:
        raise HTTPException(status_code=400, detail="Forge V2 requires mesh-v2/schema 2")
    try:
        from v2_operations import PRODUCT_CAPABILITIES, validate_operations
        if storage_slug not in PRODUCTS:
            raise HTTPException(status_code=404, detail="Product not found")
        issues = validate_operations(storage_slug, body.operations or [])
        return {
            "ok": not any(issue.get("level") == "error" for issue in issues),
            "slug": storage_slug,
            "engine_version": body.engine_version,
            "schema_version": body.schema_version,
            "issues": issues,
            "capabilities": sorted(PRODUCT_CAPABILITIES.get(storage_slug, set())),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"V2 validation error: {e}")


@app.post("/generate")
def generate(body: GenerateBody, request: Request):
    # Identity must come from a verified Supabase access token. Never trust
    # x-user-id/x-user or body.user_id because this service is internet-facing.
    user_id = _authenticated_user_id(request)

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

    # Whitelist: si existe, sólo permite esos modelos
    if not _is_enabled_by_whitelist(builder_slug):
        keb = _slug_for_storage(builder_slug)
        raise HTTPException(status_code=400, detail=f"Model '{keb}' is disabled")

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

    # El antiguo preview GLB contenía geometría de precisión completa y podía
    # reconstruirse fuera del navegador. Se deshabilita para evitar que el
    # artefacto de fabricación se filtre antes de la compra.
    fmt = (request.query_params.get("fmt") or "").strip().lower()
    if fmt == "glb":
        raise HTTPException(
            status_code=410,
            detail="Legacy full-precision GLB preview disabled; use the standard preview flow.",
        )

    # --------- STL final (con texto booleano si aplica) ---------
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
    if body.text_ops:
        if _applier is None:
            raise HTTPException(
                status_code=500,
                detail="Text engine is not available on the Forge backend",
            )
        try:
            ops = [
                op.model_dump() if hasattr(op, "model_dump") else op.dict()
                for op in body.text_ops
            ]
            result = _applier(result, ops)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Text operation failed: {e}",
            )

    if body.operations:
        if body.engine_version != "mesh-v2" or body.schema_version != 2:
            raise HTTPException(
                status_code=400,
                detail="V2 operations require engine_version=mesh-v2 and schema_version=2",
            )
        try:
            from v2_operations import PRODUCT_CAPABILITIES, apply_operations
            if storage_slug not in PRODUCTS:
                raise HTTPException(status_code=404, detail="Product not found")
            if not PRODUCT_CAPABILITIES.get(storage_slug):
                raise HTTPException(
                    status_code=400,
                    detail="This product supports Forge V2 versioning but has no advanced geometry operations enabled yet",
                )
            result = apply_operations(result, storage_slug, body.operations)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"V2 operation failed: {e}")

    stl_bytes, maybe_name = _as_stl_bytes(result)

    product = PRODUCTS.get(storage_slug, {})
    product_version = str(product.get("version", "unversioned"))
    product_stage = str(product.get("stage", "unversioned"))
    product_name = str(product.get("name", storage_slug))

    design_id, generated_at, base_path = _new_design_location(storage_slug)
    object_path = f"{base_path}.stl"
    manifest_path = f"{base_path}.json"

    # params ya contiene agujeros normalizados; los separamos para que el
    # manifiesto sea más legible y reproducible.
    manifest_params = dict(params)
    manifest_holes = manifest_params.pop("holes", [])

    manifest = _make_design_manifest(
        design_id=design_id,
        generated_at=generated_at,
        storage_slug=storage_slug,
        builder_slug=builder_slug,
        params=manifest_params,
        holes=manifest_holes,
        text_ops=_text_ops_for_manifest(body),
        object_path=object_path,
        stl_bytes=stl_bytes,
        engine_version=body.engine_version,
        schema_version=body.schema_version,
        operations=list(body.operations or []),
    )
    stl_sha256 = manifest["artifact"]["sha256"]
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
    ).encode("utf-8")

    try:
        preview_bytes, preview_precision_mm = _make_preview_stl_bytes(stl_bytes)
        preview_path = f"{base_path}-preview.stl"

        # Manufacturing artifacts stay private. Only the deliberately degraded
        # preview receives a short-lived browser URL.
        upload_and_get_url(
            stl_bytes,
            object_path,
            sign=False,
            cache_control="private, max-age=0, no-store",
        )
        upload_and_get_url(
            manifest_bytes,
            manifest_path,
            sign=False,
            content_type="application/json",
            cache_control="private, max-age=0, no-store",
        )
        preview_upload = upload_and_get_url(
            preview_bytes,
            preview_path,
            sign=True,
            expires_in=15 * 60,
            cache_control="private, max-age=900",
        )
        return {
            "ok": True,
            "slug": builder_slug,
            "design_id": design_id,
            "product_name": product_name,
            "product_version": product_version,
            "product_stage": product_stage,
            "generated_at": generated_at.isoformat(),
            "path": object_path,
            "manifest_path": manifest_path,
            "sha256": stl_sha256,
            "preview_path": preview_path,
            "preview_url": (preview_upload or {}).get("signed_url"),
            "preview_precision_mm": preview_precision_mm,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Artifact/manifest upload error: {e}",
        )

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
