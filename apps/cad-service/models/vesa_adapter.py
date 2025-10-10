from utils.geometry import make_box, apply_text
def build(params: dict, text: dict|None):
    p = {**params, "length_mm": max(params.get("length_mm",100), 100), "width_mm": max(params.get("width_mm",100), 100)}
    return apply_text(make_box(p), text)
