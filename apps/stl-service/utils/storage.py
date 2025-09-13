import io
import os
from typing import Optional

from supabase import Client, create_client
from supabase.storage.types import FileOptions


def _env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name, default)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


class Storage:
    """
    Pequeña envoltura para subir el STL a Supabase Storage y devolver
    una URL firmada temporal.
    """

    def __init__(self) -> None:
        url = _env("SUPABASE_URL")
        key = _env("SUPABASE_SERVICE_KEY")
        self.bucket = _env("SUPABASE_BUCKET")
        self.client: Client = create_client(url, key)

    def upload_stl_and_get_signed_url(
        self,
        data: bytes,
        object_path: str,
        content_type: str = "application/sla",
        expires_in_seconds: int = 3600,
        upsert: bool = True,
    ) -> str:
        """
        Sube `data` al bucket y devuelve una URL firmada temporal.
        - object_path: ruta dentro del bucket, por ejemplo 'forge-stl/abc123.stl'
        """
        # Asegura que el buffer esté al principio
        f = io.BytesIO(data)
        f.seek(0)

        # IMPORTANTE: en supabase-py v2 las opciones van dentro de FileOptions
        options = FileOptions(upsert=upsert, content_type=content_type, cache_control="3600")

        # Subida
        upload_res = self.client.storage.from_(self.bucket).upload(
            path=object_path,
            file=f,
            file_options=options,
        )

        # Si el SDK devuelve un dict, intenta leer 'error'; si es un objeto, ignora
        if isinstance(upload_res, dict) and upload_res.get("error"):
            raise RuntimeError(f"Upload error: {upload_res['error']}")

        # URL firmada
        signed = self.client.storage.from_(self.bucket).create_signed_url(
            object_path, expires_in_seconds
        )

        # El SDK puede devolver 'signedURL' o 'signed_url' según versión
        url = None
        if isinstance(signed, dict):
            url = signed.get("signedURL") or signed.get("signed_url")

        if not url:
            raise RuntimeError(f"Could not create signed URL: {signed}")

        return url
