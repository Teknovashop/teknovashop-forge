import os
from supabase import create_client, Client

supabase: Client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

def upload_to_supabase(local_path: str, bucket: str, key: str) -> str:
    with open(local_path, 'rb') as f:
        supabase.storage.from_(bucket).upload(file=f, path=key, file_options={"content-type":"model/stl"}, upsert=True)
    signed = supabase.storage.from_(bucket).create_signed_url(path=key, expires_in=3600)
    return signed['signedURL']
