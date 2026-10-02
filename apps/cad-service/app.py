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
