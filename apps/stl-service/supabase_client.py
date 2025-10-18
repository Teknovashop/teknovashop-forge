# apps/stl-service/supabase_client.py
import os
from typing import Dict, Optional

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")

_client = None

def _get():
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("Supabase ENV vars missing")
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client

def upload_and_get_url(data: bytes, object_path: str) -> Dict[str, Optional[str]]:
    """
    Sube el STL con content-type correcto y devuelve path + signed_url.
    - object_path debe ser relativo al bucket (p.ej. 'router-mount/forge-output.stl')
    """
    if not object_path or "/" not in object_path:
        # Evita volver a crear una carpeta "stl" por error: siempre <slug>/forge-output.stl
        raise ValueError("object_path must be '<slug>/forge-output.stl'")

    cli = _get()
    store = cli.storage.from_(SUPABASE_BUCKET)

    # Subir con upsert y content-type STL
    store.upload(
        object_path,
        data,
        {"contentType": "model/stl", "upsert": True},
    )

    # URL firmada (1 semana)
    signed_url = store.create_signed_url(object_path, 60 * 60 * 24 * 7).get("signedURL")  # SDK devuelve 'signedURL'
    return {"path": object_path, "signed_url": signed_url}
