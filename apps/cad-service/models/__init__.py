from . import cable_tray, vesa_adapter, router_mount

REGISTRY = {
  "cable_tray": cable_tray.build,
  "vesa_adapter": vesa_adapter.build,
  "router_mount": router_mount.build,
}
