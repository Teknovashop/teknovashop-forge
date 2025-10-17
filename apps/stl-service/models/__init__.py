# apps/stl-service/models/__init__.py
"""
Registro dinámico de modelos.

Explora los módulos Python del paquete `models/` y registra automáticamente
una función builder por módulo. Acepta estos nombres de función, por orden:
    build, make, builder, generate, generate_stl, create, main

Así evitamos importaciones rígidas tipo:
    from .cable_clip import build as cable_clip
que fallan cuando el nombre real difiere.
"""

from __future__ import annotations
import importlib
import inspect
import pkgutil
import pathlib
from typing import Any, Callable, Dict

__all__ = ["REGISTRY", "ALIASES"]

# Nombres candidatos de la función constructora dentro de cada módulo
CANDIDATE_FUNCS = (
    "build",
    "make",
    "builder",
    "generate",
    "generate_stl",
    "create",
    "main",
)

# Módulos utilitarios que NO son modelos imprimibles
EXCLUDE_MODULES = {
    "__init__",
    "_helpers",
    "_booleans",
    "_ops",
    "geom",
    "util",
    "utils_geo",
}

def _pick_builder(mod: Any) -> Callable[[Dict[str, Any]], Any] | None:
    """Devuelve la primera función candidata encontrada en el módulo."""
    for name in CANDIDATE_FUNCS:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn

    # Último recurso: toma la primera función pública que acepte al menos 1 parámetro
    for name, obj in vars(mod).items():
        if name.startswith("_"):
            continue
        if callable(obj) and inspect.isfunction(obj):
            try:
                sig = inspect.signature(obj)
                if len(sig.parameters) >= 1:
                    return obj
            except Exception:
                # Si no podemos inspeccionar la firma, saltamos
                continue
    return None


def _discover_registry() -> Dict[str, Callable[[Dict[str, Any]], Any]]:
    """Explora el paquete y construye el registro."""
    registry: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
    pkg_path = pathlib.Path(__file__).parent

    for it in pkgutil.iter_modules([str(pkg_path)]):
        name = it.name
        if name in EXCLUDE_MODULES or name.startswith("_"):
            continue

        try:
            mod = importlib.import_module(f"{__name__}.{name}")
        except Exception as e:
            # Si un módulo falla al importarse, lo omitimos pero no rompemos todo
            # (puedes revisar logs si alguno no carga).
            continue

        builder = _pick_builder(mod)
        if builder:
            registry[name] = builder

    return registry


# Registro final de modelos disponibles (clave = nombre de módulo)
REGISTRY: Dict[str, Callable[[Dict[str, Any]], Any]] = _discover_registry()

# Aliases útiles para resolver nombres que llegan desde el frontend/UX
# (guiones ↔ guiones bajos, nombres “bonitos”, etc.)
ALIASES: Dict[str, str] = {
    # Variantes con espacios/guiones
    "cable-tray": "cable_tray",
    "cable tray": "cable_tray",
    "wall-hook": "wall_hook",
    "wall hook": "wall_hook",
    "laptop-stand": "laptop_stand",
    "laptop stand": "laptop_stand",
    "headset-stand": "headset_stand",
    "headset stand": "headset_stand",
    "enclosure-ip65": "enclosure_ip65",
    "enclosure ip65": "enclosure_ip65",
    "vesa-adapter": "vesa_adapter",
    "vesa adapter": "vesa_adapter",

    # Nombres de UI ya vistos
    "camera_plate": "qr_plate",      # tu placa 1/4" vive en qr_plate.py
    "phone_dock": "phone_stand",     # dock/stand de móvil
}

# Opcional: normalización extra en tiempo de import (guiones <-> guiones bajos, minúsculas)
# La hacemos en app.py al resolver, pero si quieres puedes ampliar aquí también.
