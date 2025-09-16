# apps/stl-service/utils/watermark.py
import qrcode
import numpy as np
import trimesh
from trimesh.transformations import translation_matrix as T

def _qr_mesh(url: str, pixel: float = 0.8, thickness: float = 0.6) -> trimesh.Trimesh:
    qr = qrcode.QRCode(border=1, box_size=1)
    qr.add_data(url)
    qr.make(fit=True)
    m = qr.get_matrix()  # bool matrix
    h = len(m); w = len(m[0])
    cubes=[]
    offx, offz = -w*pixel/2, -h*pixel/2
    for j,row in enumerate(m):
        for i,val in enumerate(row):
            if not val: continue
            b = trimesh.creation.box(extents=[pixel, thickness, pixel])
            b.apply_transform(T([offx + i*pixel + pixel/2, 0, offz + j*pixel + pixel/2]))
            cubes.append(b)
    return trimesh.util.concatenate(cubes) if cubes else trimesh.creation.box([0.1,0.1,0.1])

def add_watermark_plaque(mesh: trimesh.Trimesh, qr_url: str, text: str = "FORGE") -> trimesh.Trimesh:
    """
    Añade una plaquita de 20x20mm con QR extruido y la pega bajo la pieza.
    No realiza booleanos (se queda pegada).
    """
    bbox = mesh.bounds
    size = bbox[1] - bbox[0]
    # placa
    plaque = trimesh.creation.box(extents=[22.0, 1.2, 22.0])
    # QR
    qr = _qr_mesh(qr_url, pixel=0.9, thickness=0.7)
    qr.apply_transform(T([0, 0.75, 0]))  # encima de la placa

    # posicionarla bajo la pieza, esquina X+, Z+
    px = bbox[1,0] - 12.0
    py = bbox[0,1] - 2.0
    pz = bbox[1,2] - 12.0
    plaque.apply_transform(T([px, py, pz]))
    qr.apply_transform(T([px, py, pz]))

    return trimesh.util.concatenate([mesh, plaque, qr])
