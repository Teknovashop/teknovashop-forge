# apps/stl-service/supabase_client.py
from __future__ import annotations

import os
import time
from typing import Dict, Optional

import httpx


def _env(name: str, fallback: Optional[str] = None) -> Optional[str]:
    """Lee variables con varios alias (Vercel/Render)"""
    aliases = {
        "SUPABASE_URL": [
            "SUPABASE_URL",
            "NEXT_PUBLIC_SUPABASE_URL",
        ],
        "SUPABASE_KEY": [
            "SUPABASE_SERVICE_KEY",          # Render / Backend
            "SUPABASE_SERVICE_ROLE_KEY",     # Vercel (típico)
            "SUPABASE_SECRET_KEY",
            "SUPABASE_KEY",                  # genérico
            "NEXT_PUBLIC_SUPABASE_ANON_KEY", # si el bucket es público, también sirve
        ],
        "SUPABASE_BUCKET": [
            "SUPABASE_BUCKET",
            "NEXT_PUBLIC_SUPABASE_BUCKET",
        ],
    }
    for k in aliases.get(name, [name]):
        v = os.getenv(k)
        if v:
            return v
    return fallback


def _norm_base_url(url: str) -> str:
    # Acepta con o sin barra final y devuelve SIEMPRE “…/”
    url = (url or "").strip()
    if not url:
        return url
    return url.rstrip("/") + "/"


def _storage_base(url: str) -> str:
    # https://PROJECT.supabase.co/storage/v1/
    base = _norm_base_url(url)
    return base + "storage/v1/"


def upload_and_get_url(
    data: bytes,
    *,
    bucket: Optional[str] = None,
    folder: str = "stl",
    filename: str = "model.stl",
    create_signed_url: bool = False,
    signed_ttl_seconds: int = 60 * 60,  # 1 hora
) -> Dict[str, object]:
    """
    Sube `data` a Supabase Storage y devuelve rutas/URLs.
    No requiere SDK; usa HTTP directo para evitar problemas de dependencias.

    Retorna:
        {
          "ok": True/False,
          "path": "stl/abc123/model.stl",
          "url": "https://.../storage/v1/object/public/<bucket>/stl/...",
          "signed_url": "https://... (opcional si create_signed_url=True)",
          "error": "... (si falla)"
        }
    """
    supa_url = _env("SUPABASE_URL")
    supa_key = _env("SUPABASE_KEY")
    bucket = bucket or _env("SUPABASE_BUCKET") or "forge-stl"

    if not supa_url or not supa_key:
        return {
            "ok": False,
            "error": "Missing SUPABASE_URL / SUPABASE_KEY environment variables",
        }

    storage = _storage_base(supa_url)  # siempre termina en “/”
    # RUTA INTERNA EN EL BUCKET
    ts = int(time.time())
    # subcarpeta por fecha o timestamp para evitar colisiones
    path = f"{folder.rstrip('/')}/{ts}/{filename}"

    # Cabeceras: ¡TODO como str!
    headers = {
        "Authorization": f"Bearer {supa_key}",
        "apikey": supa_key,
        "Content-Type": "application/octet-stream",
        # Si quisieras usar header en lugar de query param, debe ser string:
        # "x-upsert": "true",
    }

    # PUT/POST: usamos POST con query params estándar
    # POST /object/<bucket>/<path>?upsert=true
    object_url = f"{storage}object/{bucket}/{path}"

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                object_url,
                params={"upsert": "true"},   # ¡string, no bool!
                headers=headers,
                content=data,
            )
        if resp.status_code not in (200, 201):
            return {
                "ok": False,
                "error": f"Upload failed: {resp.status_code} {resp.text}",
            }
    except Exception as e:
        return {"ok": False, "error": f"Upload failed: {e}"}

    # URL pública (si el bucket es público)
    public_url = f"{storage}object/public/{bucket}/{path}"

    out: Dict[str, object] = {"ok": True, "path": path, "url": public_url}

    if create_signed_url:
        try:
            # POST /object/sign/<bucket>/<path>
            sign_url = f"{storage}object/sign/{bucket}/{path}"
            payload = {"expiresIn": int(signed_ttl_seconds)}
            with httpx.Client(timeout=15) as client:
                r = client.post(sign_url, headers=headers, json=payload)
            if r.status_code == 200 and isinstance(r.json(), dict):
                signed = r.json().get("signedURL") or r.json().get("signedUrl")
                if signed:
                    out["signed_url"] = _norm_base_url(supa_url) + signed.lstrip("/")
        except Exception:
            # si falla la firma, devolvemos al menos la pública
            pass

    return out
