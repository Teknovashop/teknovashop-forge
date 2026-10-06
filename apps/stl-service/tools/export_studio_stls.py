from __future__ import annotations

import argparse
from pathlib import Path

import trimesh

from model_contracts import PRODUCTS
from models import REGISTRY
from product_catalog import PRODUCT_METADATA


def as_mesh(value):
    if isinstance(value, trimesh.Trimesh):
        return value
    if isinstance(value, trimesh.Scene):
        meshes = [m for m in value.geometry.values() if isinstance(m, trimesh.Trimesh)]
        if meshes:
            return trimesh.util.concatenate(meshes)
    if isinstance(value, (list, tuple)):
        meshes = [m for m in value if isinstance(m, trimesh.Trimesh)]
        if meshes:
            return trimesh.util.concatenate(meshes)
    raise TypeError(f"Unsupported geometry: {type(value).__name__}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", default="engineering")
    parser.add_argument("--slug")
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    selected = []
    for slug, metadata in PRODUCT_METADATA.items():
        if args.slug and slug != args.slug:
            continue
        if not args.slug and metadata.get("stage") != args.stage:
            continue
        contract = PRODUCTS[slug]
        builder = REGISTRY[contract["builder"]]
        mesh = as_mesh(builder(dict(contract["default"]))).copy()
        try:
            mesh.remove_duplicate_faces()
            mesh.remove_degenerate_faces()
            mesh.remove_unreferenced_vertices()
            mesh.merge_vertices()
            mesh.fix_normals(multibody=True)
        except Exception:
            pass

        path = output / f"{slug}.stl"
        payload = mesh.export(file_type="stl")
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        path.write_bytes(bytes(payload))
        selected.append(slug)
        print(f"{slug}: {len(payload)} bytes")

    if not selected:
        raise SystemExit(f"No products with stage={args.stage!r}")
    print(f"Exported {len(selected)} products to {output}")


if __name__ == "__main__":
    main()
