from utils.geometry import make_box, apply_text
def build(params: dict, text: dict|None):
    return apply_text(make_box(params), text)
