import os
import io
from typing import Optional, Union, Dict, Any
from supabase import create_client, Client

_SUPABASE: Optional[Client] = None

def _norm_url(url: str) -> str:
    url = (url or "").strip()
    return url if not url or url.endswith("/") else (url + "/")

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
    data: Union[bytes, bytearray, io.BytesIO],
    *,
    bucket: Optional[str] = None,
    folder: str = "",
    filename: str = "",
) -> Dict[str, Any]:
    client = get_client()
    bucket_name = bucket or os.getenv("SUPABASE_BUCKET") or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET") or "forge-stl"
    if not filename:
        filename = "model.stl"
    folder = folder.strip("/")

    path = f"{folder}/{filename}" if folder else filename

    # ---> AQUI: garantizamos BYTES
    if isinstance(data, io.BytesIO):
        payload = data.getvalue()
    elif isinstance(data, (bytes, bytearray)):
        payload = bytes(data)
    else:
        raise TypeError("upload_and_get_url: data must be bytes/bytearray/BytesIO")

    try:
        # La SDK acepta `upload(path, file=...)` o `upload(path, data=bytes)`.
        # Para evitar problemas, usamos bytes crudos.
        client.storage.from_(bucket_name).upload(
            path=path,
            file=payload,
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
