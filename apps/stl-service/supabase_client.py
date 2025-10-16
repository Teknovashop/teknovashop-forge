# apps/stl-service/supabase_client.py
import os
import io
from typing import Optional, Union, Dict, Any
from supabase import create_client, Client

_SUPABASE: Optional[Client] = None


def _norm_url(url: str) -> str:
    """
    Normaliza la URL para que SIEMPRE termine en barra.
    Evita el aviso: "Storage endpoint URL should have a trailing slash."
    """
    url = (url or "").strip()
    return (url.rstrip("/") + "/") if url else ""


def _first_str(*vals) -> Optional[str]:
    """
    Devuelve el primer valor que sea str no vacío.
    Útil para manejar dicts/formatos distintos del SDK.
    """
    for v in vals:
        if isinstance(v, str) and v:
            return v
        if isinstance(v, dict):
            # Soporta claves típicas que devuelve supabase-py
            cand = v.get("publicURL") or v.get("public_url") or v.get("signedURL") or v.get("signed_url") or v.get("url")
            if isinstance(cand, str) and cand:
                return cand
    return None


def get_client() -> Client:
    """
    Crea (una única vez) el cliente de Supabase usando SERVICE_KEY si existe,
    y si no, ANON_KEY. La URL se normaliza con barra final.
    """
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
    """
    Sube bytes STL a Supabase Storage y devuelve un dict homogéneo:
    {
      "ok": True/False,
      "url": "...",           # si el bucket es público
      "stl_url": "...",       # alias usado por el frontend
      "signed_url": "...",    # si el bucket es privado
      "path": "folder/file.stl",
      "error": "..."          # si falla
    }
    """
    client = get_client()
    bucket_name = (
        bucket
        or os.getenv("SUPABASE_BUCKET")
        or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET")
        or "forge-stl"
    )

    if not filename:
        filename = "model.stl"
    folder = folder.strip("/")

    path = f"{folder}/{filename}" if folder else filename

    # Normaliza a BytesIO
    if isinstance(data, (bytes, bytearray)):
        bio = io.BytesIO(data)
    else:
        # data es BytesIO (o similar)
        bio = io.BytesIO(data.read())
    bio.seek(0)

    # Subida
    try:
        client.storage.from_(bucket_name).upload(
            path=path,
            file=bio,
            file_options={
                # headers SIEMPRE deben ser str
                "content-type": "model/stl",
                "cache-control": "public, max-age=31536000",
            },
        )
    except Exception as e:
        return {"ok": False, "error": f"upload-failed: {e}", "path": path}

    # Intento 1: URL pública (bucket público)
    try:
        pub = client.storage.from_(bucket_name).get_public_url(path)
        public_url = _first_str(pub)
        if public_url:
            return {"ok": True, "url": public_url, "stl_url": public_url, "path": path}
    except Exception:
        pass

    # Intento 2: URL firmada (bucket privado)
    try:
        signed = client.storage.from_(bucket_name).create_signed_url(path, 60 * 60)  # 1h
        signed_url = _first_str(signed)
        if signed_url:
            return {"ok": True, "signed_url": signed_url, "stl_url": signed_url, "path": path}
        # por si el SDK devolviera el URL bajo otra clave
        return {"ok": True, "signed_url": signed, "stl_url": _first_str(signed) or "", "path": path}
    except Exception as e:
        return {"ok": False, "error": f"url-failed: {e}", "path": path}
