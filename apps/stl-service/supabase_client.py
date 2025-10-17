# /supabase_client.py
import os
import time
from typing import Dict, Any, Optional

try:
    # supabase-py v2.x
    from supabase import create_client, Client  # type: ignore
except Exception:
    create_client = None
    Client = None  # type: ignore


def _get_env(name: str) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v or None


def _get_supabase_creds() -> Dict[str, str]:
    """
    Recoge credenciales de Supabase aceptando múltiples nombres de variables.

    URL:
      - SUPABASE_URL
      - NEXT_PUBLIC_SUPABASE_URL

    KEY (preferimos service/role key si existe):
      - SUPABASE_SERVICE_KEY
      - SUPABASE_SERVICE_ROLE_KEY
      - SUPABASE_KEY
      - NEXT_PUBLIC_SUPABASE_ANON_KEY  (último recurso)

    BUCKET:
      - SUPABASE_BUCKET
      - NEXT_PUBLIC_SUPABASE_BUCKET
      - (fallback) "forge-stl"
    """
    url = (
        _get_env("SUPABASE_URL")
        or _get_env("NEXT_PUBLIC_SUPABASE_URL")
    )
    key = (
        _get_env("SUPABASE_SERVICE_KEY")
        or _get_env("SUPABASE_SERVICE_ROLE_KEY")
        or _get_env("SUPABASE_KEY")
        or _get_env("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    bucket = (
        _get_env("SUPABASE_BUCKET")
        or _get_env("NEXT_PUBLIC_SUPABASE_BUCKET")
        or "forge-stl"
    )

    if not url or not key:
        missing = []
        if not url:
            missing.append("SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL")
        if not key:
            missing.append(
                "SUPABASE_SERVICE_KEY/SUPABASE_SERVICE_ROLE_KEY/"
                "SUPABASE_KEY/NEXT_PUBLIC_SUPABASE_ANON_KEY"
            )
        raise RuntimeError(f"Missing {' & '.join(missing)} environment variables")

    # Normaliza URL (sin slash final para supabase-py)
    url = url.rstrip("/")

    return {"url": url, "key": key, "bucket": bucket}


def _get_client() -> "Client":
    if create_client is None:
        raise RuntimeError(
            "Supabase client library not available. "
            "Ensure 'supabase==2.*' is in requirements.txt"
        )
    creds = _get_supabase_creds()
    return create_client(creds["url"], creds["key"])


def upload_and_get_url(
    data: bytes,
    bucket: Optional[str] = None,
    folder: str = "stl",
    filename: str = "model.stl",
) -> Dict[str, Any]:
    """
    Sube 'data' al bucket y devuelve { ok, path, url?, signed_url? }.
    - Upsert habilitado (sobrescribe si existe).
    - Genera un signed_url de 7 días.
    """
    if not isinstance(data, (bytes, bytearray)):
        return {"ok": False, "error": "Data must be bytes"}

    creds = _get_supabase_creds()
    client = _get_client()
    bucket_name = bucket or creds["bucket"]

    # Asegura rutas limpias
    folder = (folder or "").strip("/ ")
    filename = filename.strip() or "model.stl"
    path = f"{folder}/{filename}" if folder else filename

    # Subida
    try:
        # upsert=True para evitar errores si ya existe
        client.storage.from_(bucket_name).upload(
            path=path,
            file=data,
            file_options={"content-type": "model/stl", "upsert": True},
        )
    except Exception as e:
        # Si el bucket no existe o hay otro problema, devuelve error limpio
        return {"ok": False, "error": f"Upload failed: {e}"}

    # Intentamos obtener public_url (si el bucket es público) y un signed_url
    public_url = None
    signed_url = None
    try:
        public_url = client.storage.from_(bucket_name).get_public_url(path)
        # Nota: en supabase-py v2, get_public_url devuelve dict o str según versión;
        # normalizamos a str si es dict
        if isinstance(public_url, dict):
            public_url = public_url.get("publicUrl") or public_url.get("public_url")
    except Exception:
        public_url = None

    try:
        # 7 días
        expires_in = 60 * 60 * 24 * 7
        su = client.storage.from_(bucket_name).create_signed_url(path, expires_in)
        if isinstance(su, dict):
            signed_url = su.get("signedURL") or su.get("signed_url") or su.get("signedUrl")
        else:
            signed_url = su
    except Exception:
        signed_url = None

    return {
        "ok": True,
        "path": path,
        "url": public_url,
        "signed_url": signed_url,
        "bucket": bucket_name,
        "ts": int(time.time()),
    }
