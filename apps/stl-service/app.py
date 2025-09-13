from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from pathlib import Path
import tempfile
import os

from storage import upload_to_supabase

app = FastAPI(title="Teknovashop Forge API")

class GenerateRequest(BaseModel):
    order_id: str
    model_slug: str
    params: Dict[str, Any] = Field(default_factory=dict)
    license: Optional[str] = "personal"

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}

@app.post("/generate")
async def generate(body: GenerateRequest) -> Dict[str, str]:
    # --- Simulación de generación STL (sustituye con tu lógica real) ---
    tmpdir = Path(tempfile.gettempdir())
    filename = f"{body.model_slug}-{body.order_id}.stl"
    local_path = tmpdir / filename
    # Escribe un STL mínimo válido
    local_path.write_text("solid teknovashop\nendsolid teknovashop\n", encoding="utf-8")

    # --- Subida a Supabase Storage ---
    bucket = os.getenv("SUPABASE_BUCKET", "forge-stl")
    key = f"{body.order_id}/{filename}"
    try:
        signed_url = upload_to_supabase(str(local_path), bucket, key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {e}")

    if not signed_url:
        raise HTTPException(status_code=500, detail="No STL URL generated")

    return {"status": "ok", "stl_url": signed_url}
