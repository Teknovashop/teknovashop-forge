import os
import time
from typing import Optional
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_and_get_url(fileobj, object_key: str, bucket: str, public: bool=False) -> str:
    sb = get_supabase()
    fileobj.seek(0)
    # sube sobrescribiendo
    sb.storage.from_(bucket).upload(object_key, fileobj, {"content-type": "model/stl", "upsert": "true"})
    if public:
        return sb.storage.from_(bucket).get_public_url(object_key)
    # firmado 1h (3600s)
    return sb.storage.from_(bucket).create_signed_url(object_key, int(os.getenv("SIGNED_URL_EXPIRES", "3600")))
