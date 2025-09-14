import os
import time
from typing import Optional

from supabase import create_client, Client


class Storage:
    """
    Subida a Supabase Storage + URL firmada.
    Requiere en el entorno:
      - SUPABASE_URL
      - SUPABASE_SERVICE_KEY   (o ANON_KEY si tu bucket es público)
      - SUPABASE_BUCKET        (p.ej. forge-stl)
      - WATERMARK_TEXT         (opcional, texto para filename)
    """

    def __init__(self) -> None:
        url = os.environ.get("SUPABASE_URL")
        key = (
            os.environ.get("SUPABASE_SERVICE_KEY")
            or os.environ.get("SUPABASE_ANON_KEY")
        )

        if not url or not key:
            raise RuntimeError("Faltan SUPABASE_URL y/o SUPABASE_*_KEY en el entorno")

        self._client: Client = create_client(url, key)
        self._bucket = os.environ.get("SUPABASE_BUCKET", "forge-stl")
        self._watermark = os.environ.get("WATERMARK_TEXT", "Teknovashop")

    def upload_stl_and_sign(self, stl_bytes: bytes, filename: str, expires_in: int = 3600) -> str:
        # ruta única
        ts = int(time.time())
        safe_name = filename.replace(" ", "_").lower()
        path = f"forge-stl/{self._watermark}-{ts}-{safe_name}"

        # sube
        resp = self._client.storage.from_(self._bucket).upload(
            path=path,
            file=stl_bytes,
            file_options={"contentType": "model/stl"},
            upsert=False,
        )
        if hasattr(resp, "error") and resp.error:
            raise RuntimeError(f"Supabase upload error: {resp.error}")

        # URL firmada
        signed = self._client.storage.from_(self._bucket).create_signed_url(path, expires_in)
        if not signed or "signedURL" not in signed:
            raise RuntimeError("No se pudo generar URL firmada")
        return signed["signedURL"]
