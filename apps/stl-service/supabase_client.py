# /supabase_client.py
import os
import time
from typing import Dict, Any

from supabase import create_client, Client  # type: ignore


def _get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or ""
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or ""
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_KEY environment variables")

    # Asegura la barra final para evitar: "Storage endpoint URL should have a trailing slash."
    if not url.endswith("/"):
        url = url + "/"

    return create_client(url, key)


def upload_and_get_url(
    data: bytes,
    bucket: str,
    folder: str,
    filename: str,
) -> Dict[str, Any]:
    try:
        supa = _get_supabase()
        path = f"{folder.rstrip('/')}/{int(time.time())}_{filename}"
        # Subir como bytes
        res = supa.storage.from_(bucket).upload(path=path, file=data, file_options={"contentType": "model/stl"})
        # Algunas versiones devuelven None si ya existe; forzamos overwrite si hace falta
        if res is None:
            # intenta overwrite
            supa.storage.from_(bucket).update(path=path, file=data, file_options={"contentType": "model/stl", "upsert": True})

        # URL pública (si el bucket es público) o firmada
        try:
            public_url = supa.storage.from_(bucket).get_public_url(path)
        except Exception:
            public_url = None

        signed_url = None
        try:
            signed = supa.storage.from_(bucket).create_signed_url(path, expires_in=60 * 60)
            signed_url = signed.get("signedURL") if isinstance(signed, dict) else None
        except Exception:
            pass

        return {"ok": True, "path": path, "url": public_url, "signed_url": signed_url}
    except Exception as e:
        return {"ok": False, "error": str(e)}
