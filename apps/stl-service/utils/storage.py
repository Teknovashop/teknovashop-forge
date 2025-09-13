import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_KEY not set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def upload_to_supabase(local_path: str, bucket: str, key: str) -> str:
    # Lee el archivo y súbelo con opciones correctas para supabase-py v2
    with open(local_path, "rb") as f:
        supabase.storage.from_(bucket).upload(
            file=f,
            path=key,
            file_options={
                "contentType": "model/stl",  # <-- clave correcta
                "upsert": True               # <-- va dentro de file_options
            },
        )

    # Genera URL firmada (el SDK puede devolver distintos formatos)
    signed = supabase.storage.from_(bucket).create_signed_url(path=key, expires_in=3600)
    if isinstance(signed, dict):
        # devuelto por algunas versiones
        return signed.get("signedURL") or signed.get("data", {}).get("signedUrl") or ""
    return ""
