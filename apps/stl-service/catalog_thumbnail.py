from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from math import cos, radians, sin
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import trimesh

from model_contracts import PRODUCTS
from models import REGISTRY


CANVAS = (960, 720)
SUPERSAMPLE = 2
CACHE_VERSION = "studio-v3"
CACHE_DIR = Path(__file__).resolve().parent / ".catalog-thumbnail-cache" / CACHE_VERSION


def _cache_path(slug: str) -> Path:
    return CACHE_DIR / f"{slug}.png"


def _read_disk_cache(slug: str) -> bytes | None:
    path = _cache_path(slug)
    try:
        if not path.is_file():
            return None
        data = path.read_bytes()
        if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) > 5000:
            return data
    except OSError:
        return None
    return None


def _write_disk_cache(slug: str, data: bytes) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(slug)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    except OSError:
        # Runtime caching is an optimization. Rendering must still work on
        # read-only filesystems.
        pass



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
    """Bright studio backdrop aligned with Teknovashop's professional renders.

    The generated geometry must feel like the same product family as the
    hand-authored Studio Render cards: icy blue light, restrained technical
    grid and enough contrast for dark product geometry.
    """
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    ny = yy / max(1, h - 1)
    nx = xx / max(1, w - 1)

    top = np.array([236.0, 247.0, 255.0])
    bottom = np.array([183.0, 218.0, 246.0])
    rgb = top[None, None, :] * (1.0 - ny[..., None]) + bottom[None, None, :] * ny[..., None]

    # Broad white key light from upper-left and cool blue bloom behind object.
    key_glow = np.exp(
        -(
            ((nx - 0.26) / 0.34) ** 2
            + ((ny - 0.18) / 0.30) ** 2
        )
    )
    blue_glow = np.exp(
        -(
            ((nx - 0.72) / 0.38) ** 2
            + ((ny - 0.38) / 0.40) ** 2
        )
    )
    rgb += key_glow[..., None] * np.array([18.0, 18.0, 18.0])
    rgb += blue_glow[..., None] * np.array([-8.0, 6.0, 18.0])

    # Keep the edges slightly cooler/darker so cards remain visually framed.
    dx = (nx - 0.5) / 0.78
    dy = (ny - 0.47) / 0.82
    vignette = np.clip((dx * dx + dy * dy) * 0.12, 0.0, 0.12)
    rgb *= (1.0 - vignette[..., None])

    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(image, "RGBA")

    grid = 72 * SUPERSAMPLE
    for x in range(0, w, grid):
        draw.line((x, 0, x, h), fill=(30, 111, 180, 14), width=1)
    for y in range(0, h, grid):
        draw.line((0, y, w, y), fill=(30, 111, 180, 14), width=1)

    # Faint horizon gives the object a studio-table feeling without faking
    # geometry or adding product-specific decoration.
    horizon = int(h * 0.71)
    draw.line((0, horizon, w, horizon), fill=(255, 255, 255, 70), width=2)
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


@lru_cache(maxsize=128)
def render_product_thumbnail(slug: str) -> bytes:
    cached = _read_disk_cache(slug)
    if cached is not None:
        return cached
    contract = PRODUCTS.get(slug)
    if not contract:
        raise KeyError(slug)

    builder = REGISTRY.get(contract["builder"])
    if builder is None:
        raise KeyError(contract["builder"])

    mesh = _as_mesh(builder(dict(contract["default"]))).copy()
    if not len(mesh.vertices) or not len(mesh.faces):
        raise ValueError("Empty catalogue mesh")

    # Normalize winding/normals before shading. Several legacy builders return
    # triangulated planar faces with inconsistent triangle orientation; without
    # this, a single flat panel can look like a faceted low-poly object.
    try:
        mesh.fix_normals(multibody=True)
    except TypeError:
        mesh.fix_normals()

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
        fill=(18, 46, 76, 92),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(26 * SUPERSAMPLE))
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
        # Use two-sided diffuse terms. The catalogue renderer is a product
        # presentation layer, not a diagnostic normal viewer; opposite winding
        # on coplanar triangles must not create visible triangular patches.
        key = abs(float(np.dot(normal, key_light)))
        fill_amt = abs(float(np.dot(normal, fill_light)))
        rim = abs(float(np.dot(normal, rim_light)))

        # Dark anodized-metal / technical polymer language matching the
        # professional product cards. The brighter background provides the
        # separation, while specular-like lighting keeps geometry readable.
        intensity = float(np.clip(0.28 + key * 0.56 + fill_amt * 0.16, 0.18, 1.0))
        base = np.array([15.0, 24.0, 34.0])
        highlight = np.array([82.0, 102.0, 122.0]) * intensity
        cyan_rim = np.array([12.0, 44.0, 58.0]) * rim
        rgb = np.clip(base + highlight + cyan_rim, 0, 190)
        draw.polygon(
            points,
            fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255),
        )

    # Draw only real feature creases. Rendering every triangulation edge made
    # flat surfaces look like wireframe/low-poly meshes. Adjacency angles let
    # us keep meaningful product edges while hiding internal tessellation.
    try:
        adjacency_edges = np.asarray(mesh.face_adjacency_edges, dtype=int)
        adjacency_angles = np.asarray(mesh.face_adjacency_angles, dtype=float)
        sharp = adjacency_edges[adjacency_angles >= np.deg2rad(24.0)]
        if len(sharp) > 2400:
            sharp = sharp[np.linspace(0, len(sharp) - 1, 2400, dtype=int)]
        for a, b in sharp:
            pa = tuple(map(float, projected[a]))
            pb = tuple(map(float, projected[b]))
            draw.line(
                (pa, pb),
                fill=(202, 242, 255, 74),
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
    data = out.getvalue()
    _write_disk_cache(slug, data)
    return data
