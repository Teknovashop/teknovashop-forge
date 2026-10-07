from __future__ import annotations

import argparse
import hashlib
import io
import json
from typing import Any

import numpy as np
import trimesh

from model_contracts import PRODUCTS
from models import REGISTRY
from product_catalog import PRODUCT_METADATA


def _as_mesh(value: Any) -> trimesh.Trimesh:
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
    raise TypeError(f"unsupported geometry: {type(value).__name__}")


def _fingerprint(mesh: trimesh.Trimesh) -> str:
    payload = mesh.export(file_type="stl")
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(bytes(payload)).hexdigest()


def audit_product(slug: str) -> dict[str, Any]:
    contract = PRODUCTS.get(slug)
    metadata = PRODUCT_METADATA.get(slug)
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    check("contract", contract is not None, "canonical geometry contract")
    check("commercial_metadata", metadata is not None, "canonical commercial metadata")
    if not contract or not metadata:
        return {"slug": slug, "ok": False, "checks": checks}

    builder_name = str(contract.get("builder") or "")
    builder = REGISTRY.get(builder_name)
    check("builder_registered", callable(builder), builder_name)
    if not callable(builder):
        return {"slug": slug, "ok": False, "stage": metadata.get("stage"), "checks": checks}

    try:
        default_mesh = _as_mesh(builder(dict(contract["default"])))
        variant_mesh = _as_mesh(builder(dict(contract.get("variant") or contract["default"])))
    except Exception as exc:
        check("geometry_build", False, f"{type(exc).__name__}: {exc}")
        return {"slug": slug, "ok": False, "stage": metadata.get("stage"), "checks": checks}

    check("geometry_build", True)
    extents = np.asarray(default_mesh.extents, dtype=float)
    check(
        "finite_extents",
        bool(np.all(np.isfinite(extents)) and np.all(extents > 0)),
        str([round(float(v), 3) for v in extents.tolist()]),
    )
    check("non_empty_mesh", len(default_mesh.vertices) > 0 and len(default_mesh.faces) > 0)
    check("watertight", bool(default_mesh.is_watertight), f"components={len(default_mesh.split())}")
    check(
        "variant_changes_geometry",
        _fingerprint(default_mesh) != _fingerprint(variant_mesh),
        "default and variant STL fingerprints must differ",
    )

    min_extents = np.asarray(contract.get("min_extents") or [], dtype=float)
    min_ok = len(min_extents) == 3 and bool(np.all(extents + 1e-6 >= min_extents))
    check("minimum_product_envelope", min_ok, f"min={min_extents.tolist() if len(min_extents) else None}")

    stage = str(metadata.get("stage") or "engineering")
    if stage == "production":
        image = metadata.get("marketing_image")
        check(
            "production_marketing_asset",
            isinstance(image, str)
            and image.startswith((
                "/images/products/professional/",
                "/images/products/premium-v1/",
            )),
            str(image),
        )
        check("production_visual_source", metadata.get("visual_source") == "studio_asset")
        check("production_version", not str(contract.get("version", "")).endswith("beta.1"))
    else:
        check("release_not_overstated", metadata.get("marketing_image") is None or stage == "visual_qa")

    ok = all(item["ok"] for item in checks)
    return {
        "slug": slug,
        "name": metadata.get("name") or contract.get("name"),
        "stage": stage,
        "version": contract.get("version"),
        "ok": ok,
        "checks": checks,
    }


def audit_catalog() -> dict[str, Any]:
    reports = [audit_product(slug) for slug in PRODUCTS]
    return {
        "ok": all(report["ok"] for report in reports),
        "count": len(reports),
        "passed": sum(1 for report in reports if report["ok"]),
        "failed": sum(1 for report in reports if not report["ok"]),
        "reports": reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Teknovashop canonical product release gate")
    parser.add_argument("slug", nargs="?", help="Audit one canonical product")
    parser.add_argument("--all", action="store_true", help="Audit the complete catalog")
    args = parser.parse_args()

    report = audit_catalog() if args.all or not args.slug else audit_product(args.slug)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report.get("ok") else 1)


if __name__ == "__main__":
    main()
