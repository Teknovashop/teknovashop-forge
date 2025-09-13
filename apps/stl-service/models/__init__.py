# apps/stl-service/models/__init__.py
from .vesa import generate_vesa_plate

MODEL_REGISTRY = {
    "vesa": generate_vesa_plate,
}

__all__ = ["MODEL_REGISTRY", "generate_vesa_plate"]
