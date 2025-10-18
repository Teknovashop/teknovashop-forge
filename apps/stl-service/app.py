# apps/stl-service/app.py
import io
import os
import base64
import tempfile
from typing import Any, Dict, Iterable, Optional, Tuple, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models import REGISTRY, ALIASES  # registro dinámico + alias
from supabase_client import upload_and_get_url  # subida + signed url

# -------------------------- Config & App --------------------------

def _split_origins(s: Optional[str]) -> list[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]

CORS_ALLOW = os.getenv("CORS_ALLOW_ORIGINS", "")
origins = _split_origins(CORS_ALLOW) or ["*"]

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
    size: float = 6.0           # alto del texto (mm)
    depth: float = 1.2          # espesor extrusión (mm)
    mode: str = "engrave"       # "engrave" (resta) | "emboss" (suma)
    pos: list[float] = Field(default_factory=lambda: [0, 0, 0])  # x,y,z (mm)
    rot: list[float] = Field(default_factory=lambda: [0, 0, 0])  # rx,ry,rz (deg)
    font: Optional[str] = None

class GenerateBody(BaseModel):
    slug: str
    params: Dict[str, Any] = Field(default_factory=dict)
    holes: Optional[Iterable[Dict[str, Any]]] = None
    text_ops: Optional[list[TextOp]] = None

# -------------------------- Helpers --------------------------

def _norm_slug(s: str) -> str:
    """
    Normaliza el slug para el registro:
    - pasa a minúsculas
    - convierte kebab->snake
    - aplica ALIASES si procede
    """
    if not s:
        return s
    raw = s.strip().lower()
    snake = raw.replace("-", "_")
    return ALIASES.get(raw, ALIASES.get(snake, snake))

def _as_stl_bytes(obj: Any) -> Tuple[bytes, Optional[str]]:
    """
    Normaliza cualquier salida del builder a un STL binario.
    Acepta: bytes/bytearray, BytesIO/file-like, str (ruta o STL ASCII),
    objetos con .export(file_obj, file_type="stl") (p.ej. trimesh meshes),
    o dict/tuplas/listas con uno o varios items convertibles.
    """
    # bytes directos
    if isinstance(obj, (bytes, bytearray)):
        return (bytes(obj), None)

    # file-like
    if hasattr(obj, "read"):
        return (obj.read(), None)

    # string: ruta o STL ASCII
    if isinstance(obj, str):
        if os.path.exists(obj):
            with open(obj, "rb") as f:
                return (f.read(), os.path.basename(obj))
        # ASCII STL en texto:
        if obj.strip().startswith("solid"):
            return (obj.encode("utf-8"), None)

    # trimesh / objetos con .export
    if hasattr(obj, "export"):
        buf = io.BytesIO()
        try:
            obj.export(buf, file_type="stl")
        except TypeError:
            # algunas versiones requieren (file_obj=..., file_type=...)
            obj.export(file_obj=buf, file_type="stl")
        return (buf.getvalue(), None)

    # colecciones: tomar el primero convertible (o concatenar en el futuro)
    if isinstance(obj, (list, tuple)):
        for it in obj:
            try:
                data, name = _as_stl_bytes(it)
                return (data, name)
            except Exception:
                continue

    raise TypeError("Builder returned unsupported type for STL export")

# -------------------------- Core Endpoint --------------------------

@app.get("/health")
def health():
    return {"ok": True, "service": "forge-stl", "origins": origins}

@app.post("/generate")
def generate(body: GenerateBody):
    """
    Entrada principal:
      - slug: admite kebab o snake, y alias (p.ej. 'vesa-adapter' -> 'vesa_adapter').
      - params: dict con dimensiones, fillet_mm, etc.
      - text_ops: lista de operaciones de texto (engrave/emboss).
    Devuelve: { ok, slug, path, url, signed_url }
    """
    slug = _norm_slug(body.slug)
    if slug not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")

    builder = REGISTRY[slug]

    # fusiona params “limpios”
    params = dict(body.params or {})
    # soporte suave a alias de nombres de parámetros comunes
    for a, b in (("round_mm", "fillet_mm"),):
        if a in params and b not in params:
            params[b] = params[a]

    # las text_ops las pasamos como lista de dicts simples (para models.apply_text_ops)
    text_ops = [op.dict() for op in (body.text_ops or [])]

    # genera mesh/objeto exportable
    try:
        result = builder(params)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Model build error: {e}")

    # algunos builders ya devuelven mesh con texto aplicado; si no, intentamos aplicar
    # vía función util en models (si existe)
    from models import apply_text_ops as _try_apply_text  # opcional en tu repo
    try:
        if text_ops:
            result = _try_apply_text(result, text_ops)
    except Exception:
        # si no existe o falla, seguimos con la geometría base
        pass

    # serializa a STL binario
    stl_bytes, maybe_name = _as_stl_bytes(result)

    # nombre destino en bucket
    filename = maybe_name or "forge-output.stl"
    key = f"{slug}/{filename}"

    # sube a Supabase y devuelve urls
    try:
        out = upload_and_get_url(stl_bytes, key=key)
        # esperado: {"path": key, "url": public_url, "signed_url": signed}
        return {
            "ok": True,
            "slug": slug,
            **out,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {e}")
