from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

import numpy as np
import trimesh

PILOT_CAPABILITIES = {
    "cable-tray": {"hole", "slot", "cutout_rect"},
    "vesa-adapter": {"hole", "slot", "cutout_rect"},
    "enclosure-ip65": {"hole", "slot", "cutout_rect"},
}


@dataclass
class ValidationIssue:
    code: str
    message: str
    level: str = "error"

    def as_dict(self) -> Dict[str, str]:
        return {"code": self.code, "message": self.message, "level": self.level}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _op_type(op: Dict[str, Any]) -> str:
    return str(op.get("type") or "").strip().lower()


def validate_operations(slug: str, operations: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    allowed = PILOT_CAPABILITIES.get(slug, set())
    issues: List[ValidationIssue] = []
    ops = list(operations or [])

    if len(ops) > 24:
        issues.append(ValidationIssue("too_many_operations", "Máximo 24 operaciones por diseño V2."))

    seen = set()
    for index, op in enumerate(ops):
        op_id = str(op.get("id") or "").strip()
        typ = _op_type(op)

        if not op_id:
            issues.append(ValidationIssue("missing_id", f"Operación {index + 1}: falta id."))
        elif op_id in seen:
            issues.append(ValidationIssue("duplicate_id", f"Operación {op_id}: id duplicado."))
        else:
            seen.add(op_id)

        if typ not in allowed:
            issues.append(
                ValidationIssue(
                    "unsupported_operation",
                    f"{slug}: la operación '{typ or 'desconocida'}' no está habilitada.",
                )
            )
            continue

        params = op.get("params") or {}
        if typ == "hole":
            d = _num(params.get("diameter_mm"), 0)
            if d < 2 or d > 40:
                issues.append(ValidationIssue("hole_diameter", f"{op_id}: diámetro permitido 2–40 mm."))
        elif typ == "slot":
            length = _num(params.get("length_mm"), 0)
            width = _num(params.get("width_mm"), 0)
            if length < 4 or width < 2 or length < width:
                issues.append(ValidationIssue("slot_size", f"{op_id}: ranura inválida."))
        elif typ == "cutout_rect":
            width = _num(params.get("width_mm"), 0)
            height = _num(params.get("height_mm"), 0)
            if width < 2 or height < 2:
                issues.append(ValidationIssue("cutout_size", f"{op_id}: corte rectangular inválido."))

        target = (op.get("target") or {}).get("face", "top")
        if target not in {"top", "bottom"}:
            issues.append(
                ValidationIssue(
                    "target_face",
                    f"{op_id}: en la primera iteración V2 solo se permiten caras top/bottom.",
                )
            )

    return [issue.as_dict() for issue in issues]


def _through_height(mesh: trimesh.Trimesh) -> float:
    return max(float(mesh.extents[2]) * 3.0, 20.0)


def _placement_xy(mesh: trimesh.Trimesh, op: Dict[str, Any]) -> tuple[float, float]:
    placement = op.get("placement") or {}
    center = mesh.bounds.mean(axis=0)
    return (
        float(center[0]) + _num(placement.get("x"), 0),
        float(center[1]) + _num(placement.get("y"), 0),
    )


def _fits_xy(mesh: trimesh.Trimesh, x: float, y: float, half_w: float, half_h: float, margin: float = 1.2) -> bool:
    lo, hi = mesh.bounds
    return (
        x - half_w >= float(lo[0]) + margin
        and x + half_w <= float(hi[0]) - margin
        and y - half_h >= float(lo[1]) + margin
        and y + half_h <= float(hi[1]) - margin
    )


def _subtract(mesh: trimesh.Trimesh, cutter: trimesh.Trimesh, op_id: str) -> trimesh.Trimesh:
    try:
        # V2 never uses the legacy "concatenate on boolean failure" fallback.
        # A subtractive operation must be a real Manifold boolean or fail closed.
        result = trimesh.boolean.difference([mesh, cutter], engine="manifold")
    except Exception as exc:
        raise ValueError(f"{op_id}: boolean difference failed: {exc}") from exc

    if not isinstance(result, trimesh.Trimesh) or not len(result.faces):
        raise ValueError(f"{op_id}: la operación no produjo una malla válida")
    if not result.is_watertight or not result.is_winding_consistent:
        raise ValueError(f"{op_id}: la operación produciría una malla no estanca")
    return result


def apply_operations(mesh: trimesh.Trimesh, slug: str, operations: Iterable[Dict[str, Any]]) -> trimesh.Trimesh:
    ops = [op for op in (operations or []) if op.get("enabled", True)]
    issues = validate_operations(slug, ops)
    if issues:
        raise ValueError("; ".join(issue["message"] for issue in issues))

    out = mesh.copy()
    for index, op in enumerate(ops):
        op_id = str(op.get("id") or f"op_{index + 1}")
        typ = _op_type(op)
        params = op.get("params") or {}
        x, y = _placement_xy(out, op)
        z = float(out.bounds.mean(axis=0)[2])
        depth = _through_height(out)

        if typ == "hole":
            d = _num(params.get("diameter_mm"))
            if not _fits_xy(out, x, y, d / 2, d / 2):
                raise ValueError(f"{op_id}: agujero demasiado cerca del borde")
            cutter = trimesh.creation.cylinder(radius=d / 2, height=depth, sections=48)
            cutter.apply_translation((x, y, z))
            out = _subtract(out, cutter, op_id)

        elif typ == "slot":
            length = _num(params.get("length_mm"))
            width = _num(params.get("width_mm"))
            rotation_deg = _num((op.get("placement") or {}).get("rotation_deg"), 0)
            if not _fits_xy(out, x, y, length / 2, width / 2):
                raise ValueError(f"{op_id}: ranura demasiado cerca del borde")
            cutter = trimesh.creation.box(extents=(length, width, depth))
            if rotation_deg:
                cutter.apply_transform(
                    trimesh.transformations.rotation_matrix(
                        np.deg2rad(rotation_deg), [0, 0, 1]
                    )
                )
            cutter.apply_translation((x, y, z))
            out = _subtract(out, cutter, op_id)

        elif typ == "cutout_rect":
            width = _num(params.get("width_mm"))
            height = _num(params.get("height_mm"))
            if not _fits_xy(out, x, y, width / 2, height / 2):
                raise ValueError(f"{op_id}: corte demasiado cerca del borde")
            cutter = trimesh.creation.box(extents=(width, height, depth))
            cutter.apply_translation((x, y, z))
            out = _subtract(out, cutter, op_id)

    return out
