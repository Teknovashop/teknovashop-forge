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
SUPERSAMPLE = 2


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
    """Premium neutral technical backdrop.

    Rendered with numpy instead of per-pixel Python loops so we can afford
    supersampling without making catalogue responses slow.
    """
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    ny = yy / max(1, h - 1)
    nx = xx / max(1, w - 1)

    top = np.array([8.0, 20.0, 34.0])
    bottom = np.array([12.0, 31.0, 49.0])
    rgb = top[None, None, :] * (1.0 - ny[..., None]) + bottom[None, None, :] * ny[..., None]

    # Soft cyan studio glow behind the model, plus a restrained vignette.
    glow = np.exp(
        -(
            ((nx - 0.62) / 0.34) ** 2
            + ((ny - 0.30) / 0.30) ** 2
        )
    )
    rgb += glow[..., None] * np.array([9.0, 22.0, 31.0])

    dx = (nx - 0.5) / 0.72
    dy = (ny - 0.48) / 0.76
    vignette = np.clip((dx * dx + dy * dy) * 0.22, 0.0, 0.22)
    rgb *= (1.0 - vignette[..., None])

    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(image, "RGBA")

    # Fine engineering grid kept deliberately subtle.
    grid = 64 * SUPERSAMPLE
    for x in range(0, w, grid):
        draw.line((x, 0, x, h), fill=(116, 196, 255, 9), width=1)
    for y in range(0, h, grid):
        draw.line((0, y, w, y), fill=(116, 196, 255, 9), width=1)
    return image


def _project(mesh: trimesh.Trimesh, width: int, height: int):
    vertices = np.asarray(mesh.vertices, dtype=float)
    center = (vertices.min(axis=0) + vertices.max(axis=0)) / 2.0
    vertices = vertices - center
    rotated = vertices @ _rotation_matrix().T

    xy = rotated[:, :2]
    span = np.maximum(xy.max(axis=0) - xy.min(axis=0), 1e-6)
    scale = min((width * 0.72) / span[0], (height * 0.68) / span[1])
    projected = xy * scale
    projected[:, 0] += width * 0.5
    projected[:, 1] = height * 0.49 - projected[:, 1]
    return rotated, projected


def _face_indices(mesh: trimesh.Trimesh, maximum: int = 5200) -> Iterable[int]:
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

    output_width, output_height = CANVAS
    width = output_width * SUPERSAMPLE
    height = output_height * SUPERSAMPLE
    render_size = (width, height)

    image = _background(render_size)
    rotated, projected = _project(mesh, width, height)

    # Soft grounding shadow, shared across every model.
    shadow_layer = Image.new("RGBA", render_size, (0, 0, 0, 0))
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
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(24 * SUPERSAMPLE))
    image = Image.alpha_composite(image.convert("RGBA"), shadow_layer)

    draw = ImageDraw.Draw(image, "RGBA")
    key_light = np.array([-0.38, -0.52, 0.76], dtype=float)
    key_light /= np.linalg.norm(key_light)
    fill_light = np.array([0.68, 0.10, 0.38], dtype=float)
    fill_light /= np.linalg.norm(fill_light)
    rim_light = np.array([0.10, 0.72, 0.68], dtype=float)
    rim_light /= np.linalg.norm(rim_light)

    faces = np.asarray(mesh.faces, dtype=int)
    normals = np.asarray(mesh.face_normals, dtype=float) @ _rotation_matrix().T
    depths = rotated[faces].mean(axis=1)[:, 2]

    selected = np.asarray(list(_face_indices(mesh)), dtype=int)
    order = selected[np.argsort(depths[selected])]

    for face_index in order:
        face = faces[face_index]
        points = [tuple(map(float, projected[v])) for v in face]
        normal = normals[face_index]
        key = max(0.0, float(np.dot(normal, key_light)))
        fill_amt = max(0.0, float(np.dot(normal, fill_light)))
        rim = max(0.0, float(np.dot(normal, rim_light)))

        # Cool matte polymer / anodized-metal language shared by every piece.
        intensity = float(np.clip(0.32 + key * 0.50 + fill_amt * 0.14, 0.22, 0.98))
        base = np.array([132.0, 154.0, 178.0])
        highlight = np.array([82.0, 91.0, 96.0]) * intensity
        cyan_rim = np.array([8.0, 23.0, 30.0]) * rim
        rgb = np.clip(base + highlight + cyan_rim, 0, 245)
        draw.polygon(
            points,
            fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255),
        )

    # Exact mesh silhouette/feature edges, in the same cyan language as Forge.
    try:
        edge_mesh = mesh.copy()
        edges = np.asarray(edge_mesh.edges_unique, dtype=int)
        if len(edges) > 5000:
            edges = edges[np.linspace(0, len(edges) - 1, 5000, dtype=int)]
        for a, b in edges:
            pa = tuple(map(float, projected[a]))
            pb = tuple(map(float, projected[b]))
            draw.line(
                (pa, pb),
                fill=(155, 235, 255, 38),
                width=max(1, SUPERSAMPLE),
            )
    except Exception:
        pass

    # Downsample once at the end. This removes jagged triangle edges and gives
    # the generated catalogue pieces a consistent studio-render finish.
    image = image.convert("RGB").resize(
        CANVAS,
        Image.Resampling.LANCZOS,
    )

    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()
