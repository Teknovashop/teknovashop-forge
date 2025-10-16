# apps/stl-service/supabase_client.py
import os
import io
from typing import Optional, Union, Dict, Any
from supabase import create_client, Client

_SUPABASE: Optional[Client] = None

def _norm_url(url: str) -> str:
    url = (url or "").strip()
    return url if url.endswith("/") else (url + "/") if url else url

def get_client() -> Client:
    global _SUPABASE
    if _SUPABASE is not None:
        return _SUPABASE

    url = _norm_url(os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL o SUPABASE_*_KEY no configurados")

    _SUPABASE = create_client(url, key)
    return _SUPABASE

def upload_and_get_url(
    data: Union[bytes, io.BytesIO],
    *,
    bucket: Optional[str] = None,
    folder: str = "",
    filename: str = "",
) -> Dict[str, Any]:
    """
    Sube bytes STL a Supabase Storage y devuelve:
    {
      "ok": True/False,
      "url": "https://... (si público)",
      "signed_url": "https://... (si privado)",
      "path": "folder/filename"
    }
    """
    client = get_client()
    bucket_name = bucket or os.getenv("SUPABASE_BUCKET") or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET") or "forge-stl"
    if not filename:
        filename = "model.stl"
    folder = folder.strip("/")

    path = f"{folder}/{filename}" if folder else filename

    # Aseguramos bytes (no BytesIO) para compatibilidad con supabase-py que corre en Render
    raw: bytes
    if isinstance(data, (bytes, bytearray)):
        raw = bytes(data)
    else:
        bio = data  # BytesIO
        bio.seek(0)
        raw = bio.getvalue()

    try:
        client.storage.from_(bucket_name).upload(
            path=path,
            file=raw,  # <- bytes, no BytesIO
            file_options={"content-type": "model/stl", "cache-control": "public, max-age=31536000"},
        )
    except Exception as e:
        return {"ok": False, "error": f"upload-failed: {e}", "path": path}

    # Pública
    try:
        public_url = client.storage.from_(bucket_name).get_public_url(path)
        if public_url:
            return {"ok": True, "url": public_url, "path": path}
    except Exception:
        pass

    # Firmada (bucket privado)
    try:
        signed = client.storage.from_(bucket_name).create_signed_url(path, 60 * 60)  # 1h
        return {"ok": True, "signed_url": signed, "path": path}
    except Exception as e:
        return {"ok": False, "error": f"url-failed: {e}", "path": path}
