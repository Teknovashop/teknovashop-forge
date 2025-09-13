import os
from typing import Any, Dict
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def upload_to_supabase(local_path: str, bucket: str, key: str) -> str:
    # Sube el archivo (upsert=True para sobrescribir si ya existe)
    with open(local_path, "rb") as f:
        supabase.storage.from_(bucket).upload(
            file=f,
            path=key,
            file_options={"content-type": "model/stl"},
            upsert=True,
        )
    # Crea URL firmada durante 1 hora
    signed = supabase.storage.from_(bucket).create_signed_url(path=key, expires_in=3600)
    if isinstance(signed, dict):
        return signed.get("signedURL") or signed.get("signed_url") or ""
    # Algunas versiones pueden devolver un string directamente
    return str(signed)
