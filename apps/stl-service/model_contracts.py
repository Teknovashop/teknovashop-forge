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
    "vertical-laptop-dock": {
        "builder": "vertical_laptop_dock",
        "name": "Dock vertical para portátil",
        "default": {"length": 180.0, "depth": 90.0, "wall": 4.0, "slot": 24.0, "height": 65.0},
        "variant": {"length": 220.0, "slot": 32.0, "height": 78.0},
        "min_extents": (140.0, 65.0, 50.0),
    },
    "universal-mount-plate": {
        "builder": "universal_mount_plate",
        "name": "Placa universal de montaje",
        "default": {"width": 120.0, "height": 90.0, "thickness": 5.0, "rail": 10.0},
        "variant": {"width": 160.0, "height": 110.0, "rail": 14.0},
        "min_extents": (80.0, 60.0, 4.0),
    },
    "mini-pc-mount": {
        "builder": "mini_pc_mount",
        "name": "Soporte mini-PC / NUC",
        "default": {"width": 130.0, "depth": 125.0, "height": 45.0, "wall": 4.0, "lip": 16.0},
        "variant": {"width": 155.0, "depth": 145.0, "height": 55.0},
        "min_extents": (90.0, 80.0, 30.0),
    },
    "desk-grommet": {
        "builder": "desk_grommet",
        "name": "Pasacables de mesa",
        "default": {"outer_d": 65.0, "inner_d": 50.0, "height": 18.0, "flange": 4.0},
        "variant": {"outer_d": 75.0, "inner_d": 56.0, "height": 22.0},
        "min_extents": (50.0, 50.0, 12.0),
    },
    "under-desk-channel": {
        "builder": "under_desk_channel",
        "name": "Canal bajo mesa",
        "default": {"length": 240.0, "width": 55.0, "height": 35.0, "wall": 3.0},
        "variant": {"length": 320.0, "width": 70.0, "height": 45.0},
        "min_extents": (160.0, 35.0, 22.0),
    },
    "multi-device-dock": {
        "builder": "multi_device_dock",
        "name": "Peana multi-dispositivo",
        "default": {"width": 190.0, "depth": 105.0, "height": 55.0, "wall": 4.0, "slots": 3},
        "variant": {"width": 230.0, "height": 65.0, "slots": 4},
        "min_extents": (130.0, 70.0, 40.0),
    },
    "webcam-monitor-mount": {
        "builder": "webcam_monitor_mount",
        "name": "Soporte webcam de monitor",
        "default": {"width": 55.0, "depth": 45.0, "back": 35.0, "wall": 4.0, "angle_deg": 10.0},
        "variant": {"width": 70.0, "depth": 55.0, "angle_deg": 18.0},
        "min_extents": (35.0, 25.0, 20.0),
    },
    "network-switch-mount": {
        "builder": "network_switch_mount",
        "name": "Soporte switch de red",
        "default": {"width": 180.0, "depth": 95.0, "height": 42.0, "wall": 4.0, "front_lip": 12.0},
        "variant": {"width": 220.0, "depth": 115.0, "height": 50.0},
        "min_extents": (120.0, 65.0, 28.0),
    },
    "electronics-box": {
        "builder": "electronics_box",
        "name": "Caja electrónica ventilable universal",
        "default": {"length": 130.0, "width": 85.0, "height": 45.0, "wall": 3.0, "lid": 3.0},
        "variant": {"length": 165.0, "width": 105.0, "height": 60.0},
        "min_extents": (80.0, 50.0, 28.0),
    },
    "controller-stand": {
        "builder": "controller_stand",
        "name": "Soporte de mando",
        "default": {"width": 95.0, "depth": 110.0, "height": 85.0, "wall": 5.0, "angle_deg": 28.0},
        "variant": {"width": 110.0, "depth": 125.0, "height": 100.0, "angle_deg": 34.0},
        "min_extents": (60.0, 65.0, 55.0),
    },
    "drill-template": {
        "builder": "drill_template",
        "name": "Plantilla de perforación",
        "default": {"length": 160.0, "width": 45.0, "thickness": 6.0, "hole_d": 5.0, "spacing": 32.0},
        "variant": {"length": 210.0, "width": 55.0, "spacing": 40.0},
        "min_extents": (100.0, 28.0, 4.0),
    },
    "drawer-divider": {
        "builder": "drawer_divider",
        "name": "Divisor de cajón",
        "default": {"length": 220.0, "height": 55.0, "thickness": 3.0, "foot": 14.0},
        "variant": {"length": 280.0, "height": 70.0, "foot": 18.0},
        "min_extents": (150.0, 8.0, 35.0),
    },
    "vesa-offset-adapter": {
        "builder": "vesa_offset_adapter", "name": "Adaptador VESA offset",
        "default": {"width": 150.0, "height": 120.0, "thickness": 5.0, "offset": 35.0},
        "variant": {"width": 180.0, "offset": 55.0}, "min_extents": (120.0, 90.0, 4.0),
    },
    "under-desk-mount": {
        "builder": "under_desk_mount", "name": "Montura bajo mesa universal",
        "default": {"width": 130.0, "depth": 90.0, "height": 55.0, "wall": 4.0},
        "variant": {"width": 170.0, "depth": 115.0}, "min_extents": (90.0, 60.0, 35.0),
    },
    "perforated-mount-plate": {
        "builder": "perforated_mount_plate", "name": "Placa técnica configurable",
        "default": {"width": 150.0, "height": 100.0, "thickness": 5.0, "boss": 12.0},
        "variant": {"width": 190.0, "boss": 18.0}, "min_extents": (100.0, 70.0, 4.0),
    },
    "circular-pattern-adapter": {
        "builder": "circular_pattern_adapter", "name": "Adaptador de patrón circular",
        "default": {"outer_d": 100.0, "hub_d": 36.0, "thickness": 6.0, "boss_h": 8.0},
        "variant": {"outer_d": 125.0, "hub_d": 46.0}, "min_extents": (70.0, 70.0, 10.0),
    },
    "phone-landscape-stand": {
        "builder": "phone_landscape_stand", "name": "Soporte móvil horizontal / vertical",
        "default": {"width": 150.0, "depth": 85.0, "back_h": 70.0, "wall": 4.0, "lip": 12.0},
        "variant": {"width": 180.0, "back_h": 85.0}, "min_extents": (100.0, 55.0, 45.0),
    },
    "smartwatch-stand": {
        "builder": "smartwatch_stand", "name": "Base para reloj inteligente",
        "default": {"base_d": 80.0, "stem_h": 95.0, "stem_d": 18.0, "cradle_d": 48.0},
        "variant": {"base_d": 95.0, "stem_h": 115.0}, "min_extents": (45.0, 45.0, 80.0),
    },
    "cable-comb": {
        "builder": "cable_comb", "name": "Peine de cables",
        "default": {"length": 90.0, "width": 22.0, "height": 14.0, "teeth": 6},
        "variant": {"length": 120.0, "teeth": 8}, "min_extents": (60.0, 15.0, 10.0),
    },
    "charger-retainer": {
        "builder": "charger_retainer", "name": "Retenedor de cargador",
        "default": {"width": 70.0, "depth": 45.0, "height": 28.0, "wall": 3.0},
        "variant": {"width": 90.0, "depth": 55.0}, "min_extents": (45.0, 30.0, 18.0),
    },
    "zip-tie-anchor": {
        "builder": "zip_tie_anchor", "name": "Anclaje para brida reutilizable",
        "default": {"length": 32.0, "width": 22.0, "height": 9.0, "bridge": 8.0},
        "variant": {"length": 42.0, "bridge": 12.0}, "min_extents": (22.0, 15.0, 8.0),
    },
    "nvme-caddy": {
        "builder": "nvme_caddy", "name": "Caddy SSD / NVMe externo",
        "default": {"length": 115.0, "width": 38.0, "height": 18.0, "wall": 3.0},
        "variant": {"length": 135.0, "width": 46.0}, "min_extents": (75.0, 25.0, 12.0),
    },
    "power-supply-mount": {
        "builder": "power_supply_mount", "name": "Soporte fuente de alimentación",
        "default": {"width": 115.0, "depth": 55.0, "height": 40.0, "wall": 4.0, "strap": 16.0},
        "variant": {"width": 145.0, "height": 52.0}, "min_extents": (80.0, 35.0, 28.0),
    },
    "cold-shoe-adapter": {
        "builder": "cold_shoe_adapter", "name": "Adaptador cold-shoe",
        "default": {"length": 30.0, "width": 22.0, "base_t": 4.0, "post_h": 12.0},
        "variant": {"length": 36.0, "post_h": 16.0}, "min_extents": (20.0, 14.0, 14.0),
    },
    "led-light-mount": {
        "builder": "led_light_mount", "name": "Soporte de luz LED",
        "default": {"width": 65.0, "depth": 48.0, "height": 45.0, "wall": 4.0, "tilt_deg": 15.0},
        "variant": {"width": 80.0, "height": 58.0, "tilt_deg": 25.0}, "min_extents": (40.0, 28.0, 30.0),
    },
    "audio-interface-mount": {
        "builder": "audio_interface_mount", "name": "Montura para interfaz de audio",
        "default": {"width": 165.0, "depth": 115.0, "height": 35.0, "wall": 4.0},
        "variant": {"width": 205.0, "depth": 135.0}, "min_extents": (110.0, 75.0, 24.0),
    },
    "battery-card-holder": {
        "builder": "battery_card_holder", "name": "Organizador de baterías y tarjetas",
        "default": {"width": 120.0, "depth": 65.0, "height": 32.0, "bays": 4},
        "variant": {"width": 155.0, "bays": 6}, "min_extents": (80.0, 42.0, 22.0),
    },
    "double-wall-hook": {
        "builder": "double_wall_hook", "name": "Gancho doble de pared",
        "default": {"base_w": 75.0, "base_h": 60.0, "hook_d": 35.0, "hook_t": 8.0},
        "variant": {"base_w": 95.0, "hook_d": 48.0}, "min_extents": (50.0, 25.0, 40.0),
    },
    "compact-wall-shelf": {
        "builder": "compact_wall_shelf", "name": "Estante mural compacto",
        "default": {"width": 180.0, "depth": 110.0, "back_h": 65.0, "wall": 4.0},
        "variant": {"width": 230.0, "depth": 140.0}, "min_extents": (120.0, 75.0, 45.0),
    },
    "tool-holder": {
        "builder": "tool_holder", "name": "Soporte modular de herramienta",
        "default": {"width": 160.0, "height": 60.0, "depth": 48.0, "slots": 5},
        "variant": {"width": 210.0, "slots": 7}, "min_extents": (105.0, 30.0, 40.0),
    },
    "vesa-shelf-adapter": {"builder":"vesa_shelf_adapter","name":"Adaptador VESA a bandeja","default":{"width":180.0,"height":120.0,"depth":65.0,"thickness":5.0},"variant":{"width":220.0,"depth":85.0},"min_extents":(120.0,60.0,20.0)},
    "universal-wall-mount": {"builder":"universal_wall_mount","name":"Montura mural universal","default":{"width":130.0,"height":90.0,"depth":55.0,"wall":4.0},"variant":{"width":165.0,"depth":75.0},"min_extents":(90.0,45.0,50.0)},
    "multipattern-transition-plate": {"builder":"multipattern_transition_plate","name":"Placa de transición multipatrón","default":{"width":180.0,"height":140.0,"thickness":5.0,"bridge":24.0},"variant":{"width":220.0,"bridge":32.0},"min_extents":(130.0,100.0,4.0)},
    "monitor-riser": {"builder":"monitor_riser","name":"Elevador de monitor compacto","default":{"width":420.0,"depth":210.0,"height":85.0,"wall":5.0},"variant":{"width":480.0,"height":105.0},"min_extents":(320.0,150.0,60.0)},
    "tablet-angle-stand": {"builder":"tablet_angle_stand","name":"Soporte tablet de ángulo configurable","default":{"width":170.0,"depth":145.0,"back_h":125.0,"wall":4.0,"angle_deg":62.0},"variant":{"width":205.0,"angle_deg":70.0},"min_extents":(120.0,80.0,70.0)},
    "microphone-desk-adapter": {"builder":"microphone_desk_adapter","name":"Adaptador de micrófono a escritorio","default":{"base_d":72.0,"stem_h":55.0,"stem_d":22.0,"collar_d":34.0},"variant":{"base_d":86.0,"stem_h":72.0},"min_extents":(45.0,45.0,55.0)},
    "broom-tool-holder": {"builder":"broom_tool_holder","name":"Soporte de escoba / herramienta","default":{"width":140.0,"height":60.0,"depth":48.0,"grips":3},"variant":{"width":180.0,"grips":4},"min_extents":(100.0,35.0,45.0)},
    "controller-wall-mount": {"builder":"controller_wall_mount","name":"Soporte de mando mural","default":{"width":100.0,"back_h":85.0,"arm_depth":75.0,"wall":5.0},"variant":{"width":120.0,"arm_depth":90.0},"min_extents":(70.0,55.0,55.0)},
    "speaker-wall-mount": {"builder":"speaker_wall_mount","name":"Soporte de altavoz mural","default":{"width":120.0,"depth":115.0,"back_h":95.0,"wall":5.0},"variant":{"width":150.0,"depth":140.0},"min_extents":(90.0,80.0,65.0)},
    "wall-cable-clip": {"builder":"wall_cable_clip","name":"Clip mural de cable","default":{"length":36.0,"width":22.0,"height":18.0,"gap":8.0},"variant":{"length":48.0,"gap":12.0},"min_extents":(25.0,15.0,14.0)},
    "light-clamp-block": {"builder":"light_clamp_block","name":"Bloc de sujeción ligera","default":{"length":70.0,"width":45.0,"height":28.0,"jaw":12.0},"variant":{"length":90.0,"jaw":16.0},"min_extents":(50.0,30.0,25.0)},
    "cutting-guide": {"builder":"cutting_guide","name":"Guía de corte","default":{"length":240.0,"width":55.0,"height":28.0,"fence":8.0},"variant":{"length":320.0,"height":36.0},"min_extents":(180.0,40.0,20.0)},
    "parametric-spacer": {"builder":"parametric_spacer","name":"Separador / calzo paramétrico","default":{"length":70.0,"width":45.0,"thickness":8.0,"step":4.0},"variant":{"length":95.0,"thickness":12.0},"min_extents":(45.0,30.0,7.0)},
    "bit-key-organizer": {"builder":"bit_key_organizer","name":"Organizador de brocas / llaves","default":{"width":160.0,"depth":65.0,"height":25.0,"bays":8},"variant":{"width":210.0,"bays":10},"min_extents":(110.0,45.0,20.0)},
    "parametric-lidded-box": {"builder":"parametric_lidded_box","name":"Caja paramétrica con tapa","default":{"length":150.0,"width":95.0,"height":55.0,"wall":3.0,"lid":3.0},"variant":{"length":190.0,"height":70.0},"min_extents":(100.0,65.0,40.0)},
    "stackable-box": {"builder":"stackable_box","name":"Caja apilable","default":{"length":140.0,"width":90.0,"height":60.0,"wall":3.0,"rim":6.0},"variant":{"length":180.0,"height":75.0},"min_extents":(95.0,60.0,45.0)},
    "modular-tray": {"builder":"modular_tray","name":"Bandeja modular","default":{"length":180.0,"width":120.0,"height":28.0,"wall":3.0,"divider":4.0},"variant":{"length":230.0,"height":36.0},"min_extents":(125.0,80.0,22.0)},
    "desk-organizer": {"builder":"desk_organizer","name":"Organizador de escritorio","default":{"width":180.0,"depth":100.0,"height":75.0,"bays":4},"variant":{"width":230.0,"bays":5},"min_extents":(125.0,70.0,55.0)},
    "modular-pen-holder": {"builder":"modular_pen_holder","name":"Portabolígrafos modular","default":{"outer_d":85.0,"height":105.0,"wall":4.0,"cells":3},"variant":{"outer_d":105.0,"cells":4},"min_extents":(55.0,55.0,80.0)},
    "hardware-box": {"builder":"hardware_box","name":"Caja para tornillería","default":{"length":190.0,"width":125.0,"height":45.0,"cells":6},"variant":{"length":240.0,"cells":8},"min_extents":(130.0,85.0,35.0)},
    "accessory-rack": {"builder":"accessory_rack","name":"Rack pequeño de accesorios","default":{"width":220.0,"depth":80.0,"height":110.0,"levels":3},"variant":{"width":270.0,"levels":4},"min_extents":(150.0,55.0,80.0)},
    "inset-label": {"builder":"inset_label","name":"Etiqueta / placa encastrable","default":{"length":90.0,"width":32.0,"thickness":4.0,"tab":12.0},"variant":{"length":120.0,"tab":18.0},"min_extents":(60.0,22.0,3.0)},
    "sd-card-organizer": {"builder":"sd_card_organizer","name":"Organizador de tarjetas SD","default":{"width":120.0,"depth":70.0,"height":28.0,"slots":8},"variant":{"width":160.0,"slots":12},"min_extents":(80.0,48.0,22.0)},
    "cable-reel": {"builder":"cable_reel","name":"Carrete organizador de cable","default":{"outer_d":95.0,"core_d":35.0,"width":38.0,"flange":4.0},"variant":{"outer_d":120.0,"width":48.0},"min_extents":(65.0,65.0,28.0)},
}

DEFAULT_PRODUCT_VERSION = "1.0.0-beta.1"
DEFAULT_PRODUCT_STAGE = "engineering"

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

# Release state is canonical commercial metadata, not a frontend concern.
# The 18 curated Studio products are production; the remaining products stay
# engineering until geometry + visual QA promotes them explicitly.
try:
    from product_catalog import PRODUCT_METADATA
    for _slug, _metadata in PRODUCT_METADATA.items():
        if _slug not in PRODUCTS:
            continue
        PRODUCTS[_slug]["stage"] = _metadata.get("stage", DEFAULT_PRODUCT_STAGE)
        if PRODUCTS[_slug]["stage"] == "production":
            PRODUCTS[_slug]["version"] = "1.0.0"
except Exception:
    PRODUCT_METADATA = {}

# La perforación libre x/y es adicional a los agujeros nativos de estas placas.
PRODUCTS["qr-plate"]["capabilities"]["free_holes"] = True
PRODUCTS["vesa-adapter"]["capabilities"]["free_holes"] = True
PRODUCTS["cable-clip"]["capabilities"]["free_holes"] = True
PRODUCTS["cable-tray"]["capabilities"]["free_holes"] = True

CANONICAL_SLUGS = tuple(PRODUCTS.keys())
assert len(CANONICAL_SLUGS) == 72
