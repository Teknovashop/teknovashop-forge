from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from math import cos, radians, sin
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import trimesh

from model_contracts import PRODUCTS
from models import REGISTRY


CANVAS = (960, 720)


def _rotation_matrix() -> np.ndarray:
    # Fixed isometric-ish product camera. Every product uses exactly the same
    # visual language so catalogue imagery cannot drift between styles.
    az = radians(-38)
    elv = radians(27)
    rz = np.array([
        [cos(az), -sin(az), 0.0],
        [sin(az),  cos(az), 0.0],
        [0.0,      0.0,     1.0],
    ])
    rx = np.array([
        [1.0, 0.0,       0.0],
        [0.0, cos(elv), -sin(elv)],
        [0.0, sin(elv),  cos(elv)],
    ])
    return rx @ rz


def _as_mesh(value) -> trimesh.Trimesh:
    if isinstance(value, trimesh.Trimesh):
        return value
    if isinstance(value, trimesh.Scene):
        return trimesh.util.concatenate(tuple(value.geometry.values()))
    if isinstance(value, (list, tuple)):
        meshes = [item for item in value if isinstance(item, trimesh.Trimesh)]
        if meshes:
            return trimesh.util.concatenate(meshes)
    raise TypeError("Builder did not return renderable mesh geometry")


def _background(size: tuple[int, int]) -> Image.Image:
    w, h = size
    image = Image.new("RGB", size, (7, 19, 33))
    px = image.load()
    for y in range(h):
        t = y / max(1, h - 1)
        # Deep technical navy gradient.
        r = int(7 + 5 * t)
        g = int(19 + 13 * t)
        b = int(33 + 22 * t)
        for x in range(w):
            px[x, y] = (r, g, b)

    draw = ImageDraw.Draw(image, "RGBA")
    # Very restrained engineering grid.
    for x in range(0, w, 48):
        draw.line((x, 0, x, h), fill=(96, 165, 250, 12), width=1)
    for y in range(0, h, 48):
        draw.line((0, y, w, y), fill=(96, 165, 250, 12), width=1)
    return image


def _project(mesh: trimesh.Trimesh, width: int, height: int):
    vertices = np.asarray(mesh.vertices, dtype=float)
    center = (vertices.min(axis=0) + vertices.max(axis=0)) / 2.0
    vertices = vertices - center
    rotated = vertices @ _rotation_matrix().T

    xy = rotated[:, :2]
    span = np.maximum(xy.max(axis=0) - xy.min(axis=0), 1e-6)
    scale = min((width * 0.66) / span[0], (height * 0.64) / span[1])
    projected = xy * scale
    projected[:, 0] += width * 0.5
    projected[:, 1] = height * 0.48 - projected[:, 1]
    return rotated, projected


def _face_indices(mesh: trimesh.Trimesh, maximum: int = 3200) -> Iterable[int]:
    count = len(mesh.faces)
    if count <= maximum:
        return range(count)
    # Deterministic sampling for complex meshes; enough triangles to preserve
    # silhouette while bounding thumbnail render cost.
    return np.linspace(0, count - 1, maximum, dtype=int)


@lru_cache(maxsize=64)
def render_product_thumbnail(slug: str) -> bytes:
    contract = PRODUCTS.get(slug)
    if not contract:
        raise KeyError(slug)

    builder = REGISTRY.get(contract["builder"])
    if builder is None:
        raise KeyError(contract["builder"])

    mesh = _as_mesh(builder(dict(contract["default"])))
    if not len(mesh.vertices) or not len(mesh.faces):
        raise ValueError("Empty catalogue mesh")

    width, height = CANVAS
    image = _background(CANVAS)
    rotated, projected = _project(mesh, width, height)

    # Soft grounding shadow, shared across every model.
    shadow_layer = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer, "RGBA")
    bb = projected.min(axis=0), projected.max(axis=0)
    object_w = max(80.0, float(bb[1][0] - bb[0][0]))
    sd.ellipse(
        (
            width / 2 - object_w * 0.38,
            height * 0.70,
            width / 2 + object_w * 0.38,
            height * 0.77,
        ),
        fill=(0, 0, 0, 85),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(18))
    image = Image.alpha_composite(image.convert("RGBA"), shadow_layer)

    draw = ImageDraw.Draw(image, "RGBA")
    light = np.array([-0.35, -0.45, 0.82], dtype=float)
    light /= np.linalg.norm(light)

    faces = np.asarray(mesh.faces, dtype=int)
    normals = np.asarray(mesh.face_normals, dtype=float) @ _rotation_matrix().T
    depths = rotated[faces].mean(axis=1)[:, 2]

    selected = np.asarray(list(_face_indices(mesh)), dtype=int)
    order = selected[np.argsort(depths[selected])]

    for face_index in order:
        face = faces[face_index]
        points = [tuple(map(float, projected[v])) for v in face]
        normal = normals[face_index]
        intensity = float(np.clip(np.dot(normal, light) * 0.5 + 0.55, 0.18, 1.0))
        fill = (
            int(105 + intensity * 86),
            int(132 + intensity * 78),
            int(162 + intensity * 73),
            255,
        )
        draw.polygon(points, fill=fill)

    # Exact mesh silhouette/feature edges, in the same cyan language as Forge.
    try:
        edge_mesh = mesh.copy()
        edges = np.asarray(edge_mesh.edges_unique, dtype=int)
        if len(edges) > 5000:
            edges = edges[np.linspace(0, len(edges) - 1, 5000, dtype=int)]
        for a, b in edges:
            pa = tuple(map(float, projected[a]))
            pb = tuple(map(float, projected[b]))
            draw.line((pa, pb), fill=(139, 233, 255, 48), width=1)
    except Exception:
        pass

    # Consistent catalogue chip — no marketing claims, only canonical product state.
    draw.rounded_rectangle((38, 38, 177, 73), radius=13, fill=(6, 17, 29, 210), outline=(139, 233, 255, 48), width=1)
    draw.text((56, 49), "FORGE  PARAMETRIC", fill=(139, 233, 255, 220))

    out = BytesIO()
    image.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()
