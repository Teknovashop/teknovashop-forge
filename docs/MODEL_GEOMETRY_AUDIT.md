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
| vesa-adapter | Adaptador VESA 75/100 → 100/200 | ❌ | Single square plate with one 4-hole VESA pattern | Implement two distinct mounting patterns (source + target), correct plate envelope and non-overlapping holes |
| router-mount | Soporte de Router | ❌ | Flat rectangular plate | Build cradle/wall mount with bottom support, side retainers and mounting slots/holes |
| cable-tray | Bandeja de Cables | ✅ | U-shaped tray: base + two side walls, optional ventilation | Keep; validate dimensions and improve ventilation slots |
| laptop-stand | Soporte Laptop / Tablet | ✅ | Two triangular ribs, upper support, front lip and rear base | Keep; validate stability and parameter ranges |
| phone-stand | Soporte / Dock Móvil (USB-C) | ❌ | Plain rectangular block; angle is explicitly not implemented | Build real angled backrest, phone ledge and USB-C/cable clearance |
| ssd-holder | Caddy SSD 2.5 a 3.5 | ✅ | Base with side rails and front/rear retention | Keep; add real 2.5"/3.5" screw patterns later |
| raspi-case | Caja Raspberry Pi | ⚠️ | Hollow rectangular enclosure when boolean succeeds | Add lid, board standoffs and connector/vent cut-outs; define Pi variant |
| go-pro-mount | Soporte GoPro | ❌ | Rectangular block with one transverse hole | Implement standard fork/finger interface and bolt passage |
| mic-arm-clip | Clip Brazo Mic | ✅ | Split cylindrical ring clip | Keep; validate opening and grip tolerances |
| camera-plate | Placa para Cámara | ✅ | Plate with 1/4" hole and elongated adjustment slot | Keep; refine anti-twist / edge options later |
| wall-hook | Colgador de Pared | ✅ | Base plate plus L-shaped projecting hook and fixing holes | Keep; validate orientation and strength parameters |
| wall-bracket | Escuadra de Pared | ✅ | L-shaped horizontal + vertical bracket | Keep; add screw holes / optional gusset |
| cable-clip | Clip de Cable | ❌ | Flat plate with central through-hole | Implement open/snap cable clip geometry around cable diameter |
| hub-holder | Soporte Hub USB | ✅ | Open-top holder formed by outer/inner subtraction | Keep; add cable exits and retention options |
| headset-stand | Soporte Auriculares | ✅ | Base, mast and top yoke | Keep; refine yoke curvature and stability |
| vesa-shelf | Bandeja VESA | ✅ | VESA back plate + horizontal shelf + front lip + ribs | Keep; validate hole patterns and shelf load geometry |
| enclosure-ip65 | Caja IP65 | ❌ | Solid rectangular block | Implement hollow enclosure + lid + gasket groove + screw bosses; do not claim IP65 until physically validated |
| qr-plate | Placa (QR/Texto) | ⚠️ | Parametric plate with mounting holes; no QR geometry is generated | Either implement real QR relief/engraving or rename to identification/text plate |

## Immediate conclusions

### Models that should not be presented as finished until redesigned

1. vesa-adapter
2. router-mount
3. phone-stand
4. go-pro-mount
5. cable-clip
6. enclosure-ip65

### Models that need completion or more precise naming

1. raspi-case
2. qr-plate

### Models suitable for the next validation stage

1. cable-tray
2. laptop-stand
3. ssd-holder
4. mic-arm-clip
5. camera-plate
6. wall-hook
7. wall-bracket
8. hub-holder
9. headset-stand
10. vesa-shelf

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
