# /app.py
import io
import os
from typing import Any, Dict, Iterable, Optional, Tuple, Union, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Tus modelos existentes
from models import REGISTRY, ALIASES  # definidos en models/__init__.py

from supabase_client import upload_and_get_url

# ---------------------------------------------------------------------
# Utilidades locales
# ---------------------------------------------------------------------

def _norm_model_key(k: str) -> str:
    # normaliza: espacios, mayúsculas, guiones -> underscores
    return (k or "").strip().lower().replace("-", "_").replace(" ", "_")

def _first(d: Dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None

def _as_stl_bytes(
    result: Any,
) -> Tuple[bytes, Optional[str]]:
    """
    Normaliza la salida del builder a (stl_bytes, filename|None).
    Acepta:
      - bytes/bytearray
      - io.BytesIO
      - str (ruta a archivo .stl)
      - (payload, filename?) en tuple/list
      - dict con 'bytes'/'buffer'/'stl'/'path'/'filename'
      - objetos con .export(fileobj=..., file_type="stl") o .to_stl()
    """
    filename: Optional[str] = None

    # tuple/list -> desenpaquetar
    if isinstance(result, (tuple, list)) and len(result) > 0:
        maybe_payload = result[0]
        if len(result) > 1 and isinstance(result[1], str):
            filename = result[1]
        result = maybe_payload

    # dict -> buscar variantes comunes
    if isinstance(result, dict):
        filename = _first(result, ("filename", "name")) or filename
        # bytes directos
        payload = _first(result, ("bytes", "buffer", "stl"))
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload), filename
        if isinstance(payload, io.BytesIO):
            return payload.getvalue(), filename
        # ruta
        path = _first(result, ("path", "file", "filepath"))
        if isinstance(path, str) and path:
            with open(path, "rb") as f:
                return f.read(), filename or os.path.basename(path)
        # si no hubo nada válido, seguir abajo (por si vino un objeto exportable)

        result = _first(result, ("mesh", "object", "model", "geom")) or result

    # bytes/BytesIO
    if isinstance(result, (bytes, bytearray)):
        return bytes(result), filename
    if isinstance(result, io.BytesIO):
        return result.getvalue(), filename

    # ruta a fichero
    if isinstance(result, str) and result:
        # si es texto STL (muy raro), conviértelo a bytes igual
        if os.path.isfile(result):
            with open(result, "rb") as f:
                return f.read(), filename or os.path.basename(result)
        return result.encode("utf-8"), filename or "model.stl"

    # objetos con .export(fileobj=..., file_type="stl")
    export = getattr(result, "export", None)
    if callable(export):
        bio = io.BytesIO()
        try:
            export(fileobj=bio, file_type="stl")  # trimesh, etc.
            return bio.getvalue(), filename
        except Exception:
            bio = io.BytesIO()
            export(bio)  # por si la firma es distinta
            return bio.getvalue(), filename

    # objetos con .to_stl()
    to_stl = getattr(result, "to_stl", None)
    if callable(to_stl):
        out = to_stl()
        if isinstance(out, (bytes, bytearray)):
            return bytes(out), filename
        if isinstance(out, io.BytesIO):
            return out.getvalue(), filename
        if isinstance(out, str):
            if os.path.isfile(out):
                with open(out, "rb") as f:
                    return f.read(), filename or os.path.basename(out)
            return out.encode("utf-8"), filename or "model.stl"

    raise HTTPException(status_code=500, detail="Builder must return bytes or BytesIO")

# ---------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------

app = FastAPI()

# CORS
allowed_origins = [
    os.getenv("FRONTEND_ORIGIN")
    or os.getenv("NEXT_PUBLIC_SITE_URL")
    or "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- Esquemas de entrada ---------
class Hole(BaseModel):
    x_mm: float
    y_mm: float
    d_mm: float

class ArrayOp(BaseModel):
    count: int = 1
    dx: float = 0.0
    dy: float = 0.0

class TextOp(BaseModel):
    text: str
    size: float = 10.0
    x: float = 0.0
    y: float = 0.0
    depth: float | None = None
    # En el futuro: rx, ry, rz, z, align, etc.

class Params(BaseModel):
    length_mm: float = Field(gt=0)
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    thickness_mm: float | None = Field(default=None, gt=0)
    fillet_mm: float | None = Field(default=None, ge=0)
    holes: list[Hole] = Field(default_factory=list)
    arrayOps: list[ArrayOp] = Field(default_factory=list)
    textOps: list[TextOp] = Field(default_factory=list)

class GenerateBody(BaseModel):
    model: str
    params: Params

# --------- Salud (rico) ---------
@app.get("/health")
async def health(request: Request):
    # Modelos y alias visibles (sin secretos)
    env_snapshot = {
        "SUPABASE_URL_set": bool(os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")),
        "SUPABASE_BUCKET": os.getenv("SUPABASE_BUCKET") or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET") or "forge-stl",
        "FRONTEND_ORIGIN": os.getenv("FRONTEND_ORIGIN"),
        "NEXT_PUBLIC_SITE_URL": os.getenv("NEXT_PUBLIC_SITE_URL"),
    }
    return {
        "ok": True,
        "available_models": sorted(REGISTRY.keys()),
        "aliases": ALIASES if isinstance(ALIASES, dict) else {},
        "env": env_snapshot,
        "cors_allowed_origins": allowed_origins,
    }

# --------- Generate ---------
@app.post("/generate")
async def generate(body: GenerateBody, request: Request):
    raw_key = body.model or ""
    model_key = _norm_model_key(raw_key)

    # Look-up directo
    entry: Optional[Union[Callable[..., Any], Dict[str, Any]]] = REGISTRY.get(model_key)
    # Alias
    if entry is None and isinstance(ALIASES, dict):
        alias = ALIASES.get(model_key) or ALIASES.get(raw_key)  # por si el alias está en otro formato
        if isinstance(alias, str):
            entry = REGISTRY.get(_norm_model_key(alias))

    if entry is None:
        available = sorted(REGISTRY.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Model '{raw_key}' not found. Available: {', '.join(available)}"
        )

    # Puede ser una función o un dict {'make' | 'builder': fn}
    make_fn: Optional[Callable[..., Any]] = None
    if callable(entry):
        make_fn = entry
    elif isinstance(entry, dict):
        make_fn = entry.get("make") or entry.get("builder") or None

    if not callable(make_fn):
        raise HTTPException(status_code=500, detail="Invalid model registry entry (no callable).")

    # Parametría plana que algunos builders esperan
    p: Dict[str, Any] = {
        "length_mm": float(body.params.length_mm),
        "width_mm": float(body.params.width_mm),
        "height_mm": float(body.params.height_mm),
        "thickness_mm": float(body.params.thickness_mm) if body.params.thickness_mm else None,
        "fillet_mm": float(body.params.fillet_mm) if body.params.fillet_mm else None,
        "holes": [h.model_dump() for h in body.params.holes],
        "arrayOps": [a.model_dump() for a in body.params.arrayOps],
        "textOps": [t.model_dump() for t in body.params.textOps],
    }

    # Construcción
    try:
        result_any = make_fn(p)  # llama al builder real de tu modelo
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model build error: {e}")

    # Normaliza a bytes STL
    stl_bytes, suggested_name = _as_stl_bytes(result_any)

    # Nombre de salida
    filename = suggested_name or f"{model_key}.stl"

    # Subida a Supabase
    up = upload_and_get_url(
        stl_bytes,
        bucket=os.getenv("SUPABASE_BUCKET") or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET") or "forge-stl",
        folder="stl",
        filename=filename,
    )

    if not up.get("ok"):
        raise HTTPException(status_code=500, detail=up.get("error") or "Upload failed")

    # Respuesta consistente para el front
    resp: Dict[str, Any] = {"ok": True, "path": up.get("path"), "filename": filename}
    if up.get("url"):
        resp["stl_url"] = up["url"]
    if up.get("signed_url"):
        resp["signed_url"] = up["signed_url"]
    return resp
