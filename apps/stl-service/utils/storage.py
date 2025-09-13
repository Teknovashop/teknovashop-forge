import os
import uuid
from typing import Optional

from supabase import create_client, Client


class Storage:
    """
    Pequeño wrapper de Supabase Storage para subir STL y firmar URL.
    - Acepta ANON o SERVICE ROLE como auth.
    - Acepta tanto SUPABASE_SERVICE_ROLE_KEY como SUPABASE_SERVICE_KEY.
    - Genera nombre único para evitar 'Duplicate'.
    - Desactiva proxies para evitar el error 'proxy' en httpx.
    """

    def __init__(self) -> None:
        # Apaga proxies que rompen httpx/gotrue en algunos entornos
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            os.environ.pop(k, None)

        url = (os.environ.get("SUPABASE_URL") or "").strip()
        if not url:
            raise RuntimeError("Falta SUPABASE_URL en el entorno")

        # Acepta varios nombres de clave
        key = (
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or os.environ.get("SUPABASE_SERVICE_KEY")
            or os.environ.get("SUPABASE_ANON_KEY")
            or ""
        ).strip()
        if not key:
            raise RuntimeError(
                "Falta una clave de Supabase: define SUPABASE_SERVICE_ROLE_KEY "
                "(o SUPABASE_SERVICE_KEY / SUPABASE_ANON_KEY) en el entorno"
            )

        self.bucket = (os.environ.get("SUPABASE_BUCKET") or "forge-stl").strip()

        # Cliente sync (el que ya estás usando)
        self._client: Client = create_client(url, key)

    def upload_stl_and_sign(
        self,
        data: bytes,
        filename: str = "forge-output.stl",
        folder: str = "forge-stl",
        expires_in: int = 3600,
    ) -> str:
        """
        Sube bytes a storage y devuelve URL firmada.
        Para evitar 'Duplicate', añadimos un sufijo único al nombre.
        """
        # Asegura extensión y path único
        base, ext = (filename.rsplit(".", 1) + ["stl"])[0:2]
        unique = uuid.uuid4().hex[:12]
        path = f"{folder}/{base}-{unique}.{ext}"

        # Subida (sin 'upsert' para compatibilidad de SDK)
        file_options = {"contentType": "model/stl"}
        res = self._client.storage.from_(self.bucket).upload(path, data, file_options)  # type: ignore

        if isinstance(res, dict) and res.get("error"):
            # SDK v2 devuelve {'statusCode': 400, 'error': 'Duplicate', ...} en algunos casos
            raise RuntimeError(str(res))

        # URL firmada
        signed = self._client.storage.from_(self.bucket).create_signed_url(path, expires_in)  # type: ignore
        if isinstance(signed, dict) and signed.get("error"):
            raise RuntimeError(str(signed))

        # El SDK suele devolver dict con 'signedURL' o 'signed_url'
        url = signed.get("signedURL") or signed.get("signed_url") or signed.get("publicURL") or signed  # type: ignore
        if isinstance(url, str):
            return url
        # Fallback por si el SDK cambia estructura
        raise RuntimeError(f"No se pudo obtener signed URL: {signed}")
