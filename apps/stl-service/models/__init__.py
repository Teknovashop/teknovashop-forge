# apps/stl-service/models/__init__.py
"""
Carga de builders y tabla de alias para aceptar tanto kebab-case (UI)
como snake_case (código antiguo). REGISTRY expone los builders por slug
normalizado (snake) y ALIASES traduce cualquier variante a ese slug.
"""

from typing import Callable, Dict

REGISTRY: Dict[str, Callable] = {}
ALIASES: Dict[str, str] = {}

def _reg(slug_snake: str, fn: Callable, *more_aliases: str):
    # Guardamos por snake_case en el registro
    REGISTRY[slug_snake] = fn
    # Alias obvios: snake y kebab en minúsculas
    kebab = slug_snake.replace("_", "-")
    ALIASES[slug_snake] = slug_snake
    ALIASES[kebab] = slug_snake
    # Alias adicionales (tanto kebab como snake y variantes)
    for a in more_aliases:
        a = a.strip()
        if not a:
            continue
        ALIASES[a] = slug_snake
        ALIASES[a.replace("_", "-")] = slug_snake
        ALIASES[a.replace("-", "_")] = slug_snake

# -------------------------
# IMPORTA AQUÍ TUS BUILDERS
# -------------------------
# Nota: no estoy creando archivos nuevos; sólo referencio lo que ya tienes.
# Si algún import no existe en tu repo, coméntalo o crea el alias correcto.
try:
    from .vesa_adapter import build as vesa_adapter
    _reg("vesa_adapter", vesa_adapter, "vesa-adapter")
except Exception:
    pass

try:
    from .router_mount import build as router_mount
    _reg("router_mount", router_mount, "router-mount", "soporte-de-router", "router-mount-pack")
except Exception:
    pass

try:
    from .cable_tray import build as cable_tray
    _reg("cable_tray", cable_tray, "bandeja-de-cables", "cable-tray")
except Exception:
    pass

try:
    from .phone_dock import build as phone_dock
    _reg("phone_dock", phone_dock, "dock-para-movil-usb-c", "phone-dock")
except Exception:
    pass

try:
    from .tablet_stand import build as tablet_stand
    _reg("tablet_stand", tablet_stand, "soporte-de-tablet", "tablet-stand")
except Exception:
    pass

try:
    from .monitor_stand import build as monitor_stand
    _reg("monitor_stand", monitor_stand, "elevador-de-monitor", "monitor-stand")
except Exception:
    pass

try:
    from .raspi_case import build as raspi_case
    _reg("raspi_case", raspi_case, "caja-raspberry-pi", "raspi-case")
except Exception:
    pass

try:
    from .go_pro_mount import build as go_pro_mount
    _reg("go_pro_mount", go_pro_mount, "soporte-gopro", "go-pro-mount", "gopro-mount")
except Exception:
    pass

try:
    from .mic_arm_clip import build as mic_arm_clip
    _reg("mic_arm_clip", mic_arm_clip, "clip-brazo-mic", "mic-arm-clip")
except Exception:
    pass

try:
    from .ssd_holder import build as ssd_holder
    _reg("ssd_holder", ssd_holder, "caddy-ssd-2-5-a-3-5", "ssd-holder")
except Exception:
    pass

try:
    from .camera_plate import build as camera_plate
    _reg("camera_plate", camera_plate, "camera-plate")
except Exception:
    pass

try:
    from .wall_hook import build as wall_hook
    _reg("wall_hook", wall_hook, "wall-hook", "gancho-pared")
except Exception:
    pass

try:
    from .wall_bracket import build as wall_bracket
    _reg("wall_bracket", wall_bracket, "wall-bracket", "soporte-pared")
except Exception:
    pass

# -------------------------
# UTIL DE TEXTO (opcional)
# -------------------------
# Si tu repo define apply_text_ops en otra ruta, el app.py ya lo busca
# en 3 ubicaciones; aquí no necesitamos re-exportarla.
