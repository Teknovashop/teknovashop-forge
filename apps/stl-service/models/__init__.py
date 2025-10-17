# apps/stl-service/models/__init__.py
# Registro central de *model builders* usando SOLO los módulos que ya tienes.

# Importa los builders (cada módulo debe exponer una función build(params))
from .cable_clip import build as cable_clip
from .cable_tray import build as cable_tray
from .enclosure_ip65 import build as enclosure_ip65
from .geom import build as geom          # utilitario; lo dejamos disponible si lo usas
from .headset_stand import build as headset_stand
from .laptop_stand import build as laptop_stand
from .phone_stand import build as phone_stand
from .qr_plate import build as qr_plate
from .router_mount import build as router_mount
from .util import build as util          # utilitario; por si algún modelo lo llama
from .utils_geo import build as utils_geo  # utilitario; idem
from .vesa import build as vesa
from .vesa_adapter import build as vesa_adapter
from .vesa_shelf import build as vesa_shelf
from .wall_hook import build as wall_hook

# Registro base con nombres canónicos (guion_bajo)
_REGISTRY = {
    "cable_clip": cable_clip,
    "cable_tray": cable_tray,
    "enclosure_ip65": enclosure_ip65,
    "geom": geom,
    "headset_stand": headset_stand,
    "laptop_stand": laptop_stand,
    "phone_stand": phone_stand,
    "qr_plate": qr_plate,
    "router_mount": router_mount,
    "util": util,
    "utils_geo": utils_geo,
    "vesa": vesa,
    "vesa_adapter": vesa_adapter,
    "vesa_shelf": vesa_shelf,
    "wall_hook": wall_hook,
}

# Exponemos REGISTRY aceptando también alias con guion (-)
REGISTRY = dict(_REGISTRY)
for key, val in list(_REGISTRY.items()):
    hyphen = key.replace("_", "-")
    if hyphen not in REGISTRY:
        REGISTRY[hyphen] = val

__all__ = ["REGISTRY"]
