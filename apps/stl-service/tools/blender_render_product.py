from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def args_after_dash():
    if "--" not in sys.argv:
        raise SystemExit("Expected -- <input.stl> <output.png>")
    i = sys.argv.index("--")
    return sys.argv[i + 1:]


def look_at(obj, point):
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def mat_principled(name, base, metallic, roughness):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return m


def add_area(name, location, energy, size, color):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, (0, 0, 0.8))
    return obj


def add_blueprint_lines():
    material = bpy.data.materials.new("BlueprintLine")
    material.diffuse_color = (0.52, 0.86, 1.0, 1.0)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.52, 0.86, 1.0, 1.0)
    bsdf.inputs["Emission"].default_value = (0.20, 0.62, 1.0, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 0.35
    bsdf.inputs["Roughness"].default_value = 0.45

    # Sparse floor guides.
    for x in (-4.0, -2.0, 0.0, 2.0, 4.0):
        bpy.ops.mesh.primitive_cube_add(location=(x, 0.8, 0.012), scale=(0.008, 5.2, 0.008))
        line = bpy.context.object
        line.data.materials.append(material)
    for y in (-2.0, 0.0, 2.0, 4.0):
        bpy.ops.mesh.primitive_cube_add(location=(0, y, 0.012), scale=(5.2, 0.008, 0.008))
        line = bpy.context.object
        line.data.materials.append(material)


def main():
    input_path, output_path = map(Path, args_after_dash()[:2])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 96
    scene.eevee.use_gtao = True
    scene.eevee.gtao_distance = 3
    scene.eevee.gtao_factor = 1.25
    scene.render.resolution_x = 960
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.filepath = str(output_path)
    scene.render.image_settings.color_mode = "RGBA"
    # GitHub's Ubuntu Blender build may expose only the Standard color
    # transform in headless mode. Keep the pipeline portable and apply the
    # final contrast/color polish in Pillow after rendering.
    try:
        if "Filmic" in [item.identifier for item in scene.bl_rna.properties["view_settings"].fixed_type.properties["view_transform"].enum_items]:
            scene.view_settings.view_transform = "Filmic"
        else:
            scene.view_settings.view_transform = "Standard"
    except Exception:
        scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 0.15
    scene.view_settings.gamma = 1.0

    world = scene.world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.17, 0.36, 0.58, 1.0)
    bg.inputs["Strength"].default_value = 0.7

    bpy.ops.import_mesh.stl(filepath=str(input_path))
    product = bpy.context.object
    product.name = input_path.stem

    # Normalize dimensions while preserving exact geometry.
    xs = [v.co.x for v in product.data.vertices]
    ys = [v.co.y for v in product.data.vertices]
    zs = [v.co.z for v in product.data.vertices]
    dims = Vector((max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)))
    max_dim = max(dims.x, dims.y, dims.z, 1e-6)
    scale = 4.8 / max_dim
    product.scale = (scale, scale, scale)

    # Center on XY and place the part on the floor.
    bpy.context.view_layer.update()
    corners = [product.matrix_world @ Vector(c) for c in product.bound_box]
    min_v = Vector((min(p.x for p in corners), min(p.y for p in corners), min(p.z for p in corners)))
    max_v = Vector((max(p.x for p in corners), max(p.y for p in corners), max(p.z for p in corners)))
    center = (min_v + max_v) / 2
    product.location.x -= center.x
    product.location.y -= center.y
    product.location.z -= min_v.z

    # Camera-facing yaw selected by aspect ratio. Long parts keep more top surface visible.
    long_xy = max(dims.x, dims.y)
    short_xy = max(1e-6, min(dims.x, dims.y))
    ratio = long_xy / short_xy
    if ratio > 3.0:
        product.rotation_euler[2] = math.radians(-18)
    elif ratio > 1.8:
        product.rotation_euler[2] = math.radians(-28)
    else:
        product.rotation_euler[2] = math.radians(-36)

    product.data.materials.append(
        mat_principled(
            "GraphiteAnodized",
            (0.025, 0.038, 0.055),
            metallic=0.82,
            roughness=0.20,
        )
    )

    # Slight bevel in shading only; geometry is not changed for STL.
    bevel = product.modifiers.new("StudioBevel", "BEVEL")
    bevel.width = 0.035
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = math.radians(35)

    weighted = product.modifiers.new("WeightedNormals", "WEIGHTED_NORMAL")
    weighted.keep_sharp = True

    # Glossy technical floor.
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    floor = bpy.context.object
    floor.data.materials.append(
        mat_principled("StudioFloor", (0.12, 0.26, 0.38), metallic=0.22, roughness=0.28)
    )

    add_blueprint_lines()

    # Back wall for the bright blue studio look.
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 4.8, 5.0), rotation=(math.radians(90), 0, 0))
    wall = bpy.context.object
    wall.data.materials.append(
        mat_principled("Backdrop", (0.33, 0.62, 0.84), metallic=0.0, roughness=0.52)
    )

    add_area("Key", (-4.8, -4.5, 7.0), 1150, 5.0, (1.0, 0.97, 0.92))
    add_area("Fill", (4.5, -1.2, 4.8), 760, 4.0, (0.58, 0.82, 1.0))
    add_area("Rim", (2.5, 4.0, 6.2), 1050, 3.0, (0.28, 0.70, 1.0))
    add_area("Top", (-0.5, 0.3, 9.0), 650, 3.5, (0.85, 0.94, 1.0))

    # Camera position is based on actual normalized bounds.
    bpy.ops.object.camera_add(location=(7.5, -9.3, 6.1))
    camera = bpy.context.object
    camera.data.lens = 58
    camera.data.sensor_width = 36
    look_at(camera, (0, 0, 1.25))
    scene.camera = camera

    # Soft contact shadow settings.
    for obj in bpy.context.scene.objects:
        if obj.type == "LIGHT":
            obj.data.use_shadow = True
            obj.data.use_contact_shadow = True

    scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
