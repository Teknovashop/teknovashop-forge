from __future__ import annotations

"""
Contratos canónicos de producto para Teknovashop Forge.

Cada producto público debe tener:
- builder canónico
- parámetros por defecto
- una variante que cambie la geometría
- dimensiones mínimas razonables
- nombre comercial preciso

Los tests de CI consumen este fichero. Si se añade un producto al catálogo,
debe añadirse aquí antes de considerarlo publicable.
"""

PRODUCTS = {
    "vesa-adapter": {
        "builder": "vesa_adapter",
        "name": "Adaptador VESA (2 patrones)",
        "default": {
            "pattern_from": 75.0, "pattern_to": 100.0,
            "width": 120.0, "height": 120.0,
            "thickness": 5.0, "hole_d": 5.0, "margin": 10.0,
        },
        "variant": {"pattern_to": 200.0, "width": 220.0, "height": 220.0},
        "min_extents": (100.0, 100.0, 1.5),
    },
    "router-mount": {
        "builder": "router_mount",
        "name": "Soporte de Router",
        "default": {
            "base_w": 140.0, "base_h": 110.0, "depth": 55.0,
            "thickness": 4.0, "hole_d": 4.5, "lip_h": 16.0,
        },
        "variant": {"base_w": 180.0, "depth": 70.0},
        "min_extents": (60.0, 20.0, 40.0),
    },
    "cable-tray": {
        "builder": "cable_tray",
        "name": "Bandeja de Cables",
        "default": {"width": 180.0, "depth": 60.0, "height": 40.0, "wall": 3.0},
        "variant": {"width": 240.0, "depth": 80.0},
        "min_extents": (100.0, 30.0, 20.0),
    },
    "laptop-stand": {
        "builder": "laptop_stand",
        "name": "Soporte Laptop / Tablet",
        "default": {
            "width": 260.0, "depth": 240.0, "angle_deg": 18.0,
            "lip_h": 8.0, "vent_slot": 12.0, "wall": 4.0,
        },
        "variant": {"width": 300.0, "angle_deg": 24.0},
        "min_extents": (150.0, 80.0, 20.0),
    },
    "phone-stand": {
        "builder": "phone_stand",
        "name": "Soporte / Dock Móvil (USB-C)",
        "default": {
            "base_w": 90.0, "base_d": 110.0, "angle_deg": 62.0,
            "slot_w": 12.0, "slot_d": 16.0, "usb_clear_h": 7.0,
            "wall": 4.0, "back_h": 105.0,
        },
        "variant": {"base_w": 105.0, "angle_deg": 70.0, "back_h": 120.0},
        "min_extents": (55.0, 50.0, 50.0),
    },
    "ssd-holder": {
        "builder": "ssd_holder",
        "name": "Caddy SSD 2.5 a 3.5",
        "default": {
            "drive_w": 69.85, "drive_l": 100.0, "bay_w": 101.6,
            "wall": 3.0, "hole_d": 3.2, "tolerance": 0.5,
        },
        "variant": {"tolerance": 1.0, "wall": 4.0},
        "min_extents": (70.0, 80.0, 3.0),
    },
    "raspi-case": {
        "builder": "raspi_case",
        "name": "Caja Raspberry Pi 4 Model B",
        "default": {
            "board_w": 85.0, "board_l": 56.0, "board_h": 17.0,
            "port_clear": 1.0, "wall": 2.2, "bottom": 2.4,
            "lid_t": 2.2, "standoff_h": 4.0,
        },
        "variant": {"port_clear": 1.8, "wall": 3.0, "standoff_h": 5.0},
        "min_extents": (85.0, 56.0, 20.0),
    },
    "go-pro-mount": {
        "builder": "go_pro_mount",
        "name": "Soporte GoPro",
        "default": {
            "fork_pitch": 17.5, "ear_t": 3.2, "hole_d": 5.2,
            "base_w": 30.0, "base_l": 35.0, "wall": 3.0, "finger_h": 18.0,
        },
        "variant": {"base_w": 38.0, "base_l": 42.0, "finger_h": 22.0},
        "min_extents": (20.0, 20.0, 10.0),
    },
    "mic-arm-clip": {
        "builder": "mic_arm_clip",
        "name": "Clip Brazo Mic",
        "default": {"arm_d": 20.0, "opening": 0.6, "clip_t": 3.0, "width": 14.0},
        "variant": {"arm_d": 28.0, "width": 18.0},
        "min_extents": (15.0, 15.0, 8.0),
    },
    "camera-plate": {
        "builder": "camera_plate",
        "name": "Placa para Cámara",
        "default": {
            "width": 45.0, "depth": 50.0, "thickness": 6.0,
            "screw_d": 6.35, "slot_len": 18.0, "chamfer": 0.8,
        },
        "variant": {"width": 55.0, "depth": 65.0, "slot_len": 25.0},
        "min_extents": (35.0, 35.0, 3.0),
    },
    "wall-hook": {
        "builder": "wall_hook",
        "name": "Colgador de Pared",
        "default": {
            "base_w": 40.0, "base_h": 60.0, "hook_depth": 35.0,
            "hook_height": 35.0, "hook_t": 8.0, "hole_d": 4.5, "wall": 3.5,
        },
        "variant": {"hook_depth": 50.0, "hook_height": 45.0},
        "min_extents": (25.0, 20.0, 30.0),
    },
    "wall-bracket": {
        "builder": "wall_bracket",
        "name": "Escuadra de Pared",
        "default": {"length_mm": 120.0, "width_mm": 40.0, "height_mm": 80.0, "thickness_mm": 4.0},
        "variant": {"length_mm": 160.0, "height_mm": 100.0},
        "min_extents": (40.0, 20.0, 30.0),
    },
    "cable-clip": {
        "builder": "cable_clip",
        "name": "Clip de Cable",
        "default": {
            "cable_d": 6.0, "length": 24.0, "gap": 1.0,
            "wall": 2.4, "adhesive_w": 12.0, "adhesive_l": 20.0,
        },
        "variant": {"cable_d": 10.0, "wall": 3.0, "adhesive_l": 28.0},
        "min_extents": (10.0, 10.0, 5.0),
    },
    "hub-holder": {
        "builder": "hub_holder",
        "name": "Soporte Hub USB",
        "default": {"hub_w": 100.0, "hub_h": 28.0, "hub_d": 30.0, "tolerance": 0.5, "wall": 3.0},
        "variant": {"hub_w": 125.0, "hub_h": 35.0},
        "min_extents": (60.0, 15.0, 15.0),
    },
    "headset-stand": {
        "builder": "headset_stand",
        "name": "Soporte Auriculares",
        "default": {
            "base_w": 120.0, "base_d": 120.0, "stem_h": 260.0,
            "stem_w": 30.0, "hook_r": 40.0, "wall": 4.0,
        },
        "variant": {"stem_h": 300.0, "hook_r": 50.0, "base_w": 140.0},
        "min_extents": (50.0, 40.0, 180.0),
    },
    "vesa-shelf": {
        "builder": "vesa_shelf",
        "name": "Bandeja VESA",
        "default": {
            "vesa": 100.0, "thickness": 4.0, "shelf_width": 180.0,
            "shelf_depth": 120.0, "lip_height": 15.0, "rib_count": 3, "hole_d": 5.0,
        },
        "variant": {"shelf_width": 240.0, "shelf_depth": 150.0, "rib_count": 4},
        "min_extents": (100.0, 50.0, 40.0),
    },
    "enclosure-ip65": {
        "builder": "enclosure_ip65",
        "name": "Caja técnica con tapa",
        "default": {
            "length": 120.0, "width": 68.0, "height": 45.0,
            "wall": 3.0, "lid_thickness": 3.0, "lid_gap": 2.0,
        },
        "variant": {"length": 160.0, "width": 90.0, "height": 60.0},
        "min_extents": (50.0, 35.0, 20.0),
    },
    "qr-plate": {
        "builder": "qr_plate",
        "name": "Placa de identificación / Texto",
        "default": {"length": 90.0, "width": 38.0, "thickness": 8.0, "slot_mm": 22.0, "screw_d_mm": 6.5},
        "variant": {"length": 120.0, "width": 50.0, "slot_mm": 32.0},
        "min_extents": (40.0, 20.0, 2.0),
    },
}

DEFAULT_PRODUCT_VERSION = "1.0.0-beta.1"
DEFAULT_PRODUCT_STAGE = "engineering-beta"

for _contract in PRODUCTS.values():
    _contract.setdefault("version", DEFAULT_PRODUCT_VERSION)
    _contract.setdefault("stage", DEFAULT_PRODUCT_STAGE)
    _contract.setdefault(
        "capabilities",
        {
            "text": True,
            "free_holes": False,
        },
    )

# La perforación libre x/y es adicional a los agujeros nativos de estas placas.
PRODUCTS["qr-plate"]["capabilities"]["free_holes"] = True
PRODUCTS["vesa-adapter"]["capabilities"]["free_holes"] = True

CANONICAL_SLUGS = tuple(PRODUCTS.keys())
assert len(CANONICAL_SLUGS) == 18
