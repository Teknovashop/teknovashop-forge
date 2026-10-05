from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from math import cos, radians, sin
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter
import trimesh

from model_contracts import PRODUCTS
from models import REGISTRY


CANVAS = (960, 720)
SUPERSAMPLE = 2
CACHE_VERSION = "studio-v6"
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
    """Clean commercial studio backdrop for generated product photography."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    ny = yy / max(1, h - 1)
    nx = xx / max(1, w - 1)

    top = np.array([240.0, 247.0, 253.0])
    bottom = np.array([163.0, 199.0, 229.0])
    rgb = top[None, None, :] * (1.0 - ny[..., None]) + bottom[None, None, :] * ny[..., None]

    center_glow = np.exp(
        -(
            ((nx - 0.55) / 0.48) ** 2
            + ((ny - 0.34) / 0.40) ** 2
        )
    )
    rgb += center_glow[..., None] * np.array([4.0, 8.0, 16.0])

    dx = (nx - 0.5) / 0.8
    dy = (ny - 0.45) / 0.85
    vignette = np.clip((dx * dx + dy * dy) * 0.10, 0.0, 0.10)
    rgb *= (1.0 - vignette[..., None])

    image = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    horizon = int(h * 0.72)
    draw.line((0, horizon, w, horizon), fill=(255, 255, 255, 88), width=2)
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
        fill=(15, 30, 48, 118),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(34 * SUPERSAMPLE))
    image = Image.alpha_composite(image.convert("RGBA"), shadow_layer)

    draw = ImageDraw.Draw(image, "RGBA")
    object_mask = Image.new("L", render_size, 0)
    object_mask_draw = ImageDraw.Draw(object_mask)

    key_light = np.array([-0.60, -0.50, 0.62], dtype=float)
    key_light /= np.linalg.norm(key_light)
    fill_light = np.array([0.65, 0.20, 0.25], dtype=float)
    fill_light /= np.linalg.norm(fill_light)
    view_dir = np.array([0.0, 0.0, 1.0], dtype=float)
    half_vec = key_light + view_dir
    half_vec /= np.linalg.norm(half_vec)

    faces = np.asarray(mesh.faces, dtype=int)
    normals = np.asarray(mesh.face_normals, dtype=float) @ _rotation_matrix().T
    depths = rotated[faces].mean(axis=1)[:, 2]

    selected = np.asarray(list(_face_indices(mesh)), dtype=int)
    order = selected[np.argsort(depths[selected])]

    for face_index in order:
        face = faces[face_index]
        points = [tuple(map(float, projected[v])) for v in face]
        normal = normals[face_index]

        # Commercial hard-surface material: no wireframe. One-sided diffuse
        # lighting plus a tight specular response gives graphite/anodized
        # surfaces real depth while preserving the exact canonical geometry.
        key = max(0.0, float(np.dot(normal, key_light)))
        fill_amt = max(0.0, float(np.dot(normal, fill_light)))
        specular = max(0.0, float(np.dot(normal, half_vec))) ** 28

        base = np.array([10.0, 13.0, 18.0])
        diffuse_rgb = np.array([65.0, 69.0, 76.0]) * (
            0.10 + key * 0.58 + fill_amt * 0.12
        )
        specular_rgb = np.array([130.0, 140.0, 155.0]) * specular
        rgb = np.clip(base + diffuse_rgb + specular_rgb, 0, 165)

        draw.polygon(
            points,
            fill=(int(rgb[0]), int(rgb[1]), int(rgb[2]), 255),
        )
        object_mask_draw.polygon(points, fill=255)

    # A manufactured-object silhouette, not a CAD outline. This is generated
    # from the final product mask and therefore does not expose triangulation.
    dilated = object_mask.filter(ImageFilter.MaxFilter(9))
    eroded = object_mask.filter(ImageFilter.MinFilter(7))
    outer = ImageChops.subtract(dilated, object_mask)
    inner = ImageChops.subtract(object_mask, eroded)

    outer_layer = Image.new("RGBA", render_size, (2, 7, 12, 0))
    outer_layer.putalpha(outer.point(lambda value: int(value * 0.55)))
    image = Image.alpha_composite(image, outer_layer)

    inner_layer = Image.new("RGBA", render_size, (190, 225, 250, 0))
    inner_layer.putalpha(inner.point(lambda value: int(value * 0.10)))
    image = Image.alpha_composite(image, inner_layer)

    # Add a restrained photographic bloom around the product silhouette.
    # It creates separation from the blueprint background without turning the
    # technical geometry into a neon/wireframe illustration.
    glow = Image.new("RGBA", render_size, (78, 174, 236, 0))
    glow_alpha = object_mask.filter(
        ImageFilter.GaussianBlur(18 * SUPERSAMPLE)
    ).point(lambda v: int(v * 0.04))
    glow.putalpha(glow_alpha)
    image = Image.alpha_composite(glow, image)

    # Downsample once at the end for clean commercial antialiasing.
    image = image.convert("RGB").resize(
        CANVAS,
        Image.Resampling.LANCZOS,
    )

    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    data = out.getvalue()
    _write_disk_cache(slug, data)
    return data
