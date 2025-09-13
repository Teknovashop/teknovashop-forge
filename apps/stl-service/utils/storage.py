from supabase import create_client
import os

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(url, key)

BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")


def upload_file(file_path: str, dest_name: str) -> str:
    with open(file_path, "rb") as f:
        res = supabase.storage.from_(BUCKET).upload(dest_name, f)
        if res is None or "error" in str(res).lower():
            raise Exception(f"Upload failed: {res}")

        # obtener URL pública firmada
        signed = supabase.storage.from_(BUCKET).create_signed_url(dest_name, 60 * 60)
        return signed["signedURL"]
