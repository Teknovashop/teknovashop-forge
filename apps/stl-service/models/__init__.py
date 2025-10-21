"""
Registro de builders y tabla de alias.
- REGISTRY: builders indexados por slug snake_case
- ALIASES:  cualquier variante (kebab/snake/etiquetas de la UI) -> slug snake_case
"""

from typing import Callable, Dict
import sys, traceback

REGISTRY: Dict[str, Callable] = {}
ALIASES: Dict[str, str] = {}

def _alias(s: str) -> str:
    return (s or "").strip().lower()

def _reg(slug_snake: str, fn: Callable, *aliases: str) -> None:
    REGISTRY[slug_snake] = fn
    # alias propios
    ALIASES[_alias(slug_snake)] = slug_snake
    ALIASES[_alias(slug_snake.replace("_", "-"))] = slug_snake
    for a in aliases:
        if a:
            ALIASES[_alias(a)] = slug_snake

def _safe_import(name: str, prefer: str, slug_snake: str, *aliases: str):
    """
    Importa models.<name> y registra un builder.
    Acepta, en este orden:
      - función: prefer (ej. 'build'), 'build', 'make', 'make_model'
      - dict BUILD: ['make'] o ['build']
    """
    try:
        mod = __import__(f"models.{name}", fromlist=["*"])
        fn = None

        # 1) funciones directas
        for cand in (prefer, "build", "make", "make_model"):
            f = getattr(mod, cand, None)
            if callable(f):
                fn = f
                break

        # 2) diccionario BUILD
        if fn is None and isinstance(getattr(mod, "BUILD", None), dict):
            for cand in ("make", "build"):
                f = mod.BUILD.get(cand)
                if callable(f):
                    fn = f
                    break

        if not callable(fn):
            raise RuntimeError(f"models.{name} no expone builder válido (build/make/make_model o BUILD)")

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
