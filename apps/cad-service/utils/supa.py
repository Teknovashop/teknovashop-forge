import os, time, hashlib
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BUCKET_STL = os.environ.get("SUPABASE_BUCKET_STL", "forge-stl")
BUCKET_DXF = os.environ.get("SUPABASE_BUCKET_DXF", "forge-dxf")
BUCKET_PNG = os.environ.get("SUPABASE_BUCKET_PNG", "forge-previews")

def supa() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def put_bytes(bucket: str, path: str, data: bytes, content_type: str):
    cl = supa().storage.from_(bucket)
    cl.upload(path, data, {"content-type": content_type, "upsert": True})
    return cl.get_public_url(path)

def hash_key(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode())
    return h.hexdigest()[:16]
