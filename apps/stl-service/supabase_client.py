# apps/stl-service/supabase_client.py
import io
import os
import time
from typing import Optional, Dict, Any

from supabase import create_client, Client  # supabase-py

_SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
_SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
_STORAGE_BUCKET = os.getenv("SUPABASE_BUCKET", "stl")
_SIGN_SECONDS = int(os.getenv("SUPABASE_SIGN_SECONDS", str(7 * 24 * 3600)))  # 7 días

_supabase: Optional[Client] = None


def _get_client() -> Client:
    global _supabase
    if _supabase is None:
        if not _SUPABASE_URL or not _SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL o SUPABASE_*_KEY no configurados")
        _supabase = create_client(_SUPABASE_URL, _SUPABASE_KEY)
    return _supabase


def _norm_path(*parts: str) -> str:
    p = "/".join([s.strip("/ ") for s in parts if s is not None and s != ""])
    return p


def upload_and_get_url(
    fileobj: io.BufferedIOBase,
    *,
    folder: Optional[str] = None,
    filename: str = "output.stl",
) -> Dict[str, Any]:
    """
    Sube el contenido de `fileobj` al bucket y devuelve una URL firmada.
    Acepta cualquier file-like que implemente .read().
    """
    sb = _get_client()

    # Normaliza ruta: <folder>/<filename>
    path = _norm_path(folder or "", filename)

    # Lee bytes (adm. también que te pasen bytes por error)
    if hasattr(fileobj, "read"):
        data = fileobj.read()
    else:
        # si llega un bytes/bytearray por compatibilidad
        data = bytes(fileobj)

    # Subida con overwrite=True para despliegues repetibles
    _ = sb.storage.from_(_STORAGE_BUCKET).upload(
        path=path,
        file=data,
        file_options={"contentType": "model/stl", "upsert": True},
    )

    # URL firmada
    signed = sb.storage.from_(_STORAGE_BUCKET).create_signed_url(path, _SIGN_SECONDS)
    url = signed.get("signedURL") or signed.get("signed_url") or signed.get("url")

    # Fallback: URL pública si el bucket es público
    if not url:
        public_url = sb.storage.from_(_STORAGE_BUCKET).get_public_url(path)
        url = public_url.get("publicURL") or public_url.get("public_url")

    return {"bucket": _STORAGE_BUCKET, "path": path, "url": url}
