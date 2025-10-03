from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, time

app = FastAPI(title="teknovashop-forge addons (safe)")
origins = os.getenv("CORS_ALLOW_ORIGINS","").split(",") if os.getenv("CORS_ALLOW_ORIGINS") else ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"ok":True,"ts":time.time()}

class SignedUrlOut(BaseModel):
    signed_url: str

try:
    from supabase import create_client, Client  # type: ignore
    have_supabase = True
except Exception:
    have_supabase = False

@app.get("/signed-url", response_model=SignedUrlOut)
def signed_url(path: str):
    if not have_supabase:
        raise HTTPException(status_code=500, detail="Supabase SDK no disponible.")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    bucket = os.getenv("SUPABASE_BUCKET","forge-stl")
    if not url or not key:
        raise HTTPException(status_code=500, detail="Faltan credenciales de Supabase.")
    client: Client = create_client(url, key)
    res = client.storage.from_(bucket).create_signed_url(path, 60)
    if not res or "signedURL" not in res:
        raise HTTPException(status_code=500, detail="No se pudo generar signed URL.")
    return {"signed_url": res["signedURL"]}
