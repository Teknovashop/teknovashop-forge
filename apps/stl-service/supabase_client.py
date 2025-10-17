# supabase_client.py
import io
import os
import time
import hashlib
from typing import Optional, Dict, Any, Tuple

# Supabase 2.x
from supabase import create_client, Client


# -------------------------------
# Utilidades
# -------------------------------
def _norm_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return u
    u = u.strip()
    if not u:
        return None
    # Asegura barra final
    if not u.endswith("/"):
        u = u + "/"
    return u

def _safe_filename(name: str) -> str:
    name = (name or "").strip().replace("\\", "/")
    name = name.replace("..", "")
    if not name.lower().endswith(".stl"):
        name = name + ".stl"
    return name

def _folder_join(folder: Optional[str], filename: str) -> str:
    folder = (folder or "").strip().strip("/")
    filename = _safe_filename(filename)
    return f"{folder}/{filename}" if folder else filename


# -------------------------------
# Cliente Supabase
# -------------------------------
def _get_client() -> Tuple[Client, str, str]:
    """
    Crea cliente de Supabase y devuelve (client, base_url, storage_url)
    """
    raw_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or ""
    url = _norm_url(raw_url)
    key = (
        os.getenv("SUPABASE_SERVICE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        or ""
    )

    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_*_KEY environment variables")

    # Log amable (sin claves)
    print(f"[forge] Supabase URL: {url} (from {('SUPABASE_URL' if os.getenv('SUPABASE_URL') else 'NEXT_PUBLIC_SUPABASE_URL')})")

    client: Client = create_client(url, key)

    # Construye storage base (la librería ya sabe, pero lo dejamos claro para logs)
    storage_url = url + "storage/v1/"
    return client, url, storage_url


def _is_bucket_public(client: Client, bucket: str) -> bool:
    """
    Intenta inferir si un bucket es público. No hay flag directo en supabase-py,
    así que hacemos best-effort: si get_public_url() devuelve algo útil, lo usamos
    igualmente; en buckets privados seguirá devolviendo URL pero 403 al leer.
    En cualquier caso, generamos también signed_url si hace falta.
    """
    try:
        # Si esto no explota, asumimos que la feature de URL pública existe.
        _ = client.storage.from_(bucket)
        return False  # por seguridad asumimos privado; ya decidimos luego
    except Exception:
        return False


# -------------------------------
# API principal
# -------------------------------
def upload_and_get_url(
    data: bytes,
    bucket: Optional[str] = None,
    folder: Optional[str] = "stl",
    filename: Optional[str] = None,
    sign_expires_seconds: int = 24 * 3600,
) -> Dict[str, Any]:
    """
    Sube 'data' (bytes STL) a Supabase Storage y devuelve dict:
      { ok: bool, path: 'stl/xyz.stl', url?: str, signed_url?: str, error?: str }

    - Si el bucket es público -> 'url'
    - Si es privado -> 'signed_url'
    """
    try:
        if not isinstance(data, (bytes, bytearray)):
            # Permite BytesIO
            if isinstance(data, io.BytesIO):
                data = data.getvalue()
            else:
                raise TypeError(f"upload_and_get_url expects bytes, got {type(data).__name__}")

        client, base_url, storage_url = _get_client()

        bucket_name = (
            bucket
            or os.getenv("SUPABASE_BUCKET")
            or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET")
            or "forge-stl"
        ).strip()

        # Nombre por defecto estable si no se pasa
        if not filename:
            digest = hashlib.sha1(data).hexdigest()[:10]
            filename = f"model_{int(time.time())}_{digest}.stl"

        path = _folder_join(folder, filename)

        print(f"[forge] Uploading to bucket='{bucket_name}' path='{path}' (contentType=model/stl)")

        storage = client.storage.from_(bucket_name)

        # Subida (upsert para no fallar si el nombre se repite)
        storage.upload(
            path=path,
            file=data,
            file_options={"contentType": "model/stl", "upsert": True, "cacheControl": "31536000"},
        )

        # Intento de URL pública
        public = _is_bucket_public(client, bucket_name)
        public_url = None
        try:
            public_url = storage.get_public_url(path)
        except Exception:
            public_url = None

        # Intento de URL firmada (si el bucket es privado, será la válida)
        signed_url = None
        try:
            # create_signed_url retorna dict con 'signedURL'
            s = storage.create_signed_url(path, sign_expires_seconds)
            if isinstance(s, dict):
                signed_url = s.get("signedURL") or s.get("signed_url")
        except Exception:
            signed_url = None

        payload: Dict[str, Any] = {"ok": True, "path": path}

        # Selección de URL para el frontend:
        if signed_url:
            payload["signed_url"] = signed_url
            print(f"[forge] Signed URL created ({sign_expires_seconds}s)")
        if public_url:
            payload["url"] = public_url
            print("[forge] Public URL available")

        # Si no hay ninguna URL utilizable, devolvemos igualmente ok para que
        # el frontend pueda al menos descargar por API si lo necesitara.
        if not signed_url and not public_url:
            print("[forge][warn] No public/signed URL available. Check bucket policies.")

        return payload

    except Exception as e:
        err = str(e)
        print(f"[forge][upload:error] {err}")
        return {"ok": False, "error": err}
