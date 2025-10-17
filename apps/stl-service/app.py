import io
import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Importa el registry dinámico que construimos arriba
from models import REGISTRY, ALIASES

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
    # Si en el futuro añades rotación/altura, extiende aquí (rx, ry, rz, z, etc.)

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

# --------- Generate ---------
@app.post("/generate")
async def generate(body: GenerateBody, request: Request):
    model_key = (body.model or "").strip()

    # Alias: si el nombre de UI difiere del nombre de fichero
    model_lookup = REGISTRY.get(model_key)
    if model_lookup is None and model_key in ALIASES:
        model_lookup = REGISTRY.get(ALIASES[model_key])

    if model_lookup is None:
        # Mensaje claro + lista de disponibles (solo en dev)
        available = sorted(REGISTRY.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model_key}' not found. Available: {', '.join(available)}"
        )

    # model_lookup puede ser función make(...) o un dict con {'make': fn}
    if callable(model_lookup):
        make_fn = model_lookup
    elif isinstance(model_lookup, dict):
        make_fn = model_lookup.get("make") or model_lookup.get("builder")
        if not callable(make_fn):
            raise HTTPException(status_code=500, detail="Invalid model registry entry (no callable).")
    else:
        raise HTTPException(status_code=500, detail="Invalid model registry entry.")

    # Prepara parámetros “planos” que esperan los modelos existentes
    p = {
        "length_mm": float(body.params.length_mm),
        "width_mm": float(body.params.width_mm),
        "height_mm": float(body.params.height_mm),
        # Algunos modelos no usan thickness/fillet; pasarlos no les molesta.
        "thickness_mm": float(body.params.thickness_mm) if body.params.thickness_mm else None,
        "fillet_mm": float(body.params.fillet_mm) if body.params.fillet_mm else None,
        # Extras:
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
    out_name = f"{model_key}.stl"
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
