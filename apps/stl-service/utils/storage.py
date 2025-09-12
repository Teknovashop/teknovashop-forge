import os
from supabase import create_client, Client

# Inicializa el cliente Supabase
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

def upload_to_supabase(local_path: str, bucket: str, key: str) -> str:
    """
    Sube un archivo a Supabase Storage y devuelve una URL firmada (1h de validez).
    """
    with open(local_path, "rb") as f:
        data = f.read()

    # upload() en supabase-py v2 requiere file_options
    res = supabase.storage.from_(bucket).upload(
        path=key,
        file=data,
        file_options={
            "contentType": "model/stl",  # MIME correcto para STL
            "upsert": True               # Sobrescribir si existe
        }
    )

    # Manejo de error explícito
    if isinstance(res, dict) and res.get("error"):
        raise RuntimeError(res["error"]["message"])

    # Generar URL firmada (1 hora de validez)
    signed = supabase.storage.from_(bucket).create_signed_url(
        path=key,
        expires_in=3600
    )

    return signed.get("signedURL") or signed.get("signed_url")
