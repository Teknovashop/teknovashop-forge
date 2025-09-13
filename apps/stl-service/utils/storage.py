import os
import io
import uuid
from typing import Optional

from supabase import Client, create_client
# NOTA: con supabase==2.4.0 + httpx==0.25.x no usar FileOptions.upsert (no existe en sync mixin)

class Storage:
    """
    Pequeña envoltura para subir bytes a Supabase Storage y devolver URL firmada.
    Compatible con supabase==2.4.0 (SDK v2) y httpx==0.25.x.
    """

    def __init__(self) -> None:
        # --------- IMPORTANTE: neutralizar proxies heredados de la plataforma ----------
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
            os.environ.pop(k, None)
        # --------------------------------------------------------------------------------

        url = os.environ.get("SUPABASE_URL", "").strip()
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
        key = (key or "").strip()
        if not url or not key:
            raise RuntimeError("Faltan SUPABASE_URL y/o SUPABASE_*_KEY en el entorno")

        # Crear cliente síncrono
        self._client: Client = create_client(url, key)

        # Bucket a usar (por defecto el que ya estás usando)
        self._bucket = os.environ.get("SUPABASE_BUCKET", "forge-stl")

    def upload_stl_and_sign(
        self,
        data: bytes,
        filename: Optional[str] = None,
        expires_in: int = 3600,
        prefix: str = "forge-stl",
    ) -> str:
        """
        Sube `data` al bucket y devuelve una URL firmada temporal.
        Para evitar colisiones, generamos un path único.
        """
        if not filename:
            filename = "output.stl"

        unique = uuid.uuid4().hex  # evita "Duplicate"
        path = f"{prefix}/{unique}-{filename}"

        # Subida (no hay 'upsert' en el mixin síncrono de esta versión)
        # content_type opcional: "model/stl" o "application/sla"
        self._client.storage.from_(self._bucket).upload(
            path,
            io.BytesIO(data),
            file_options={"content-type": "model/stl"},
        )

        # URL firmada
        signed = self._client.storage.from_(self._bucket).create_signed_url(path, expires_in)
        # La SDK devuelve dict con 'signedURL' o 'signed_url' según versión;
        # contemplamos ambas claves.
        url = signed.get("signedURL") or signed.get("signed_url")
        if not url:
            # fallback: si la lib cambiase, intentamos construir URL pública si el bucket lo fuera
            raise RuntimeError(f"No se pudo obtener signed URL: {signed!r}")

        return url
