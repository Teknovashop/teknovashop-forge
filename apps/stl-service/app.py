# apps/stl-service/app.py
import io
import os
from typing import Any, Dict, Iterable, Optional, Tuple

from fastapi import FastAPI, HTTPException
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
    size: float = 6.0
    depth: float = 1.2
    mode: str = "engrave"        # "engrave" | "emboss"
    pos: list[float] = Field(default_factory=lambda: [0, 0, 0])
    rot: list[float] = Field(default_factory=lambda: [0, 0, 0])
    font: Optional[str] = None

class GenerateBody(BaseModel):
    slug: str                     # <- requerido por tus builders
    params: Dict[str, Any] = Field(default_factory=dict)
    holes: Optional[Iterable[Dict[str, Any]]] = None
    text_ops: Optional[list[TextOp]] = None
    # compat: algunos clientes podrían seguir enviando "model"
    model: Optional[str] = None

# -------------------------- Helpers --------------------------

def _norm_slug(s: str) -> str:
    if not s:
        return s
    raw = s.strip().lower()
    snake = raw.replace("-", "_")
    return ALIASES.get(raw, ALIASES.get(snake, snake))

def _as_stl_bytes(obj: Any) -> Tuple[bytes, Optional[str]]:
    # bytes/bytearray
    if isinstance(obj, (bytes, bytearray)):
        return (bytes(obj), None)
    # file-like
    if hasattr(obj, "read"):
        return (obj.read(), None)
    # string: ruta o ASCII STL
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
    # colecciones: intenta el primero convertible
    if isinstance(obj, (list, tuple)):
        for it in obj:
            try:
                data, name = _as_stl_bytes(it)
                return (data, name)
            except Exception:
                continue
    raise TypeError("Builder returned unsupported type for STL export")

# -------------------------- Endpoints --------------------------

@app.get("/health")
def health():
    return {"ok": True, "service": "forge-stl", "origins": origins}

@app.post("/generate")
def generate(body: GenerateBody):
    # slug normalizado (admite kebab/snake/alias)
    slug = _norm_slug(body.slug or body.model or "")
    if not slug or slug not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")

    builder = REGISTRY[slug]

    # params saneados + alias comuns
    params = dict(body.params or {})
    if "round_mm" in params and "fillet_mm" not in params:
        try:
            params["fillet_mm"] = float(params["round_mm"])
        except Exception:
            pass

    # genera base
    try:
        result = builder(params)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Model build error: {e}")

    # aplicar texto si existe la utilidad en tu paquete 'models' (OPCIONAL)
    _try_apply_text = None
    try:
        from models import apply_text_ops as _apply  # puede no existir
        _try_apply_text = _apply
    except Exception:
        _try_apply_text = None

    if _try_apply_text and body.text_ops:
        try:
            result = _try_apply_text(result, [op.dict() for op in body.text_ops])
        except Exception:
            # si falla el texto, seguimos con la geometría base
            pass

    # serializar STL
    stl_bytes, maybe_name = _as_stl_bytes(result)
    filename = maybe_name or "forge-output.stl"
    key = f"{slug}/{filename}"

    # subir y devolver URLs
    try:
        out = upload_and_get_url(stl_bytes, key=key)
        # esperado del helper: {"path": key, "url": public_url, "signed_url": signed_url}
        return {"ok": True, "slug": slug, **out}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {e}")
