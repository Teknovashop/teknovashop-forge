# apps/stl-service/app.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import io, time
from .models import build_model
from .supabase_client import upload_and_get_url

app = FastAPI()

origins = (os.getenv("CORS_ALLOW_ORIGINS") or "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"ok": True, "ts": int(time.time())}

@app.post("/generate")
async def generate(req: Request):
    body = await req.json()
    slug = body.get("model") or body.get("slug") or "cable_tray"
    params = body.get("params") or {}
    text_ops = body.get("text_ops") or body.get("textOps") or []

    try:
        mesh = build_model(slug, params, text_ops=text_ops)
    except KeyError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"build-failed: {e}"}, status_code=500)

    stl_bytes = mesh.export(file_type="stl")

    # subir a Supabase
    filename = f"{slug}.stl"
    folder = body.get("folder") or slug
    up = upload_and_get_url(stl_bytes, folder=folder, filename=filename)

    if not up.get("ok"):
        return JSONResponse({"ok": False, "error": up.get("error", "upload-failed")}, status_code=500)

    # unificar claves esperadas por el front
    payload = {"ok": True, "size": len(stl_bytes), **({k: v for k, v in up.items() if k in ("url", "signed_url", "path")})}
    # espejo compatible
    if "url" in payload:
        payload["stl_url"] = payload["url"]
    elif "signed_url" in payload:
        payload["stl_url"] = payload["signed_url"]

    return JSONResponse(payload, status_code=200)
