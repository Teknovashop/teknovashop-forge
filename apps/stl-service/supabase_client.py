# supabase_client.py
from __future__ import annotations

import os
import io
import json
from typing import Dict, Optional

# SDK oficial (opcional). Si no está, hacemos fallback a httpx
try:
    from supabase import create_client  # type: ignore
except Exception:  # pragma: no cover
    create_client = None  # type: ignore

import httpx


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name) or os.getenv(f"NEXT_PUBLIC_{name}") or default


def _norm_url(u: str) -> str:
    u = (u or "").strip()
    # quitar espacios, dobles barras, etc.
    if not u:
        return u
    if not u.endswith("/"):
        u = u + "/"
    return u


def _sb_url_and_key() -> tuple[str, Optional[str]]:
    url = _env("SUPABASE_URL", "") or ""
    key = (
        _env("SUPABASE_SERVICE_KEY")
        or _env("SUPABASE_SERVICE_ROLE_KEY")
        or _env("SUPABASE_KEY")
    )
    url = _norm_url(url)
    return url, key


def _sdk_client():
    url, key = _sb_url_and_key()
    if create_client and url and key:
        try:
            return create_client(url, key)
        except Exception:
            pass
    return None


def upload_and_get_url(
    data: bytes,
    bucket: str,
    folder: str = "stl",
    filename: str = "model.stl",
) -> Dict[str, object]:
    """
    Sube bytes STL a Supabase Storage y devuelve:
      { ok, path, url?, signed_url? , error? }

    - Usa el SDK oficial si está disponible; si no, httpx.
    - Asegura encabezados válidos (string) y content-type correcto.
    - Normaliza la URL base (añade '/' final).
    """
    try:
        if isinstance(data, io.BytesIO):
            data = data.getvalue()
        if not isinstance(data, (bytes, bytearray)):
            return {"ok": False, "error": "upload: input is not bytes"}

        # Normaliza path
        bucket = (bucket or "").strip()
        if not bucket:
            bucket = _env("SUPABASE_BUCKET", "forge-stl") or "forge-stl"

        folder = (folder or "").strip().strip("/")
        filename = (filename or "model.stl").strip()
        if not filename.lower().endswith(".stl"):
            filename += ".stl"

        path = f"{folder}/{filename}" if folder else filename
        path = path.lstrip("/")

        url, key = _sb_url_and_key()
        if not url:
            return {"ok": False, "error": "Missing SUPABASE_URL env var"}
        if not key:
            # Se puede subir con reglas públicas + anon, pero lo normal es service key
            return {"ok": False, "error": "Missing SUPABASE_SERVICE_KEY env var"}

        # ---------- PRIMERO: intenta SDK oficial ----------
        sb = _sdk_client()
        if sb is not None:
            try:
                # upload con upsert y content-type STL
                # Nota: el SDK acepta bytes directamente.
                res = sb.storage.from_(bucket).upload(
                    path=path,
                    file=data,  # type: ignore[arg-type]
                    file_options={"content-type": "model/stl", "upsert": True},
                )
                # El SDK devuelve dict con 'data' y 'error' (en versiones nuevas puede variar)
                if isinstance(res, dict) and res.get("error"):
                    return {"ok": False, "error": str(res["error"])}

                # Public URL (si el bucket es público)
                public_url = sb.storage.from_(bucket).get_public_url(path)
                # Signed URL (por si el bucket no es público)
                signed_url = None
                try:
                    signed = sb.storage.from_(bucket).create_signed_url(path, 60 * 60 * 24 * 7)
                    if isinstance(signed, dict):
                        signed_url = signed.get("signed_url") or signed.get("signedURL")
                except Exception:
                    pass

                out: Dict[str, object] = {"ok": True, "path": path}
                if public_url:
                    out["url"] = public_url
                if signed_url:
                    out["signed_url"] = signed_url
                return out
            except Exception as e:
                # Si el SDK falla, caemos al fallback httpx
                pass

        # ---------- FALLBACK: httpx ----------
        # PUT /storage/v1/object/{bucket}/{path}
        put_url = f"{url}storage/v1/object/{bucket}/{path}"
        headers = {
            "Authorization": f"Bearer {key}",
            # ¡Importante!: valores de header SIEMPRE strings
            "Content-Type": "model/stl",
            "x-upsert": "true",  # nunca booleanos aquí
        }

        with httpx.Client(timeout=30.0) as client:
            r = client.put(put_url, content=bytes(data), headers=headers)
            # Si hay reglas RLS, necesitarás la service key como aquí
            r.raise_for_status()

            # Construimos public URL (funciona si el bucket es público)
            public_url = f"{url}storage/v1/object/public/{bucket}/{path}"

            # Creamos un signed URL por si el bucket no es público
            signed_url: Optional[str] = None
            try:
                sign_endpoint = f"{url}storage/v1/object/sign/{bucket}/{path}"
                r2 = client.post(
                    sign_endpoint,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    },
                    json={"expiresIn": 60 * 60 * 24 * 7},
                )
                if r2.status_code < 400:
                    payload = r2.json()
                    # La API devuelve algo como {"signedURL": "object/sign/..."}
                    s = payload.get("signedURL") or payload.get("signedUrl")
                    if isinstance(s, str) and s:
                        signed_url = f"{url}storage/v1/{s.lstrip('/')}"
            except Exception:
                pass

        out: Dict[str, object] = {"ok": True, "path": path}
        if public_url:
            out["url"] = public_url
        if signed_url:
            out["signed_url"] = signed_url
        return out

    except httpx.HTTPStatusError as e:  # respuestas 4xx/5xx
        try:
            body = e.response.text
        except Exception:
            body = ""
        return {
            "ok": False,
            "error": f"upload http error {e.response.status_code}: {body or e}",
        }
    except Exception as e:
        return {"ok": False, "error": f"upload exception: {e}"}
