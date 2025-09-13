import os
import uuid
from typing import Optional

from supabase import create_client, Client


class Storage:
    """
    Envoltorio mínimo sobre Supabase Storage que evita tipos internos inestables
    y no usa `upsert`. Se usa un nombre de archivo único para evitar colisiones.
    """

    def __init__(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_KEY")
        bucket = os.environ.get("SUPABASE_BUCKET", "forge-stl")

        if not url or not key:
            raise RuntimeError("SUPABASE_URL o SUPABASE_SERVICE_KEY no configurados")

        self._bucket = bucket
        self._client: Client = create_client(url, key)

    def _unique_path(self, filename: Optional[str] = None) -> str:
        # Siempre un nombre único para no requerir 'upsert'
        fname = filename or f"{uuid.uuid4()}.stl"
        # Opcional: asegurar extensión .stl
        if not fname.lower().endswith(".stl"):
            fname = f"{fname}.stl"
        # Puedes cambiar la carpeta lógica dentro del bucket si quieres
        return f"{fname}"

    def upload_stl_and_sign(self, data: bytes, filename: Optional[str] = None, expires_in: int = 3600) -> str:
        """
        Sube el STL con un nombre único y devuelve una URL firmada.
        """
        object_path = self._unique_path(filename)

        # Subida SIN FileOptions ni 'upsert'
        # Firma del método (cliente síncrono): upload(path: str, file: Union[bytes, IO])
        res = self._client.storage.from_(self._bucket).upload(object_path, data)

        # 'res' puede ser un dict o un objeto con 'error'
        # Normalizamos comprobación de error
        if isinstance(res, dict) and res.get("error"):
            raise RuntimeError(f"Upload failed: {res['error']}")
        if hasattr(res, "error") and getattr(res, "error"):
            raise RuntimeError(f"Upload failed: {getattr(res, 'error')}")

        # Crear URL firmada (la clave puede ser 'signed_url' o 'signedURL' según versión)
        signed = self._client.storage.from_(self._bucket).create_signed_url(object_path, expires_in)
        if not isinstance(signed, dict):
            raise RuntimeError("Unexpected response from create_signed_url")

        url = signed.get("signed_url") or signed.get("signedURL")
        if not url:
            raise RuntimeError(f"Signed URL not present in response: {signed}")

        return url
