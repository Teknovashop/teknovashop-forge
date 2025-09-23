# apps/stl-service/utils/storage.py

import os
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET_DEFAULT = os.environ.get("SUPABASE_BUCKET", "forge-stl")

BASE = f"{SUPABASE_URL}/storage/v1"
AUTH_HEADERS = {
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

def upload_stl_and_sign(
    data: bytes,
    key: str,
    bucket: str | None = None,
    expires_sec: int = 3600,
) -> str:
    """
    Sube el STL a Supabase Storage y devuelve una URL firmada lista para descargar.
    - data: contenido .stl en bytes
    - key:  ruta/archivo dentro del bucket, p.ej. "qr_plate/abc123.stl"
    - bucket: nombre de bucket (por defecto SUPABASE_BUCKET)
    - expires_sec: segundos de validez del token
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_KEY")

    bucket = bucket or BUCKET_DEFAULT
    object_path = f"{bucket}/{key}"

    # 1) Upload
    up_url = f"{BASE}/object/{object_path}"
    up_headers = {
        **AUTH_HEADERS,
        # STL MIME: muchos visores aceptan estas dos; application/sla es clásico
        "Content-Type": "application/sla",
        "x-upsert": "true",  # sobreescribe si ya existe
    }
    up_res = httpx.post(up_url, content=data, headers=up_headers, timeout=60.0)
    up_res.raise_for_status()

    # 2) Firmar
    sign_url = f"{BASE}/object/sign/{object_path}"
    sign_headers = {
        **AUTH_HEADERS,
        "Content-Type": "application/json",
    }
    sign_res = httpx.post(sign_url, json={"expiresIn": expires_sec}, headers=sign_headers, timeout=30.0)
    sign_res.raise_for_status()

    # Supabase devuelve {"signedURL": "/object/sign/<bucket>/<key>?token=..."}
    signed_rel = sign_res.json().get("signedURL")
    if not signed_rel:
        raise RuntimeError("Supabase no devolvió signedURL")

    # IMPORTANTE: anteponer /storage/v1
    return f"{BASE}{signed_rel}"
