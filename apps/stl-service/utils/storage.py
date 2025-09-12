# utils/storage.py
import os
from supabase import create_client, Client

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

def upload_to_supabase(local_path: str, bucket: str, key: str) -> str:
    """
    Sube un archivo a Supabase Storage y devuelve una URL firmada (1h).
    Nota: en supabase-py v2, 'upsert' debe ir como string "true"/"false".
    """
    # Abrimos como file-like; es lo que mejor se lleva el SDK
    with open(local_path, "rb") as f:
        res = supabase.storage.from_(bucket).upload(
            path=key,
            file=f,  # file-like object
            file_options={
                "contentType": "model/stl",  # o "application/sla"
                "upsert": "true"             # <- STRING, no boolean
            },
        )

    # Manejo de error del SDK (por si devuelve dict con 'error')
    if isinstance(res, dict) and res.get("error"):
        raise RuntimeError(res["error"]["message"])

    signed = supabase.storage.from_(bucket).create_signed_url(
        path=key,
        expires_in=3600
    )
    # La key puede llamarse 'signedURL' o 'signed_url' según versión
    return signed.get("signedURL") or signed.get("signed_url")
