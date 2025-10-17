# Construye el registro de modelos automáticamente a partir
# de los módulos que ya existen en este paquete.
import importlib
import pkgutil
from typing import Callable, Dict

REGISTRY: Dict[str, Callable] = {}

def _register_all() -> None:
    """
    Recorre todos los módulos del paquete `models`, importa cada uno
    y si expone una función `make(...)`, lo registra con el nombre del
    módulo (por ejemplo: models/cable_tray.py -> "cable_tray").
    Ignora los módulos que empiezan por "_".
    """
    pkg = __name__
    for mod in pkgutil.iter_modules(__path__):  # type: ignore[name-defined]
        name = mod.name
        if name.startswith("_"):
            continue
        module = importlib.import_module(f"{pkg}.{name}")
        make = getattr(module, "make", None)
        if callable(make):
            REGISTRY[name] = make

# Construcción perezosa, pero ejecutamos al importar para que
# el registro esté listo cuando `app.py` lo necesite.
_register_all()

# Aliases opcionales por si el front usa un nombre distinto al nombre del fichero.
ALIASES = {
    # Si en el front aparece "vesa_adapter" pero el fichero se llama "vesa_mount.py",
    # mapea aquí: "vesa_adapter": "vesa_mount",
    # Añade los que necesites; si no hay alias, se usará exactamente el nombre del módulo.
}
