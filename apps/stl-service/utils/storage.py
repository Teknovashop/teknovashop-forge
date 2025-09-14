import os
import uuid
from typing import Optional

# Cliente DIRECTO de Storage (evita gotrue/supabase auth)
from storage3 import create_client as create_storage_client


class Storage:
    """
    Adaptador de Supabase Storage usando storage3 directamente.
    - Evita gotrue y el error 'proxy'
    - Compatible con storage3==0.7.x (no existe 'upsert')
    - Sube con ruta única y devuelve URL firmada
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

        # Cliente de storage3
        self._storage = create_storage_client(storage_url, headers)
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
        - En storage3 0.7.x NO existe 'upsert'.
        - Por defecto generamos una ruta única => sin sobrescribir.
        - Si make_unique=False, intentamos borrar y re-subir.
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
                pass

        file_options = {"contentType": content_type}
        bucket.upload(final_path, data, file_options=file_options)
        return final_path

    def sign_url(self, path: str, expires_in: int = 3600) -> str:
        res = self._bucket().create_signed_url(path, expires_in)
        return res.get("signedURL") or res.get("signed_url") or ""

    def upload_stl_and_sign(
        self, stl_bytes: bytes, filename: str, model_folder: Optional[str] = None, expires_in: int = 3600
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
