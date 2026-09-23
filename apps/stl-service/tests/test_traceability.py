from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app import _make_design_manifest
from model_contracts import PRODUCTS


def test_design_manifest_is_reproducible_and_versioned():
    stl = b"solid test\nendsolid test\n"
    generated_at = datetime(2026, 9, 23, 10, 30, 0, tzinfo=timezone.utc)
    object_path = "vesa-adapter/2026/09/23/103000-demo.stl"

    manifest = _make_design_manifest(
        design_id="demo-design-id",
        generated_at=generated_at,
        storage_slug="vesa-adapter",
        builder_slug="vesa_adapter",
        params={"pattern_from": 75.0, "pattern_to": 100.0},
        holes=[],
        text_ops=[],
        object_path=object_path,
        stl_bytes=stl,
    )

    assert manifest["schema"] == "teknovashop.design.v1"
    assert manifest["design_id"] == "demo-design-id"
    assert manifest["generated_at"] == "2026-09-23T10:30:00+00:00"

    product = manifest["product"]
    assert product["slug"] == "vesa-adapter"
    assert product["builder"] == "vesa_adapter"
    assert product["name"] == PRODUCTS["vesa-adapter"]["name"]
    assert product["version"] == PRODUCTS["vesa-adapter"]["version"]
    assert product["stage"] == PRODUCTS["vesa-adapter"]["stage"]

    artifact = manifest["artifact"]
    assert artifact["format"] == "stl"
    assert artifact["units"] == "mm"
    assert artifact["path"] == object_path
    assert artifact["bytes"] == len(stl)
    assert artifact["sha256"] == hashlib.sha256(stl).hexdigest()


def test_all_product_versions_and_stages_are_nonempty_strings():
    for slug, contract in PRODUCTS.items():
        assert isinstance(contract["version"], str) and contract["version"].strip(), slug
        assert isinstance(contract["stage"], str) and contract["stage"].strip(), slug


def test_manifest_does_not_include_user_identity_fields():
    stl = b"demo"
    manifest = _make_design_manifest(
        design_id="privacy-test",
        generated_at=datetime.now(timezone.utc),
        storage_slug="cable-clip",
        builder_slug="cable_clip",
        params={"cable_d": 6.0},
        holes=[],
        text_ops=[],
        object_path="cable-clip/demo.stl",
        stl_bytes=stl,
    )

    serialized_keys = str(manifest).lower()
    assert "user_id" not in serialized_keys
    assert "email" not in serialized_keys
