# apps/stl-service/supabase_client.py
import os
import io
from typing import Optional, Union, Dict, Any

from supabase import create_client, Client

_SUPABASE: Optional[Client] = None

def _norm_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    # la SDK insiste en el slash final para la parte de Storage
    return url if url.endswith("/") else url + "/"

def get_client() -> Client:
    global _SUPABASE
    if _SUPABASE is not None:
        return _SUPABASE

    url = _norm_url(os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "")
    # Preferimos SERVICE_ROLE para poder subir sin fricciones desde backend
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or ""
    if not url or not key:
        raise RuntimeError("SUPABASE_URL o SUPABASE_*_KEY no configurados")

    _SUPABASE = create_client(url, key)
    return _SUPABASE

def upload_and_get_url(fileobj: Union[bytes, io.BytesIO, io.BufferedIOBase],
                       folder: str,
                       filename: str,
                       bucket: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Sube a Supabase Storage y retorna {'url', 'path'}.
    - Acepta bytes o file-like.
    - Usa bucket de entorno: SUPABASE_BUCKET o NEXT_PUBLIC_SUPABASE_BUCKET
    """
    try:
        client = get_client()
    except Exception:
        return None

    bucket_name = bucket or os.getenv("SUPABASE_BUCKET") or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET") or "forge-stl"
    path = f"{folder.strip().strip('/')}/{filename}".replace("//", "/")

    # Aseguramos file-like
    if isinstance(fileobj, (bytes, bytearray)):
        bio = io.BytesIO(fileobj)
    else:
        bio = fileobj  # ya es file-like

    # La SDK maneja 'upsert' como parámetro, no como cabecera
    try:
        client.storage.from_(bucket_name).upload(
            path=path,
            file=bio,
            file_options={"content-type": "model/stl", "cache-control": "public, max-age=31536000", "upsert": True},
        )
    except Exception:
        # si ya existe o algo falla, intentamos upsert explícito
        try:
            client.storage.from_(bucket_name).update(
                path=path,
                file=bio,
                file_options={"content-type": "model/stl", "cache-control": "public, max-age=31536000"},
            )
        except Exception:
            return None

    # URL pública
    try:
        public_url = client.storage.from_(bucket_name).get_public_url(path)
    except Exception:
        public_url = None

    return {"url": public_url, "path": path}
