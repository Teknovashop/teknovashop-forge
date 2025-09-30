# apps/stl-service/models/_booleans.py
import trimesh

try:
    import manifold3d as m3d
    HAS_MANIFOLD = True
except Exception:
    HAS_MANIFOLD = False


def _mesh_to_manifold(mesh: trimesh.Trimesh):
    v = mesh.vertices.astype("float64")
    f = mesh.faces.astype("int32")
    return m3d.Manifold(v, f)


def _manifold_to_mesh(mani: "m3d.Manifold") -> trimesh.Trimesh:
    v, f = mani.to_tri_mesh()
    return trimesh.Trimesh(vertices=v, faces=f, process=True)


def boolean_diff(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    """
    Diferencia booleana robusta. Usa manifold3d si está disponible; si no, intenta con trimesh.
    """
    if HAS_MANIFOLD:
        try:
            ma = _mesh_to_manifold(a)
            mb = _mesh_to_manifold(b)
            mc = ma - mb
            return _manifold_to_mesh(mc)
        except Exception as e:
            print(f"[WARN] manifold3d diff fallback: {e}")

    # Fallback trimesh (engine auto): puede no estar en contenedor, por eso mantenemos manifold.
    try:
        return a.difference(b)
    except Exception as e:
        print(f"[WARN] trimesh difference falló: {e}")
        # último recurso: devuelve el original sin taladro
        return a


def boolean_union(a: trimesh.Trimesh, b: trimesh.Trimesh) -> trimesh.Trimesh:
    if HAS_MANIFOLD:
        try:
            ma = _mesh_to_manifold(a)
            mb = _mesh_to_manifold(b)
            mc = ma + mb
            return _manifold_to_mesh(mc)
        except Exception as e:
            print(f"[WARN] manifold3d union fallback: {e}")
    try:
        return a.union(b)
    except Exception as e:
        print(f"[WARN] trimesh union falló: {e}")
        return a
