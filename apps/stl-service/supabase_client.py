# supabase_client.py
import os
from typing import BinaryIO, Optional
from supabase import create_client, Client

SUPABASE_URL: Optional[str] = os.environ.get("SUPABASE_URL")
SUPABASE_KEY: Optional[str] = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")  # <- prioriza Service Role
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
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
    sb = get_supabase()
    try:
        fileobj.seek(0)
    except Exception:
        pass

    sb.storage.from_(bucket).upload(
        path=object_key,
        file=fileobj,
        file_options={"content-type": content_type, "upsert": True},
    )
    if public:
        return sb.storage.from_(bucket).get_public_url(object_key)
    signed = sb.storage.from_(bucket).create_signed_url(
        object_key, int(os.getenv("SIGNED_URL_EXPIRES", "3600"))
    )
    return signed.get("signedURL") or signed.get("signed_url") or str(signed)
