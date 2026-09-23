# Teknovashop Forge — Model Geometry Audit

Date: 2026-09-23

Purpose: ensure every public model name corresponds to recognizable, parameterizable geometry. A model is not accepted merely because it exports an STL.

## Status legend

- ✅ **Semantically credible** — geometry broadly matches the public name and can be refined.
- ⚠️ **Partial / simplified** — recognizable base concept, but missing essential functional details.
- ❌ **Incorrect placeholder** — current geometry does not justify the public name and must be redesigned before production.

## Canonical catalog audit

| Slug | Public name | Status | Current geometry | Required action |
|---|---|---:|---|---|
| vesa-adapter | Adaptador VESA (2 patrones) | ✅ | Plate with two configurable square VESA mounting patterns | Keep; validate supported pattern combinations and clearances |
| router-mount | Soporte de Router | ✅ | Wall cradle with back plate, shelf, retainers and fixing holes | Keep; validate router size ranges and load behaviour |
| cable-tray | Bandeja de Cables | ✅ | U-shaped tray: base + two side walls, optional ventilation | Keep; validate dimensions and improve ventilation slots |
| laptop-stand | Soporte Laptop / Tablet | ✅ | Two triangular ribs, upper support, front lip and rear base | Keep; validate stability and parameter ranges |
| phone-stand | Soporte / Dock Móvil (USB-C) | ✅ | Angled stand with backrest, ledge and cable clearance | Keep; validate phone thickness and USB-C clearance ranges |
| ssd-holder | Caddy SSD 2.5 a 3.5 | ✅ | Base with side rails and front/rear retention | Keep; add real 2.5"/3.5" screw patterns later |
| raspi-case | Caja Raspberry Pi 4 Model B | ✅ | Ventilated enclosure with lid, Pi 4 mounting bosses and connector windows | Keep; physical-fit validation against real board still required |
| go-pro-mount | Soporte GoPro | ✅ | Three-finger fork-style mount with transverse bolt passage | Keep; validate interchangeability against real GoPro hardware |
| mic-arm-clip | Clip Brazo Mic | ✅ | Split cylindrical ring clip | Keep; validate opening and grip tolerances |
| camera-plate | Placa para Cámara | ✅ | Plate with 1/4" hole and elongated adjustment slot | Keep; refine anti-twist / edge options later |
| wall-hook | Colgador de Pared | ✅ | Base plate plus L-shaped projecting hook and fixing holes | Keep; validate orientation and strength parameters |
| wall-bracket | Escuadra de Pared | ✅ | L-shaped horizontal + vertical bracket | Keep; add screw holes / optional gusset |
| cable-clip | Clip de Cable | ✅ | Open snap-style ring with adhesive base | Keep; validate material-flex ranges by cable diameter |
| hub-holder | Soporte Hub USB | ✅ | Open-top holder formed by outer/inner subtraction | Keep; add cable exits and retention options |
| headset-stand | Soporte Auriculares | ✅ | Base, mast and top yoke | Keep; refine yoke curvature and stability |
| vesa-shelf | Bandeja VESA | ✅ | VESA back plate + horizontal shelf + front lip + ribs | Keep; validate hole patterns and shelf load geometry |
| enclosure-ip65 | Caja técnica con tapa | ✅ | Hollow enclosure with separate lid and centring lip | Keep; do not claim any IP rating without physical validation |
| qr-plate | Placa de identificación / Texto | ✅ | Parametric identification plate with mounting holes; text can be added through Forge text tools | Keep under accurate name; QR generation can be added later as a separate feature |

## Immediate conclusions

### Current semantic status

All 18 canonical public models now have geometry that broadly matches their public name.

Remaining physical-validation items:

1. Raspberry Pi 4 case: verify connector openings and mounting fit against a real board.
2. GoPro mount: verify fork spacing and bolt fit against real hardware.
3. Cable clip: validate flex/snap behaviour for real print materials and cable diameters.
4. Technical enclosure: no IP rating is claimed until physical testing is performed.
5. QR generation is not currently claimed; the model is published as an identification/text plate.

## Acceptance criteria for every production model

A model is production-ready only when all of these are true:

1. The default geometry is immediately recognizable as the advertised object.
2. Every exposed UI parameter has a measurable geometric effect.
3. Parameter ranges cannot create degenerate or impossible geometry.
4. The generated mesh is non-empty and exportable as STL.
5. Target dimensions match requested dimensions within modelling tolerance.
6. Required openings, mounting holes, clearances and interfaces exist.
7. The catalogue thumbnail is generated from the actual default geometry, not a placeholder image.
8. A regression test exists for default generation and at least one changed-parameter case.

## Thumbnail policy

Catalogue images must be generated from the same canonical model builders used by the configurator. Broken or manually unrelated thumbnails should not be considered authoritative.
