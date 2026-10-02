from __future__ import annotations

import io
import tempfile
from pathlib import Path

import cadquery as cq
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

app = FastAPI(title="Teknovashop CAD V2", version="0.2.0")

SUPPORTED_OPERATIONS = (
    "hole",
    "slot",
    "cutout_rect",
    "cutout_circle",
    "counterbore",
    "pocket_rect",
    "hole_pattern",
    "vesa_pattern",
    "vent_linear",
    "vent_hex",
    "cable_channel",
    "rib",
    "boss",
)


class PlateRequest(BaseModel):
    width: float = Field(120, ge=20, le=500)
    height: float = Field(80, ge=20, le=500)
    thickness: float = Field(6, ge=2, le=40)
    corner_radius: float = Field(4, ge=0, le=30)
    chamfer: float = Field(1, ge=0, le=10)


def build_plate(body: PlateRequest):
    part = cq.Workplane("XY").box(body.width, body.height, body.thickness)
    if body.corner_radius > 0:
        max_radius = min(body.width, body.height) / 2 - 0.5
        radius = min(body.corner_radius, max_radius)
        part = part.edges("|Z").fillet(radius)
    if body.chamfer > 0:
        max_chamfer = max(0.0, body.thickness / 2 - 0.25)
        amount = min(body.chamfer, max_chamfer)
        if amount > 0:
            part = part.faces(">Z").edges().chamfer(amount)
    return part


class CadOperation(BaseModel):
    type: str
    x: float = 0
    y: float = 0
    rotation_deg: float = 0
    enabled: bool = True
    diameter_mm: float | None = None
    length_mm: float | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    depth_mm: float | None = None
    through_diameter_mm: float | None = None
    bore_diameter_mm: float | None = None
    bore_depth_mm: float | None = None
    pitch_mm: float | None = None
    count: int | None = None
    rows: int | None = None
    cols: int | None = None
    spacing_mm: float | None = None
    spacing_x_mm: float | None = None
    spacing_y_mm: float | None = None
    radius_mm: float | None = None
    gap_mm: float | None = None


class PlateDesignRequest(PlateRequest):
    operations: list[CadOperation] = Field(default_factory=list, max_length=24)


def _positive(value: float | None, name: str, minimum: float = 0.1) -> float:
    if value is None or value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return float(value)


def apply_plate_operations(part, operations: list[CadOperation]):
    for operation in operations:
        if not operation.enabled:
            continue

        typ = operation.type.strip().lower()
        x = float(operation.x)
        y = float(operation.y)

        if typ == "hole":
            diameter = _positive(operation.diameter_mm, "diameter_mm", 2)
            part = part.faces(">Z").workplane().center(x, y).hole(diameter)

        elif typ == "slot":
            length = _positive(operation.length_mm, "length_mm", 4)
            width = _positive(operation.width_mm, "width_mm", 2)
            if length < width:
                raise ValueError("slot length must be >= width")
            part = (
                part.faces(">Z")
                .workplane()
                .center(x, y)
                .slot2D(length, width, angle=operation.rotation_deg)
                .cutThruAll()
            )

        elif typ == "cutout_rect":
            width = _positive(operation.width_mm, "width_mm", 2)
            height = _positive(operation.height_mm, "height_mm", 2)
            part = (
                part.faces(">Z")
                .workplane()
                .center(x, y)
                .rect(width, height)
                .cutThruAll()
            )

        elif typ == "cutout_circle":
            diameter = _positive(operation.diameter_mm, "diameter_mm", 4)
            part = (
                part.faces(">Z")
                .workplane()
                .center(x, y)
                .circle(diameter / 2)
                .cutThruAll()
            )

        elif typ == "counterbore":
            through_d = _positive(
                operation.through_diameter_mm, "through_diameter_mm", 2
            )
            bore_d = _positive(operation.bore_diameter_mm, "bore_diameter_mm", 3)
            bore_depth = _positive(operation.bore_depth_mm, "bore_depth_mm", 0.5)
            if bore_d <= through_d:
                raise ValueError("bore diameter must be greater than through diameter")
            part = (
                part.faces(">Z")
                .workplane()
                .center(x, y)
                .cboreHole(through_d, bore_d, bore_depth)
            )

        elif typ == "pocket_rect":
            width = _positive(operation.width_mm, "width_mm", 4)
            height = _positive(operation.height_mm, "height_mm", 4)
            depth = _positive(operation.depth_mm, "depth_mm", 0.4)
            part = (
                part.faces(">Z")
                .workplane()
                .center(x, y)
                .rect(width, height)
                .cutBlind(-depth)
            )

        elif typ == "hole_pattern":
            diameter = _positive(operation.diameter_mm, "diameter_mm", 2)
            rows = int(operation.rows or 2)
            cols = int(operation.cols or 2)
            if rows < 1 or rows > 12 or cols < 1 or cols > 12:
                raise ValueError("rows and cols must be between 1 and 12")
            sx = _positive(operation.spacing_x_mm, "spacing_x_mm", 2)
            sy = _positive(operation.spacing_y_mm, "spacing_y_mm", 2)
            points = []
            for row in range(rows):
                for col in range(cols):
                    px = x + (col - (cols - 1) / 2) * sx
                    py = y + (row - (rows - 1) / 2) * sy
                    points.append((px, py))
            part = part.faces(">Z").workplane().pushPoints(points).hole(diameter)

        elif typ == "vent_linear":
            count = int(operation.count or 5)
            if count < 1 or count > 24:
                raise ValueError("count must be between 1 and 24")
            length = _positive(operation.length_mm, "length_mm", 6)
            width = _positive(operation.width_mm, "width_mm", 1.5)
            spacing = _positive(operation.spacing_mm, "spacing_mm", width + 1)
            if length < width:
                raise ValueError("vent length must be >= width")
            for index in range(count):
                py = y + (index - (count - 1) / 2) * spacing
                part = (
                    part.faces(">Z")
                    .workplane()
                    .center(x, py)
                    .slot2D(length, width, angle=operation.rotation_deg)
                    .cutThruAll()
                )

        elif typ == "vent_hex":
            rows = int(operation.rows or 2)
            cols = int(operation.cols or 3)
            if rows < 1 or rows > 10 or cols < 1 or cols > 12:
                raise ValueError("rows/cols outside supported vent range")
            radius = _positive(operation.radius_mm, "radius_mm", 1.5)
            gap = _positive(operation.gap_mm, "gap_mm", 0.5)
            sx = radius * 2 + gap
            sy = radius * 1.75 + gap
            for row in range(rows):
                row_shift = sx / 2 if row % 2 else 0
                for col in range(cols):
                    px = x + (col - (cols - 1) / 2) * sx + row_shift
                    py = y + (row - (rows - 1) / 2) * sy
                    part = (
                        part.faces(">Z")
                        .workplane()
                        .center(px, py)
                        .polygon(6, radius * 2)
                        .cutThruAll()
                    )

        elif typ == "cable_channel":
            length = _positive(operation.length_mm, "length_mm", 6)
            width = _positive(operation.width_mm, "width_mm", 2)
            if length < width:
                raise ValueError("channel length must be >= width")
            part = (
                part.faces(">Z")
                .workplane()
                .center(x, y)
                .slot2D(length, width, angle=operation.rotation_deg)
                .cutThruAll()
            )

        elif typ == "rib":
            length = _positive(operation.length_mm, "length_mm", 4)
            width = _positive(operation.width_mm, "width_mm", 1.5)
            height = _positive(operation.height_mm, "height_mm", 1)
            part = (
                part.faces(">Z")
                .workplane()
                .center(x, y)
                .transformed(rotate=(0, 0, operation.rotation_deg))
                .rect(length, width)
                .extrude(height, combine=True)
            )

        elif typ == "vesa_pattern":
            pitch = _positive(operation.pitch_mm, "pitch_mm", 20)
            diameter = _positive(operation.diameter_mm, "diameter_mm", 3)
            half = pitch / 2
            points = [
                (x - half, y - half),
                (x - half, y + half),
                (x + half, y - half),
                (x + half, y + half),
            ]
            part = part.faces(">Z").workplane().pushPoints(points).hole(diameter)

        elif typ == "boss":
            diameter = _positive(operation.diameter_mm, "diameter_mm", 4)
            height = _positive(operation.height_mm, "height_mm", 1)
            part = (
                part.faces(">Z")
                .workplane()
                .center(x, y)
                .circle(diameter / 2)
                .extrude(height, combine=True)
            )

        else:
            raise ValueError(f"Unsupported CAD operation: {typ}")

        solid = part.val()
        if not solid.isValid() or solid.Volume() <= 0:
            raise ValueError(f"{typ} produced an invalid B-Rep")

    return part


def build_plate_design(body: PlateDesignRequest):
    base = build_plate(
        PlateRequest(
            width=body.width,
            height=body.height,
            thickness=body.thickness,
            corner_radius=body.corner_radius,
            chamfer=body.chamfer,
        )
    )
    return apply_plate_operations(base, body.operations)



@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "teknovashop-cad-v2",
        "engine": "cadquery",
        "cadquery_version": cq.__version__,
        "operations": list(SUPPORTED_OPERATIONS),
    }


@app.post("/v2/plate/stl")
def plate_stl(body: PlateRequest):
    try:
        part = build_plate(body)
        with tempfile.NamedTemporaryFile(suffix=".stl") as tmp:
            cq.exporters.export(part, tmp.name, exportType="STL")
            tmp.seek(0)
            data = tmp.read()
        return Response(data, media_type="model/stl")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CAD generation failed: {exc}") from exc


@app.post("/v2/plate/step")
def plate_step(body: PlateRequest):
    try:
        part = build_plate(body)
        with tempfile.NamedTemporaryFile(suffix=".step") as tmp:
            cq.exporters.export(part, tmp.name, exportType="STEP")
            tmp.seek(0)
            data = tmp.read()
        return Response(data, media_type="application/step")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CAD generation failed: {exc}") from exc


@app.post("/v2/plate/design/stl")
def plate_design_stl(body: PlateDesignRequest):
    try:
        part = build_plate_design(body)
        with tempfile.NamedTemporaryFile(suffix=".stl") as tmp:
            cq.exporters.export(part, tmp.name, exportType="STL")
            tmp.seek(0)
            data = tmp.read()
        return Response(data, media_type="model/stl")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CAD operation failed: {exc}") from exc


@app.post("/v2/plate/design/step")
def plate_design_step(body: PlateDesignRequest):
    try:
        part = build_plate_design(body)
        with tempfile.NamedTemporaryFile(suffix=".step") as tmp:
            cq.exporters.export(part, tmp.name, exportType="STEP")
            tmp.seek(0)
            data = tmp.read()
        return Response(data, media_type="application/step")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CAD operation failed: {exc}") from exc
