# /app.py
import io
import os
import tempfile
from typing import Any, Dict, Iterable, Optional, Tuple, Union, Callable, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from models import REGISTRY, ALIASES
from supabase_client import upload_and_get_url


# ---------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------
def _norm_model_key(k: str) -> str:
    return (k or "").strip().lower().replace("-", "_").replace(" ", "_")

def _first(d: Dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None

def _bytes_from_filelike(obj: Any) -> Optional[bytes]:
    try:
        read = getattr(obj, "read", None)
        if callable(read):
            data = read()
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
            if isinstance(data, str):
                return data.encode("utf-8")
    except Exception:
        pass
    return None

def _export_via_tempfile(callable_with_path, suffix: str = ".stl") -> bytes:
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        callable_with_path(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ---------------------------------------------------------------------
# Fallback: placeholder si un builder devuelve lista vacía
# ---------------------------------------------------------------------
def _placeholder_box_mm(length_mm: float, width_mm: float, height_mm: float) -> bytes:
    """
    Genera una cajita STL con las dimensiones indicadas en mm
    para evitar 500 cuando un builder devuelve [].
    """
    try:
        import trimesh  # type: ignore
        from trimesh.creation import box  # type: ignore

        # Trimesh usa unidades arbitrarias, mantenemos mm.
        mesh = box(extents=[max(length_mm, 1e-3), max(width_mm, 1e-3), max(height_mm, 1e-3)])
        data = mesh.export(file_type="stl")
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        if isinstance(data, str):
            return data.encode("utf-8")
    except Exception as e:
        # Último backup: STL ASCII mínimo de un tetra (poco probable llegar aquí)
        ascii_stl = f"""solid placeholder
endsolid placeholder
"""
        return ascii_stl.encode("utf-8")
    # debería haber retornado antes
    raise HTTPException(status_code=500, detail="Failed to build placeholder STL")


# ---------------------------------------------------------------------
# Normalizador de salidas -> STL bytes
# ---------------------------------------------------------------------
def _as_stl_bytes(result: Any) -> Tuple[bytes, Optional[str]]:
    """
    Normaliza la salida del builder a (stl_bytes, filename|None).

    Acepta:
      - bytes / bytearray / io.BytesIO / file-like .read()
      - str (ruta o STL ASCII)
      - dict con {bytes|buffer|stl|path|file|filepath|filename|name} o con objeto en {mesh|object|model|geom}
      - tuple/list:
          * (payload, "nombre.stl")
          * lista de piezas -> fusiona en una escena (si trimesh está disponible);
            si no, toma el primer STL convertible
      - objetos con .export(...), .to_stl(), .save(path)
      - objetos trimesh (Trimesh/Scene) y cadquery (Workplane)
    """
    filename: Optional[str] = None

    # --- LISTAS/TUPLAS ---
    if isinstance(result, (list, tuple)):
        items = list(result)
        if os.getenv("DEBUG_FORGE"):
            print(f"[forge] normalize:list/tuple len= {len(items)}")

        if len(items) == 0:
            # lista vacía: no hay nada que convertir
            raise HTTPException(
                status_code=500,
                detail="Builder returned an empty list (no geometry)."
            )

        # Caso (payload, "nombre.stl")
        if len(items) == 2 and isinstance(items[1], str) and not isinstance(items[0], str):
            payload = items[0]
            filename = items[1] if items[1].lower().endswith(".stl") else items[1]
            data, fn = _as_stl_bytes(payload)
            return data, (filename or fn)

        # Si hay strings *.stl incluidos, úsalo como nombre sugerido
        for it in items:
            if isinstance(it, str) and it.lower().endswith(".stl"):
                filename = it
                break

        # Pre-procesa: si hay callables, intenta invocarlos sin args
        pre_items: List[Any] = []
        for it in items:
            if callable(it):
                try:
                    it = it()
                except Exception:
                    pass
            pre_items.append(it)

        # Intento 1: convertir TODOS a bytes STL
        stl_blobs: List[bytes] = []
        first_name: Optional[str] = filename
        for it in pre_items:
            try:
                data, fn = _as_stl_bytes(it)
                if isinstance(data, (bytes, bytearray)) and data:
                    stl_blobs.append(bytes(data))
                    if not first_name and fn:
                        first_name = fn
            except Exception:
                continue

        if len(stl_blobs) == 1:
            return stl_blobs[0], first_name

        if len(stl_blobs) > 1:
            # Intento 2: fusionar con trimesh
            try:
                import trimesh  # type: ignore
                scene = trimesh.Scene()
                for blob in stl_blobs:
                    mesh = trimesh.load(io.BytesIO(blob), file_type="stl")
                    if isinstance(mesh, trimesh.Scene):
                        for g in mesh.geometry.values():
                            scene.add_geometry(g)
                    elif isinstance(mesh, trimesh.Trimesh):
                        scene.add_geometry(mesh)
                exported = scene.export(file_type="stl")
                if os.getenv("DEBUG_FORGE"):
                    print(f"[forge] merge: trimesh ok (n piezas={len(stl_blobs)})")
                if isinstance(exported, (bytes, bytearray)):
                    return bytes(exported), first_name
                if isinstance(exported, str):
                    return exported.encode("utf-8"), (first_name or "model.stl")
            except Exception as e:
                if os.getenv("DEBUG_FORGE"):
                    print(f"[forge] merge: trimesh failed → {e}. Fallback a primera pieza")
                return stl_blobs[0], first_name

        # Intento 3: si solo hay un elemento no-str, probarlo
        non_str = [x for x in pre_items if not isinstance(x, str)]
        if len(non_str) == 1:
            data, fn = _as_stl_bytes(non_str[0])
            return data, (filename or fn)

        # Nada convertible
        raise HTTPException(
            status_code=500,
            detail="Builder must return bytes or BytesIO (got list with no convertible items)"
        )

    # --- DICT ---
    if isinstance(result, dict):
        filename = _first(result, ("filename", "name")) or filename
        payload = _first(result, ("bytes", "buffer", "stl"))
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload), filename
        if isinstance(payload, io.BytesIO):
            return payload.getvalue(), filename

        # ruta
        path = _first(result, ("path", "file", "filepath"))
        if isinstance(path, str) and path:
            with open(path, "rb") as f:
                return f.read(), filename or os.path.basename(path)

        # Objeto embebido exportable
        result = _first(result, ("mesh", "object", "model", "geom")) or result

    # --- BYTES/BYTESIO ---
    if isinstance(result, (bytes, bytearray)):
        return bytes(result), filename
    if isinstance(result, io.BytesIO):
        return result.getvalue(), filename

    # --- FILE-LIKE .read() ---
    fb = _bytes_from_filelike(result)
    if fb is not None:
        return fb, filename

    # --- STR (ruta o STL ASCII) ---
    if isinstance(result, str) and result:
        if os.path.isfile(result):
            with open(result, "rb") as f:
                return f.read(), filename or os.path.basename(result)
        return result.encode("utf-8"), filename or "model.stl"

    # --- __bytes__() ---
    try:
        to_bytes = getattr(result, "__bytes__", None)
        if callable(to_bytes):
            return bytes(result), filename
    except Exception:
        pass

    # --- export(...), varias variantes ---
    export = getattr(result, "export", None)
    if callable(export):
        bio = io.BytesIO()
        try:
            export(fileobj=bio, file_type="stl")
            return bio.getvalue(), filename
        except Exception:
            try:
                bio = io.BytesIO()
                export(bio)
                return bio.getvalue(), filename
            except Exception:
                try:
                    data = _export_via_tempfile(lambda p: export(p), ".stl")
                    return data, filename
                except Exception:
                    pass

    # --- to_stl() ---
    to_stl = getattr(result, "to_stl", None)
    if callable(to_stl):
        out = to_stl()
        if isinstance(out, (bytes, bytearray)):
            return bytes(out), filename
        if isinstance(out, io.BytesIO):
            return out.getvalue(), filename
        if isinstance(out, str):
            if os.path.isfile(out):
                with open(out, "rb") as f:
                    return f.read(), filename or os.path.basename(out)
            return out.encode("utf-8"), filename or "model.stl"

    # --- trimesh directo ---
    try:
        import trimesh  # type: ignore
        if isinstance(result, (trimesh.Trimesh, trimesh.Scene)):
            data = result.export(file_type="stl")
            if isinstance(data, (bytes, bytearray)):
                return bytes(data), filename
            if isinstance(data, str):
                return data.encode("utf-8"), filename or "model.stl"
    except Exception:
        pass

    # --- cadquery ---
    try:
        import cadquery as cq  # type: ignore
        from cadquery import exporters  # type: ignore

        if isinstance(result, cq.Workplane) or hasattr(result, "toStlString"):
            tss = getattr(result, "toStlString", None)
            if callable(tss):
                s = tss()
                if isinstance(s, str):
                    return s.encode("utf-8"), filename or "model.stl"
            try:
                data = _export_via_tempfile(lambda p: exporters.export(result, p))
                return data, filename
            except Exception:
                pass
    except Exception:
        pass

    # --- save(path) ---
    save = getattr(result, "save", None)
    if callable(save):
        try:
            data = _export_via_tempfile(lambda p: save(p))
            return data, filename
        except Exception:
            pass

    # Sin conversión posible
    typename = type(result).__name__
    methods = [m for m in dir(result) if not m.startswith("_")]
    preview = ", ".join(methods[:20])
    raise HTTPException(
        status_code=500,
        detail=f"Builder must return bytes or BytesIO (got {typename}; methods: {preview} …)"
    )


# ---------------------------------------------------------------------
# FastAPI + CORS
# ---------------------------------------------------------------------
app = FastAPI()

allowed_origins = [
    os.getenv("FRONTEND_ORIGIN")
    or os.getenv("NEXT_PUBLIC_SITE_URL")
    or "*"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------- Esquemas ---------
class Hole(BaseModel):
    x_mm: float
    y_mm: float
    d_mm: float

class ArrayOp(BaseModel):
    count: int = 1
    dx: float = 0.0
    dy: float = 0.0

class TextOp(BaseModel):
    text: str
    size: float = 10.0
    x: float = 0.0
    y: float = 0.0
    depth: float | None = None

class Params(BaseModel):
    length_mm: float = Field(gt=0)
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    thickness_mm: float | None = Field(default=None, gt=0)
    fillet_mm: float | None = Field(default=None, ge=0)
    holes: list[Hole] = Field(default_factory=list)
    arrayOps: list[ArrayOp] = Field(default_factory=list)
    textOps: list[TextOp] = Field(default_factory=list)

class GenerateBody(BaseModel):
    model: str
    params: Params


# --------- Salud ---------
@app.get("/health")
async def health(request: Request):
    env_snapshot = {
        "SUPABASE_URL_set": bool(os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")),
        "SUPABASE_BUCKET": os.getenv("SUPABASE_BUCKET") or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET") or "forge-stl",
        "FRONTEND_ORIGIN": os.getenv("FRONTEND_ORIGIN"),
        "NEXT_PUBLIC_SITE_URL": os.getenv("NEXT_PUBLIC_SITE_URL"),
    }
    return {
        "ok": True,
        "available_models": sorted(REGISTRY.keys()),
        "aliases": ALIASES if isinstance(ALIASES, dict) else {},
        "env": env_snapshot,
        "cors_allowed_origins": allowed_origins,
    }


# --------- Generate ---------
@app.post("/generate")
async def generate(body: GenerateBody, request: Request):
    raw_key = body.model or ""
    model_key = _norm_model_key(raw_key)

    entry: Optional[Union[Callable[..., Any], Dict[str, Any]]] = REGISTRY.get(model_key)
    if entry is None and isinstance(ALIASES, dict):
        alias = ALIASES.get(model_key) or ALIASES.get(raw_key)
        if isinstance(alias, str):
            entry = REGISTRY.get(_norm_model_key(alias))

    if entry is None:
        available = sorted(REGISTRY.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Model '{raw_key}' not found. Available: {', '.join(available)}"
        )

    make_fn: Optional[Callable[..., Any]] = None
    if callable(entry):
        make_fn = entry
    elif isinstance(entry, dict):
        make_fn = entry.get("make") or entry.get("builder") or None

    if not callable(make_fn):
        raise HTTPException(status_code=500, detail="Invalid model registry entry (no callable).")

    # Parámetros planos
    p: Dict[str, Any] = {
        "length_mm": float(body.params.length_mm),
        "width_mm": float(body.params.width_mm),
        "height_mm": float(body.params.height_mm),
        "thickness_mm": float(body.params.thickness_mm) if body.params.thickness_mm else None,
        "fillet_mm": float(body.params.fillet_mm) if body.params.fillet_mm else None,
        "holes": [h.model_dump() for h in body.params.holes],
        "arrayOps": [a.model_dump() for a in body.params.arrayOps],
        "textOps": [t.model_dump() for t in body.params.textOps],
    }

    if os.getenv("DEBUG_FORGE"):
        print(f"[forge] incoming model: {raw_key} -> {model_key}")
        print(f"[forge] params: {p}")

    # Construcción del modelo
    try:
        result_any = make_fn(p)
        if os.getenv("DEBUG_FORGE"):
            print(f"[forge] builder returned: {type(result_any).__name__}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model build error: {e}")

    # Fallback inmediato si el builder ha devuelto lista vacía
    if isinstance(result_any, (list, tuple)) and len(result_any) == 0:
        if os.getenv("DEBUG_FORGE"):
            print("[forge] builder devolvió lista vacía → usando placeholder box")
        stl_bytes = _placeholder_box_mm(
            p["length_mm"], p["width_mm"], p["height_mm"]
        )
        filename = f"{model_key}.stl"
    else:
        # Normalización a STL bytes
        stl_bytes, suggested_name = _as_stl_bytes(result_any)
        filename = suggested_name or f"{model_key}.stl"

    # Subida a Supabase
    up = upload_and_get_url(
        stl_bytes,
        bucket=os.getenv("SUPABASE_BUCKET") or os.getenv("NEXT_PUBLIC_SUPABASE_BUCKET") or "forge-stl",
        folder="stl",
        filename=filename,
    )

    if not up.get("ok"):
        raise HTTPException(status_code=500, detail=up.get("error") or "Upload failed")

    resp: Dict[str, Any] = {"ok": True, "path": up.get("path"), "filename": filename}
    if up.get("url"):
        resp["stl_url"] = up["url"]
    if up.get("signed_url"):
        resp["signed_url"] = up["signed_url"]
    return resp
