# apps/stl-service/app.py
import io
import os
from typing import Any, Dict, Callable, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Registro de modelos existente en tu repo
from models import REGISTRY, ALIASES  # ALIASES puede estar vacío; no pasa nada

from supabase_client import upload_and_get_url

app = FastAPI()

# --- CORS (permite tu frontend) ---
allowed_origins = [
    os.getenv("FRONTEND_ORIGIN") or os.getenv("NEXT_PUBLIC_SITE_URL") or "*",
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
    # En el futuro puedes añadir rotaciones o z: rx, ry, rz, z, etc.

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

# --------- Salud ---------
@app.get("/health")
async def health():
    return {"ok": True}

# --------- Util: resolver modelo en el registro ---------
def _resolve_model_entry(model_key: str) -> tuple[str, Any]:
    """
    Devuelve (key_resuelta, entry) donde entry puede ser:
      - función builder(params) -> bytes/BytesIO
      - dict con 'make' o 'builder'
    Intenta variantes con guion/guion_bajo y minúsculas, y usa ALIASES si aplica.
    """
    if not model_key:
        return model_key, None  # type: ignore

    raw = model_key.strip()
    candidates = []

    # Original tal cual
    candidates.append(raw)
    # slug comunes
    candidates.append(raw.replace(" ", "_"))
    candidates.append(raw.replace(" ", "-"))
    candidates.append(raw.replace("-", "_"))
    candidates.append(raw.replace("_", "-"))

    # Minúsculas (por si en UI llega con mayúsculas)
    low = raw.lower()
    if low != raw:
        candidates.extend([
            low,
            low.replace(" ", "_"),
            low.replace(" ", "-"),
            low.replace("-", "_"),
            low.replace("_", "-"),
        ])

    # Aliases explícitos
    for c in list(candidates):
        alias = ALIASES.get(c) if isinstance(ALIASES, dict) else None
        if alias:
            candidates.append(alias)

    # Primera coincidencia en REGISTRY
    for c in candidates:
        entry = REGISTRY.get(c)
        if entry is not None:
            return c, entry

    return raw, None  # type: ignore

def _resolve_builder(entry: Any, model_key: str) -> Callable[[Dict[str, Any]], Any]:
    """
    A partir de la entry del registro, devuelve un callable builder(params).
    Acepta función directa o dict con 'make'/'builder'.
    """
    if callable(entry):
        return entry  # función directa

    if isinstance(entry, dict):
        make = entry.get("make") or entry.get("builder")
        if callable(make):
            return make

    raise HTTPException(status_code=500, detail=f"bad-registry-entry:{model_key}")

# --------- Generate ---------
@app.post("/generate")
async def generate(body: GenerateBody, request: Request):
    model_key_input = (body.model or "").strip()

    resolved_key, entry = _resolve_model_entry(model_key_input)
    if entry is None:
        available = sorted(REGISTRY.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_key_input}' not found. Available: {', '.join(available)}"
        )

    # Soporta función directa o dict {'make': fn} / {'builder': fn}
    make_fn = _resolve_builder(entry, resolved_key)

    # Prepara parámetros “planos” que esperan los modelos existentes
    p: Dict[str, Any] = {
        "length_mm": float(body.params.length_mm),
        "width_mm": float(body.params.width_mm),
        "height_mm": float(body.params.height_mm),
        # Algunos modelos no usan thickness/fillet; pasarlos es inocuo.
        "thickness_mm": float(body.params.thickness_mm) if body.params.thickness_mm else None,
        "fillet_mm": float(body.params.fillet_mm) if body.params.fillet_mm else None,
        # Extras
        "holes": [h.model_dump() for h in body.params.holes],
        "arrayOps": [a.model_dump() for a in body.params.arrayOps],
        "textOps": [t.model_dump() for t in body.params.textOps],
    }

    # Llama al builder real
    try:
        stl_bytes: bytes | bytearray | io.BytesIO = make_fn(p)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model build error: {e}")

    # Normaliza a bytes para la subida (evita el error de BytesIO)
    if isinstance(stl_bytes, io.BytesIO):
        stl_data = stl_bytes.getvalue()
    elif isinstance(stl_bytes, (bytes, bytearray)):
        stl_data = bytes(stl_bytes)
    else:
        raise HTTPException(status_code=500, detail="Builder must return bytes or BytesIO")

    # Nombre de archivo “bonito”
    out_name = f"{resolved_key}.stl"
    up = upload_and_get_url(
        stl_data,
        bucket=os.getenv("SUPABASE_BUCKET") or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET") or "forge-stl",
        folder="stl",
        filename=out_name,
    )

    if not up.get("ok"):
        raise HTTPException(status_code=500, detail=up.get("error") or "Upload failed")

    # Normaliza la respuesta para el front
    resp: Dict[str, Any] = {"ok": True, "path": up.get("path")}
    if up.get("url"):
        resp["stl_url"] = up["url"]
    if up.get("signed_url"):
        resp["signed_url"] = up["signed_url"]
    return resp
