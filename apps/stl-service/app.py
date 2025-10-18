# apps/stl-service/app.py
import io
import os
from typing import Any, Dict, Iterable, Optional, Tuple, List

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

# -------------------------- Endpoints --------------------------

@app.get("/health")
def health():
    return {"ok": True, "service": "forge-stl", "origins": origins}

@app.post("/generate")
def generate(body: GenerateBody):
    """
    Genera STL:
      - slug: admite kebab o snake; se normaliza a snake para el builder
      - storage: guarda en carpeta kebab-case <slug>/forge-output.stl
      - text_ops: opcional (si hay util en models)
    """
    # 1) Slug para builder y para storage
    builder_slug = _norm_slug_for_builder(body.slug or body.model or "")
    if not builder_slug or builder_slug not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Model '{builder_slug}' not found")
    storage_slug = _slug_for_storage(builder_slug)

    builder = REGISTRY[builder_slug]

    # 2) Params saneados + alias round->fillet
    params = dict(body.params or {})
    if "round_mm" in params and "fillet_mm" not in params:
        try:
            params["fillet_mm"] = float(params["round_mm"])
        except Exception:
            pass

    # 3) Geometría base
    try:
        result = builder(params)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Model build error: {e}")

    # 4) Texto opcional (import opcional, no rompe si no existe)
    try:
        from models import apply_text_ops as _apply_text_ops
        if body.text_ops:
            result = _apply_text_ops(result, [op.dict() for op in body.text_ops])
    except Exception:
        # si no existe o falla el texto, seguimos con la base
        pass

    # 5) Serializar STL
    stl_bytes, maybe_name = _as_stl_bytes(result)
    filename = maybe_name or "forge-output.stl"
    object_path = f"{storage_slug}/{filename}"  # SIEMPRE kebab en el bucket

    # 6) Subir (el helper NO acepta keyword 'key', va posicional)
    try:
        # esperado: upload_and_get_url(data_bytes, object_path) -> dict con {path,url,signed_url}
        out = upload_and_get_url(stl_bytes, object_path)  # <-- POSICIONAL
        return {"ok": True, "slug": builder_slug, "path": object_path, **(out or {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {e}")

# -------------------------- Mantenimiento (opcional) --------------------------

@app.post("/admin/cleanup-underscore")
def cleanup_underscore(request: Request):
    """
    Borra TODAS las claves del bucket cuyo primer segmento contenga '_'.
    Protegido por 'CLEANUP_TOKEN' (enviar como header 'x-cleanup-token').
    Úsalo una sola vez para limpiar carpetas snake_case antiguas.
    """
    token = request.headers.get("x-cleanup-token", "")
    if not CLEANUP_TOKEN or token != CLEANUP_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # lazy import para no cargar si no se usa
    try:
        from supabase import create_client
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase client not available: {e}")

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

        # Listar todos los objetos del bucket (paginando)
        removed: List[str] = []
        page = 0
        page_size = 1000
        while True:
            # Nota: el SDK retorna lista de dicts con 'name'
            listing = supabase.storage.from_(SUPABASE_BUCKET).list("", {"limit": page_size, "offset": page * page_size, "sortBy": {"column": "name", "order": "asc"}})
            items = listing or []
            if not items:
                break
            to_remove: List[str] = []
            for it in items:
                name = it.get("name") or ""
                # Primer segmento (carpeta)
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
