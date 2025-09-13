import os
from supabase import create_client, Client
from supabase.lib.storage.types import FileOptions  # <-- ruta correcta en v2


class Storage:
    def __init__(self) -> None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        bucket = os.getenv("SUPABASE_BUCKET", "forge-stl")

        if not url or not key:
            raise RuntimeError("SUPABASE_URL o SUPABASE_SERVICE_KEY no configurados")

        self.client: Client = create_client(url, key)
        self.bucket_name = bucket

    def _bucket(self):
        return self.client.storage.from_(self.bucket_name)

    def upload_bytes(
        self,
        path: str,
        data: bytes,
        *,
        content_type: str = "application/sla",
        upsert: bool = True,
        cache_control: str = "3600",
    ) -> dict:
        """
        Sube bytes al bucket y devuelve un dict con 'path' y 'signedURL'.
        """
        file_options = FileOptions(
            upsert=upsert,
            cache_control=cache_control,
            content_type=content_type,
        )

        # En v2: upload(path, file, file_options=...)
        res = self._bucket().upload(path, data, file_options=file_options)
        # 'res' suele traer {'path': '...'} si todo fue bien

        # Firma URL (1 hora)
        signed = self._bucket().create_signed_url(path, 3600)
        # Devuelve {'signedURL': 'https://...'}

        return {"path": res.get("path", path), "signedURL": signed.get("signedURL")}
