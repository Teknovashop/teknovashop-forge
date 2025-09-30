import os
from typing import Optional, BinaryIO
from supabase import create_client, Client

SUPABASE_URL: Optional[str] = os.getenv("SUPABASE_URL")
SUPABASE_KEY: Optional[str] = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
)

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL no configurada")
if not SUPABASE_KEY:
    raise RuntimeError("Falta SUPABASE_SERVICE_ROLE_KEY / SUPABASE_KEY")

_SB: Optional[Client] = None

def get_supabase() -> Client:
    global _SB
    if _SB is None:
        _SB = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _SB

def upload_and_get_url(
    fileobj: BinaryIO,
    object_key: str,
    bucket: str,
    public: bool = False,
    content_type: str = "model/stl",
) -> str:
    """
    Sube a Supabase Storage con el SDK oficial.
    - `file` como BYTES (no BytesIO) para evitar open().
    - `upsert` debe ser STRING "true" (headers no aceptan bool).
    - Devuelve URL pública o firmada (1h por defecto).
    """
    sb = get_supabase()

    if not bucket:
        raise ValueError("bucket vacío")
    if not object_key:
        raise ValueError("object_key vacío")

    try:
        fileobj.seek(0)
    except Exception:
        pass

    data = fileobj.read()
    if isinstance(data, str):
        data = data.encode("utf-8")

    # ⬅️ clave: upsert como "true" (string), y file en bytes
    sb.storage.from_(bucket).upload(
        path=object_key,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )

    if public:
        return sb.storage.from_(bucket).get_public_url(object_key)

    expires = int(os.getenv("SIGNED_URL_EXPIRES", "3600"))
    signed = sb.storage.from_(bucket).create_signed_url(object_key, expires)

    url = (
        (isinstance(signed, dict) and (signed.get("signedURL") or signed.get("signed_url") or signed.get("url")))
        or (str(signed) if signed else None)
    )
    if not url:
        raise RuntimeError(f"No pude obtener URL firmada: {signed!r}")
    return url
