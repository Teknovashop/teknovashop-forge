# utils/stl_writer.py
# Utilidades mínimas para generar STL ASCII con cajas y cilindros (aprox. poligonal)
import math
from typing import List, Tuple

Vec3 = Tuple[float, float, float]
Tri = Tuple[Vec3, Vec3, Vec3]

def _normal(a: Vec3, b: Vec3, c: Vec3) -> Vec3:
    ax, ay, az = a; bx, by, bz = b; cx, cy, cz = c
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = (uy*vz - uz*vy, uz*vx - ux*vz, ux*vy - uy*vx)
    length = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
    return (nx/length, ny/length, nz/length)

def triangles_to_stl(name: str, tris: List[Tri]) -> bytes:
    lines = [f"solid {name}"]
    for (a,b,c) in tris:
        nx,ny,nz = _normal(a,b,c)
        lines.append(f"  facet normal {nx} {ny} {nz}")
        lines.append("    outer loop")
        for v in (a,b,c):
            lines.append(f"      vertex {v[0]} {v[1]} {v[2]}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {name}")
    return ("\n".join(lines) + "\n").encode("utf-8")

def add_box(tris: List[Tri], cx: float, cy: float, cz: float,
            sx: float, sy: float, sz: float):
    """Caja centrada en (cx,cy,cz) con tamaños sx,sy,sz (mm)."""
    hx, hy, hz = sx/2, sy/2, sz/2
    # 8 vértices
    v = [
        (cx-hx, cy-hy, cz-hz), (cx+hx, cy-hy, cz-hz),
        (cx+hx, cy+hy, cz-hz), (cx-hx, cy+hy, cz-hz),
        (cx-hx, cy-hy, cz+hz), (cx+hx, cy-hy, cz+hz),
        (cx+hx, cy+hy, cz+hz), (cx-hx, cy+hy, cz+hz),
    ]
    # 12 triángulos (2 por cara)
    faces = [
        (0,1,2,3), # bottom
        (4,5,6,7), # top
        (0,1,5,4), # front
        (1,2,6,5), # right
        (2,3,7,6), # back
        (3,0,4,7), # left
    ]
    for a,b,c,d in faces:
        tris.append((v[a], v[b], v[c]))
        tris.append((v[a], v[c], v[d]))

def add_cylinder_z(tris: List[Tri], cx: float, cy: float, z0: float, z1: float,
                   radius: float, segments: int = 48):
    """Cilindro (o pilón) a lo largo de Z entre z0..z1."""
    ang = 2*math.pi/segments
    for i in range(segments):
        a0, a1 = i*ang, (i+1)*ang
        x0, y0 = cx + radius*math.cos(a0), cy + radius*math.sin(a0)
        x1, y1 = cx + radius*math.cos(a1), cy + radius*math.sin(a1)
        # cara lateral (dos triángulos)
        tris.append(((x0,y0,z0), (x1,y1,z0), (x1,y1,z1)))
        tris.append(((x0,y0,z0), (x1,y1,z1), (x0,y0,z1)))
    # tapas
    for i in range(1, segments-1):
        xA,yA = cx + radius*math.cos(0),         cy + radius*math.sin(0)
        xB,yB = cx + radius*math.cos(i*ang),     cy + radius*math.sin(i*ang)
        xC,yC = cx + radius*math.cos((i+1)*ang), cy + radius*math.sin((i+1)*ang)
        tris.append(((xA,yA,z0), (xB,yB,z0), (xC,yC,z0)))  # base
        tris.append(((xA,yA,z1), (xC,yC,z1), (xB,yB,z1)))  # tapa
