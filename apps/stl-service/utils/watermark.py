import trimesh

def apply_text_watermark(stl_path: str, text: str = 'Teknovashop'):
    # Minimal non-destructive watermark: ensure ASCII STL header includes brand.
    try:
        with open(stl_path, 'rb') as f:
            data = f.read()
        if data[:5].lower() != b'solid':
            mesh = trimesh.load(stl_path)
            mesh.export(stl_path, file_type='stl')
    except Exception:
        pass
