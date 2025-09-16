# apps/stl-service/utils/storage.py
import os, json, httpx, uuid

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")

class Storage:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_URL o SUPABASE_SERVICE_KEY no configurados")

    def upload_stl_and_sign(self, stl_bytes: bytes, filename: str, model_folder: str, expires_in: int = 300) -> str:
        key = f"{model_folder}/{uuid.uuid4().hex}/{filename}"
        up_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{key}"
        sg_url = f"{SUPABASE_URL}/storage/v1/object/sign/{SUPABASE_BUCKET}/{key}"
        headers = {"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}

        with httpx.Client(timeout=60) as c:
            r = c.post(up_url, headers={**headers, "Content-Type":"application/octet-stream"}, content=stl_bytes)
            if r.status_code not in (200,201): raise RuntimeError(f"Upload fallo {r.status_code}: {r.text}")
            s = c.post(sg_url, headers={**headers, "Content-Type":"application/json"}, content=json.dumps({"expiresIn": expires_in}))
            if s.status_code != 200: raise RuntimeError(f"Sign fallo {s.status_code}: {s.text}")
            signedURL = s.json().get("signedURL")
            return f"{SUPABASE_URL}{signedURL}"
