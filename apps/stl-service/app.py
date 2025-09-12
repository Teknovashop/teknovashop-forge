# apps/stl-service/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import cadquery as cq
import tempfile, os
from utils.storage import upload_to_supabase
from utils.watermark import apply_text_watermark

app = FastAPI()  # <<--- ESTA variable debe llamarse exactamente "app"

class GenReq(BaseModel):
    order_id: str
    model_slug: str
    params: dict
    license: str  # 'personal' | 'commercial'

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/generate")
def generate(req: GenReq):
    try:
        if req.model_slug == 'vesa-adapter':
            stl = vesa_adapter(**req.params)
        elif req.model_slug == 'router-mount':
            stl = router_mount(**req.params)
        elif req.model_slug == 'cable-tray':
            stl = cable_tray(**req.params)
        else:
            raise HTTPException(400, 'Unknown model')

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, f"{req.model_slug}-{req.order_id}.stl")
            cq.exporters.export(stl, path)
            if req.license == 'commercial':
                apply_text_watermark(path, text=os.getenv('WATERMARK_TEXT','Teknovashop'))
            url = upload_to_supabase(
                path,
                bucket=os.getenv('SUPABASE_BUCKET','forge-stl'),
                key=f"{req.order_id}/{os.path.basename(path)}"
            )
        return {"status":"ok", "stl_url": url}
    except Exception as e:
        raise HTTPException(500, str(e))

# === modelos ===
from models.vesa_adapter import build as vesa_adapter
from models.router_mount import build as router_mount
from models.cable_tray import build as cable_tray
