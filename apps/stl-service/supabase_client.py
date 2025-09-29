import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
)

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL no configurada")
if not SUPABASE_KEY:
    raise RuntimeError("Falta SUPABASE_KEY o SUPABASE_SERVICE_KEY en el entorno")

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_and_get_url(fileobj, object_key: str, bucket: str, public: bool=False) -> str:
    sb = get_supabase()
    fileobj.seek(0)
    # upsert
    sb.storage.from_(bucket).upload(
        object_key,
        fileobj,
        {"content-type": "model/stl", "upsert": "true"}
    )
    if public:
        return sb.storage.from_(bucket).get_public_url(object_key)
    # firmado 1h
    return sb.storage.from_(bucket).create_signed_url(object_key, int(os.getenv("SIGNED_URL_EXPIRES", "3600")))
