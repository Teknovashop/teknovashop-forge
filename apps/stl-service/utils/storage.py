import os
import uuid
from typing import Optional

# Cliente DIRECTO de Storage (evitamos gotrue/supabase auth)
from storage3 import create_client as _create_storage_client


def _make_storage_client(storage_url: str, headers: dict):
    """
    Crea el cliente de storage3 siendo compatible con diferentes versiones.
    - En versiones nuevas: create_client(url, headers, *, is_async=...)
    - En versiones antiguas: create_client(url, headers)
    """
    try:
        # Firmas nuevas (requieren keyword-only is_async)
        return _create_storage_client(storage_url, headers, is_async=False)
    except TypeError:
        # Firmas antiguas
        return _create_storage_client(storage_url, headers)


class Storage:
    """
    Adaptador de Supabase Storage usando storage3 directamente.
    - Evita gotrue y el error 'proxy'
    - Sin 'upsert': generamos rutas únicas por defecto
    """

    def __init__(self) -> None:
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = (
            os.environ.get("SUPABASE_SERVICE_KEY")
            or os.environ.get("SUPABASE_ANON_KEY")
            or ""
        ).strip()
        bucket = os.environ.get("SUPABASE_BUCKET", "").strip()

        if not url or not key:
            raise RuntimeError("Faltan SUPABASE_URL y/o SUPABASE_*_KEY en el entorno")
        if not bucket:
            raise RuntimeError("Falta SUPABASE_BUCKET en el entorno")

        # Endpoint de storage
        storage_url = f"{url.rstrip('/')}/storage/v1"

        # Cabeceras para autenticación
        headers = {
            "Authorization": f"Bearer {key}",
            "apikey": key,
        }

        # Cliente de storage3 (compat con distintas versiones)
        self._storage = _make_storage_client(storage_url, headers)
        self.bucket: str = bucket

    def _bucket(self):
        return self._storage.from_(self.bucket)

    def upload_bytes(
        self,
        data: bytes,
        dest_path: str,
        content_type: str = "model/stl",
        make_unique: bool = True,
    ) -> str:
        """
        Sube bytes al bucket y devuelve el path final dentro del bucket.
        - storage3 no tiene 'upsert' en varias versiones -> generamos ruta única.
        - Si make_unique=False, intentamos borrar el anterior y re-subir.
        """
        bucket = self._bucket()

        final_path = dest_path
        if make_unique:
            base, ext = (dest_path.rsplit(".", 1) + ["stl"])[:2]
            ext = ext if ext else "stl"
            final_path = f"{base.rstrip('/')}/{uuid.uuid4().hex}.{ext}"

        if not make_unique:
            try:
                bucket.remove([dest_path])
            except Exception:
                # Ignora si no existía
                pass

        file_options = {"contentType": content_type}
        bucket.upload(final_path, data, file_options=file_options)
        return final_path

    def sign_url(self, path: str, expires_in: int = 3600) -> str:
        res = self._bucket().create_signed_url(path, expires_in)
        return res.get("signedURL") or res.get("signed_url") or ""

    def upload_stl_and_sign(
        self,
        stl_bytes: bytes,
        filename: str,
        model_folder: Optional[str] = None,
        expires_in: int = 3600,
    ) -> str:
        folder = (model_folder or filename.rsplit(".", 1)[0]).strip().replace("\\", "/")
        folder = folder.strip("/")
        dest_path = f"{folder}/{filename}"

        path_in_bucket = self.upload_bytes(
            data=stl_bytes,
            dest_path=dest_path,
            content_type="model/stl",
            make_unique=True,
        )
        return self.sign_url(path_in_bucket, expires_in=expires_in)
