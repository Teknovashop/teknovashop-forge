import io, os, json
from fastapi import FastAPI
from pydantic import BaseModel
import cadquery as cq
from utils.supa import put_bytes, hash_key, BUCKET_STL, BUCKET_DXF, BUCKET_PNG
from models import REGISTRY

app = FastAPI(title="Forge CAD v2")

class TextOpt(BaseModel):
    value: str
    height_mm: float = 8
    depth_mm: float = 0.6
    mode: str = "engrave"  # engrave | emboss
    font: str | None = None

class GenReq(BaseModel):
    model: str
    params: dict
    holes: list[dict] | None = None
    text: TextOpt | None = None
    outputs: list[str] = ["stl"]  # "stl","png","dxf"

def norm_model(m: str) -> str:
    return (m or "cable_tray").replace("-", "_")

@app.post("/v2/generate")
def generate(req: GenReq):
    mid = norm_model(req.model)
    if mid not in REGISTRY:
        return {"error": f"model '{mid}' not found"}, 400

    # build solid
    part = REGISTRY[mid](req.params or {}, req.text.model_dump() if req.text else None)

    # hash para cache/paths
    key = hash_key(mid, json.dumps(req.params, sort_keys=True), json.dumps(req.text.model_dump() if req.text else {}, sort_keys=True))
    base = f"{mid}/{key}"

    out = {}

    # STL
    if "stl" in req.outputs:
      stl_bytes = cq.exporters.export(part, cq.exporters.ExportTypes.STL, tolerance=0.1)
      if isinstance(stl_bytes, str):
          stl_bytes = stl_bytes.encode()
      stl_url = put_bytes(BUCKET_STL, f"{base}.stl", stl_bytes, "model/stl")
      out["stl_url"] = stl_url

    # PNG render simple (screenshot no-OpenGL: bounding box raster)
    if "png" in req.outputs:
      # Placeholder: genera una imagen básica con Pillow (puedes sustituir por render Three server)
      from PIL import Image, ImageDraw, ImageFont
      img = Image.new("RGB", (1200, 800), (20,20,24))
      d = ImageDraw.Draw(img)
      d.text((24,24), f"FORGE v2: {mid}", fill=(230,230,235))
      buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
      out["png_url"] = put_bytes(BUCKET_PNG, f"{base}.png", buf.getvalue(), "image/png")

    # DXF (proyección 2D)
    if "dxf" in req.outputs:
      # Export simple: perfil superior como DXF (wire)
      try:
        dxf_str = cq.exporters.export(part, cq.exporters.ExportTypes.DXF)
        if isinstance(dxf_str, bytes) is False:
            dxf_str = dxf_str.encode()
        out["dxf_url"] = put_bytes(BUCKET_DXF, f"{base}.dxf", dxf_str, "image/vnd.dxf")
      except Exception as e:
        out["dxf_error"] = str(e)

    out["design_id"] = key
    return out
