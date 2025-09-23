# apps/stl-service/utils/storage.py
import os
import json
import uuid
import httpx

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "forge-stl")


class Storage:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_URL o SUPABASE_SERVICE_KEY no configurados")

    def upload_stl_and_sign(
        self,
        stl_bytes: bytes,
        filename: str,
        model_folder: str,
        expires_in: int = 3600,  # 1h
    ) -> str:
        # key dentro del bucket
        key = f"{model_folder}/{uuid.uuid4().hex}/{filename}"

        # Endpoints REST de Storage v2
        up_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{key}"
        sg_url = f"{SUPABASE_URL}/storage/v1/object/sign/{SUPABASE_BUCKET}/{key}"

        headers = {"Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}

        with httpx.Client(timeout=60) as c:
            # Subida binaria
            r = c.post(
                up_url,
                headers={**headers, "Content-Type": "application/octet-stream"},
                content=stl_bytes,
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"Upload fallo {r.status_code}: {r.text}")

            # Firma (JSON correcto + header correcto)
            s = c.post(
                sg_url,
                headers={**headers, "Content-Type": "application/json"},
                content=json.dumps({"expiresIn": expires_in}),
            )
            if s.status_code != 200:
                raise RuntimeError(f"Sign fallo {s.status_code}: {s.text}")

            data = s.json() or {}
            # algunas versiones devuelven "signedURL", otras "signedUrl"
            path = data.get("signedURL") or data.get("signedUrl")
            if not path:
                raise RuntimeError(f"Respuesta de sign inesperada: {data}")

            # Asegurar prefijo /storage/v1
            # Supabase devuelve típicamente "/object/sign/…"
            if path.startswith("/object/sign/"):
                path = f"/storage/v1{path}"
            elif not path.startswith("/storage/v1/object/sign/"):
                # caso defensivo
                path = f"/storage/v1/object/sign/{SUPABASE_BUCKET}/{key}{'' if '?' in path else ''}"

            # URL absoluta lista para el front
            return f"{SUPABASE_URL.rstrip('/')}{path}"
