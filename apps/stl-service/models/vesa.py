# apps/stl-service/models/vesa.py
"""
Generador de STL para un adaptador VESA (versión 0):
- Placa rectangular (ancho x alto x grosor).
- Sin agujeros aún (los añadimos en la siguiente iteración).
- STL ASCII generado de forma procedimental (sin dependencias externas).
"""

from typing import Dict, Any
import math


def _tri(v1, v2, v3) -> str:
    """Crea un triángulo STL ASCII con normal plana (calculada simple)."""
    # normal aproximada (no es crítico para impresión, la mayoría de slicers lo ignoran)
    # cálculo de normal por producto cruzado
    def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
    def cross(a, b): 
        return (
            a[1]*b[2] - a[2]*b[1],
            a[2]*b[0] - a[0]*b[2],
            a[0]*b[1] - a[1]*b[0],
        )

    u = sub(v2, v1)
    w = sub(v3, v1)
    nx, ny, nz = cross(u, w)
    length = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
    nx, ny, nz = nx/length, ny/length, nz/length

    return (
        f"  facet normal {nx:.6f} {ny:.6f} {nz:.6f}\n"
        f"    outer loop\n"
        f"      vertex {v1[0]:.6f} {v1[1]:.6f} {v1[2]:.6f}\n"
        f"      vertex {v2[0]:.6f} {v2[1]:.6f} {v2[2]:.6f}\n"
        f"      vertex {v3[0]:.6f} {v3[1]:.6f} {v3[2]:.6f}\n"
        f"    endloop\n"
        f"  endfacet\n"
    )


def _quad(v1, v2, v3, v4) -> str:
    """Triangula un quad como dos triángulos (v1,v2,v3) y (v1,v3,v4)."""
    return _tri(v1, v2, v3) + _tri(v1, v3, v4)


def generate_vesa_plate(params: Dict[str, Any]) -> bytes:
    """
    Genera una placa rectangular centrada en el origen:
      - width (mm), height (mm), thickness (mm)

    Devuelve STL ASCII en bytes.
    """
    width = float(params.get("width", 120.0))
    height = float(params.get("height", 120.0))
    thickness = float(params.get("thickness", 5.0))

    # mitad-dimensiones
    hw = width / 2.0
    hh = height / 2.0
    hz = thickness / 2.0

    # 8 vértices del cubo/placa
    # z+: cara superior, z-: cara inferior
    p = {
        "p1": (-hw, -hh, -hz),
        "p2": ( hw, -hh, -hz),
        "p3": ( hw,  hh, -hz),
        "p4": (-hw,  hh, -hz),
        "p5": (-hw, -hh,  hz),
        "p6": ( hw, -hh,  hz),
        "p7": ( hw,  hh,  hz),
        "p8": (-hw,  hh,  hz),
    }

    # 6 caras (como quads)
    faces = []
    # inferior (z-)
    faces.append(_quad(p["p1"], p["p2"], p["p3"], p["p4"]))
    # superior (z+)
    faces.append(_quad(p["p5"], p["p6"], p["p7"], p["p8"]))
    # lateral -y (cara frente)
    faces.append(_quad(p["p1"], p["p2"], p["p6"], p["p5"]))
    # lateral +y (cara atrás)
    faces.append(_quad(p["p4"], p["p3"], p["p7"], p["p8"]))
    # lateral -x
    faces.append(_quad(p["p1"], p["p5"], p["p8"], p["p4"]))
    # lateral +x
    faces.append(_quad(p["p2"], p["p3"], p["p7"], p["p6"]))

    stl = "solid vesa_adapter\n" + "".join(faces) + "endsolid vesa_adapter\n"
    return stl.encode("utf-8")
