from utils.geometry import make_box, apply_text

def build(params: dict, text: dict|None):
    part = make_box(params)
    part = apply_text(part, text)
    return part
