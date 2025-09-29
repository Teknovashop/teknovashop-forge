# supabase_client.py
import os
from typing import BinaryIO, Optional
from supabase import create_client, Client

# ---- Carga de entorno (prioriza SERVICE_KEY) ----
SUPABASE_URL: Optional[str] = os.environ.get("SUPABASE_URL")
SUPABASE_KEY: Optional[str] = (
    os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
)

SIGNED_URL_EXPIRES: int = int(os.getenv("SIGNED_URL_EXPIRES", "3600"))  # 1h por defecto

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL no configurada (faltan variables de entorno).")
if not SUPABASE_KEY:
    raise RuntimeError(
        "Falta clave de Supabase. Define SUPABASE_SERVICE_KEY (recomendado) o SUPABASE_KEY / SUPABASE_ANON_KEY."
    )

# ---- Singleton del cliente ----
_SB: Optional[Client] = None

def get_supabase() -> Client:
    """
    Devuelve un cliente de Supabase (reutilizable). Lanza error si las credenciales no son válidas.
    """
    global _SB
    if _SB is None:
        _SB = create_client(SUPABASE_URL, SUPABASE_KEY)
        # pequeña sonda para fallar pronto si hay credenciales/bucket mal
        # (no hace petición de red pesada)
    return _SB


# ---- Helpers de almacenamiento ----
def upload_and_get_url(
    fileobj: BinaryIO,
    object_key: str,
    bucket: str,
    public: bool = False,
    content_type: str = "model/stl",  # también válido: "application/sla"
) -> str:
    """
    Sube el fichero al bucket dado (con upsert=True) y devuelve una URL.
    - Si public=True => URL pública permanente.
    - Si public=False => URL firmada (caduca en SIGNED_URL_EXPIRES segundos).
    """

    if not bucket:
        raise ValueError("Parametro 'bucket' vacío.")
    if not object_key:
        raise ValueError("Parametro 'object_key' vacío.")

    sb = get_supabase()

    # Asegura puntero al inicio
    try:
        fileobj.seek(0)
    except Exception:
        # Si es un bytes-like sin seek, lo ignoramos
        pass

    # Subida con upsert=True (¡booleano!, no string)
    try:
        sb.storage.from_(bucket).upload(
            path=object_key,
            file=fileobj,
            file_options={"content-type": content_type, "upsert": True},
        )
    except Exception as e:
        # Mensaje más claro para depurar permisos/bucket inexistente
        raise RuntimeError(
            f"Error subiendo '{object_key}' al bucket '{bucket}': {e}"
        ) from e

    if public:
        try:
            return sb.storage.from_(bucket).get_public_url(object_key)
        except Exception as e:
            raise RuntimeError(
                f"Subida OK pero no pude obtener URL pública para '{object_key}': {e}"
            ) from e

    # URL firmada temporal
    try:
        signed = sb.storage.from_(bucket).create_signed_url(
            object_key, SIGNED_URL_EXPIRES
        )
        # En supabase-py 2.x, create_signed_url devuelve un dict con 'signedURL' o 'signed_url'
        return signed.get("signedURL") or signed.get("signed_url") or str(signed)
    except Exception as e:
        raise RuntimeError(
            f"Subida OK pero no pude generar URL firmada para '{object_key}': {e}"
        ) from e


def health_check(bucket: str) -> bool:
    """
    Comprueba mínimamente que el bucket existe y que podemos listar (requiere permisos).
    Útil para logs de arranque.
    """
    try:
        sb = get_supabase()
        # Esto no siempre está permitido según la política; si falla, no es crítico.
        _ = sb.storage.from_(bucket).list()
        return True
    except Exception:
        return False
