import os
import uuid
from typing import Optional

from supabase import create_client, Client


class Storage:
    """
    Adaptador de Supabase Storage compatible con storage3==0.7.x (sin parámetro 'upsert').
    Sube el archivo con un nombre único y devuelve una URL firmada.
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

        self._client: Client = create_client(url, key)
        self.bucket: str = bucket

    def _bucket(self):
        return self._client.storage.from_(self.bucket)

    def upload_bytes(
        self,
        data: bytes,
        dest_path: str,
        content_type: str = "model/stl",
        make_unique: bool = True,
    ) -> str:
        """
        Sube bytes al bucket y devuelve el path final dentro del bucket.
        - En storage3 0.7.x NO existe 'upsert', así que:
          * Por defecto generamos una ruta única (uuid) => no hace falta sobrescribir.
          * Si make_unique=False, intentamos borrar la ruta y re-subir.
        """
        bucket = self._bucket()

        final_path = dest_path
        if make_unique:
            # p.ej.: "vesa-adapter/123e4567.stl"
            base, ext = (dest_path.rsplit(".", 1) + ["stl"])[:2]
            ext = ext if ext else "stl"
            final_path = f"{base.rstrip('/')}/{uuid.uuid4().hex}.{ext}"

        if not make_unique:
            # intento de "sobrescritura" manual: borrar si existiera
            try:
                bucket.remove([dest_path])
            except Exception:
                # si no existe, ignoramos
                pass

        # storage3 0.7.x: upload(path, file, file_options=None)
        # file_options admite contentType.
        file_options = {"contentType": content_type}
        bucket.upload(final_path, data, file_options=file_options)

        return final_path

    def sign_url(self, path: str, expires_in: int = 3600) -> str:
        """
        Devuelve una URL firmada temporal para un objeto del bucket.
        """
        res = self._bucket().create_signed_url(path, expires_in)
        # SDK devuelve un dict con 'signedURL' o 'signed_url' según versión;
        # contemplamos ambos por seguridad.
        return res.get("signedURL") or res.get("signed_url") or ""

    # helper principal usado por la API
    def upload_stl_and_sign(
        self, stl_bytes: bytes, filename: str, model_folder: Optional[str] = None, expires_in: int = 3600
    ) -> str:
        """
        Sube un STL y devuelve URL firmada. Crea carpeta por modelo y nombre único.
        """
        folder = (model_folder or filename.rsplit(".", 1)[0]).strip().replace("\\", "/")
        folder = folder.strip("/")  # p.ej. "vesa-adapter"
        dest_path = f"{folder}/{filename}"  # base para componer el path único

        path_in_bucket = self.upload_bytes(
            data=stl_bytes,
            dest_path=dest_path,  # se convertirá en único internamente
            content_type="model/stl",
            make_unique=True,
        )
        return self.sign_url(path_in_bucket, expires_in=expires_in)
