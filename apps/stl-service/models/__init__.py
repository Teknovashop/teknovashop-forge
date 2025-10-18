"""
Registro de builders y tabla de alias.
- REGISTRY: builders indexados por slug snake_case
- ALIASES:  cualquier variante (kebab/snake/etiquetas de la UI) -> slug snake_case
Además: loggeamos por qué falla cada import para no “tragarnos” errores.
"""

from typing import Callable, Dict
import traceback
import sys

REGISTRY: Dict[str, Callable] = {}
ALIASES: Dict[str, str] = {}

def _alias(s: str) -> str:
    return (s or "").strip().lower()

def _reg(slug_snake: str, fn: Callable, *more_aliases: str):
    """Registra el builder y todas sus variantes como alias."""
    slug_snake = _alias(slug_snake).replace("-", "_")
    REGISTRY[slug_snake] = fn

    kebab = slug_snake.replace("_", "-")
    ALIASES[_alias(slug_snake)] = slug_snake
    ALIASES[_alias(kebab)] = slug_snake

    for a in more_aliases:
        a = _alias(a)
        if not a:
            continue
        ALIASES[a] = slug_snake
        ALIASES[a.replace("_", "-")] = slug_snake
        ALIASES[a.replace("-", "_")] = slug_snake

def _safe_import(name: str, builder_name: str, slug_snake: str, *aliases: str):
    """
    Importa models.<name> y registra su .build como <slug_snake>.
    Si falla, imprime el error a stderr para que se vea en Render.
    """
    try:
        mod = __import__(f"models.{name}", fromlist=["build"])
        fn = getattr(mod, builder_name, None) or getattr(mod, "build", None)
        if not callable(fn):
            raise RuntimeError(f"models.{name} no expone '{builder_name}' ni 'build'")
        _reg(slug_snake, fn, *aliases)
    except Exception:
        print(f"[FORGE][models] ERROR importando models.{name} -> {slug_snake}", file=sys.stderr)
        traceback.print_exc()

# -------------------------
# REGISTROS (mantener en sync con tu UI)
# -------------------------

_safe_import("vesa_adapter",   "build", "vesa_adapter",   "vesa-adapter", "adaptador-vesa-75-100-a-100-200")
_safe_import("router_mount",   "build", "router_mount",   "router-mount", "soporte-de-router")
_safe_import("cable_tray",     "build", "cable_tray",     "cable-tray", "bandeja-de-cables")
_safe_import("tablet_stand",   "build", "tablet_stand",   "tablet-stand", "soporte-de-tablet")
_safe_import("monitor_stand",  "build", "monitor_stand",  "monitor-stand", "elevador-de-monitor")
_safe_import("ssd_holder",     "build", "ssd_holder",     "ssd-holder", "caddy-ssd-2-5-a-3-5")
_safe_import("raspi_case",     "build", "raspi_case",     "raspi-case", "caja-raspberry-pi")
_safe_import("go_pro_mount",   "build", "go_pro_mount",   "go-pro-mount", "gopro-mount", "soporte-gopro")
_safe_import("mic_arm_clip",   "build", "mic_arm_clip",   "mic-arm-clip", "clip-brazo-mic")
_safe_import("camera_plate",   "build", "camera_plate",   "camera-plate", "placa-para-camara")
_safe_import("wall_hook",      "build", "wall_hook",      "wall-hook", "gancho-pared")
_safe_import("wall_bracket",   "build", "wall_bracket",   "wall-bracket", "soporte-pared")
_safe_import("phone_dock",     "build", "phone_dock",     "phone-dock", "dock-para-movil-usb-c")
_safe_import("hub_holder",     "build", "hub_holder",     "hub-holder")

# Nota: si en tu repo hay más modelos, añádelos aquí con _safe_import.
# Este archivo NO silencía errores: verás en logs si algo no carga.
