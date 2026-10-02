from __future__ import annotations

import io
import tempfile
from pathlib import Path

import cadquery as cq
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

app = FastAPI(title="Teknovashop CAD V2", version="0.1.0")


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
