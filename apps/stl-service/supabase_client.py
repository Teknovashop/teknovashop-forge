# apps/stl-service/supabase_client.py
import io
import os
import time
from typing import Optional, Union, BinaryIO, Dict, Any

from supabase import create_client, Client


_CLIENT: Optional[Client] = None


def _env(name: str, fallback: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return fallback
    v = v.strip()
    return v or fallback


def get_client() -> Client:
    """
    Crea (singleton) el cliente oficial de Supabase con URL y KEY válidos.
    Acepta tanto SUPABASE_SERVICE_KEY como SUPABASE_SERVICE_ROLE_KEY.
    """
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    url = _env("SUPABASE_URL") or _env("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        _env("SUPABASE_SERVICE_KEY")
        or _env("SUPABASE_SERVICE_ROLE_KEY")
        or _env("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )

    if not url or not key:
        raise RuntimeError("SUPABASE_URL o SUPABASE_*_KEY no configurados")

    _CLIENT = create_client(url, key)
    return _CLIENT


def _get_bucket_name() -> str:
    return (
        _env("SUPABASE_BUCKET")
        or _env("NEXT_PUBLIC_SUPABASE_BUCKET")
        or "forge-stl"
    )


def upload_and_get_url(
    fileobj: Union[bytes, BinaryIO],
    *,
    folder: Optional[str] = None,
    filename: Optional[str] = None,
    mime: str = "model/stl",
    public: bool = True,
) -> Dict[str, Any]:
    """
    Sube al bucket y devuelve { url, path }.
    Acepta bytes o file-like. Si el bucket no es público, devuelve signed URL.
    """
    client = get_client()
    bucket = _get_bucket_name()

    # Normaliza path
    folder = (folder or "").strip().strip("/")
    name = (filename or f"file-{int(time.time())}.stl").strip().replace("/", "_")
    path = f"{folder}/{name}" if folder else name

    # Normaliza a bytes
    if isinstance(fileobj, (bytes, bytearray)):
        data = bytes(fileobj)
    else:
        # file-like
        data = fileobj.read()

    # Subida (si existe, sobreescribe)
    client.storage.from_(bucket).upload(
        path=path,
        file=data,
        file_options={"content-type": mime, "upsert": True},
    )

    # URL pública (si el bucket es público)…
    try:
        public_url = client.storage.from_(bucket).get_public_url(path)  # type: ignore
        if public_url and isinstance(public_url, str):
            return {"url": public_url, "path": path}
        if isinstance(public_url, dict) and public_url.get("publicUrl"):
            return {"url": public_url["publicUrl"], "path": path}
    except Exception:
        pass

    # …o firmada como fallback
    try:
        signed = client.storage.from_(bucket).create_signed_url(path, 60 * 60)  # 1 h
        if isinstance(signed, dict):
            url = signed.get("signedURL") or signed.get("signed_url") or signed.get("url")
            if url:
                return {"url": url, "path": path}
    except Exception:
        pass

    # Último recurso: devolver el path
    return {"url": None, "path": path}
