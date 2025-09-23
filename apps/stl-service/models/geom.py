# models/geom.py
from dataclasses import dataclass
from typing import Any, Iterable

@dataclass
class Vec:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    # util
    def as_tuple(self): return (self.x, self.y, self.z)
    def __iter__(self): yield from (self.x, self.y, self.z)
    # operadores
    def __neg__(self):       return Vec(-self.x, -self.y, -self.z)
    def __add__(self, o):    o = vec3(o); return Vec(self.x+o.x, self.y+o.y, self.z+o.z)
    def __sub__(self, o):    o = vec3(o); return Vec(self.x-o.x, self.y-o.y, self.z-o.z)
    def __mul__(self, s: float):  return Vec(self.x*s, self.y*s, self.z*s)
    def __rmul__(self, s: float): return self.__mul__(s)
    def __truediv__(self, s: float): return Vec(self.x/s, self.y/s, self.z/s)

def vec3(obj: Any) -> Vec:
    """Convierte dict/tuple/list/Vec a Vec; tolera {x,y,z} o {x_mm,z_mm}."""
    if isinstance(obj, Vec):
        return obj
    if isinstance(obj, dict):
        x = obj.get("x", obj.get("x_mm", 0.0))
        y = obj.get("y", obj.get("y_mm", 0.0))
        z = obj.get("z", obj.get("z_mm", 0.0))
        return Vec(float(x or 0.0), float(y or 0.0), float(z or 0.0))
    if isinstance(obj, Iterable):
        tup = tuple(obj)
        if len(tup) == 3:
            return Vec(float(tup[0]), float(tup[1]), float(tup[2]))
    # fallback: escalar a eje X
    try:
        return Vec(float(obj), 0.0, 0.0)
    except Exception:
        return Vec()
