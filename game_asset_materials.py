"""Portable varnished-fir texture and UVs for the GIS game export.

Call ``prepare_game_materials()`` after the export builder has converted
curves and applied any geometry modifiers.  It changes the current scene,
never the source .blend on disk.  The resulting PNG is a reusable external
asset suitable for import alongside an FBX into Unreal Engine.
"""

from pathlib import Path
import math

import bpy
import numpy as np


FIR_MATERIAL_NAME = "Clear varnished fir | warm straight grain"
TEXTURE_NAME = "GIS varnished fir base color"
UV_NAME = "GameFirUV"
TEXTURE_FILENAME = "fir_varnished_basecolor.png"


def _save_fir_texture(path, size):
    """Generate a seamless straight-grain color map in scene-linear RGB."""
    if size < 64 or size & (size - 1):
        raise ValueError("texture_size must be a power of two, at least 64")

    # Every sine has an integral cycle count on both axes.  The edge pixels
    # therefore join when the image repeats across longer rails and spars.
    x = np.arange(size, dtype=np.float32)[None, :] / size
    y = np.arange(size, dtype=np.float32)[:, None] / size
    tau = 2.0 * math.pi
    wandering = (
        0.004 * np.sin(tau * (2 * y + 0.19))
        + 0.002 * np.sin(tau * (5 * y + 0.37))
        + 0.001 * np.sin(tau * (9 * y + 3 * x))
    )
    cross_grain = x + wandering
    annual = 0.5 + 0.5 * np.cos(
        tau * (18 * cross_grain + 0.18 * np.sin(tau * 3 * x)
               + 0.08 * np.sin(tau * 3 * y))
    )
    dark_growth_lines = annual ** 15
    fine = np.sin(tau * (47 * cross_grain + 0.11 * np.sin(tau * 4 * y)))
    broad = np.sin(tau * (4 * x + 2 * y))
    pore = np.sin(tau * (83 * cross_grain + 7 * y))
    tone = np.clip(
        0.72 - 0.38 * dark_growth_lines + 0.065 * fine
        + 0.055 * broad + 0.015 * pore,
        0.18, 0.92,
    )

    dark = np.array((0.50, 0.30, 0.15), dtype=np.float32)
    light = np.array((0.82, 0.63, 0.38), dtype=np.float32)
    rgba = np.empty((size, size, 4), dtype=np.float32)
    rgba[:, :, :3] = dark + tone[:, :, None] * (light - dark)
    rgba[:, :, 3] = 1.0

    image = bpy.data.images.get(TEXTURE_NAME)
    if image is not None and tuple(image.size) != (size, size):
        bpy.data.images.remove(image)
        image = None
    if image is None:
        image = bpy.data.images.new(TEXTURE_NAME, width=size, height=size,
                                    alpha=True)
    image.colorspace_settings.name = "sRGB"
    image.file_format = "PNG"
    image.filepath_raw = str(path)
    image.pixels.foreach_set(rgba.ravel())
    image.save()
    image.filepath = str(path)
    return image


def _physical_local_vertex(obj, vertex):
    """Local axes including object scale but excluding orientation in world."""
    scale = obj.scale
    co = vertex.co
    return (co.x * scale.x, co.y * scale.y, co.z * scale.z)


def _uv_fir_mesh(obj):
    mesh = obj.data
    if mesh.users > 1:
        # Shared geometry can be placed at different physical sizes.
        obj.data = mesh.copy()
        mesh = obj.data

    vertices = [_physical_local_vertex(obj, v) for v in mesh.vertices]
    if not vertices:
        return False
    spans = [max(p[i] for p in vertices) - min(p[i] for p in vertices)
             for i in range(3)]
    long_axis = max(range(3), key=lambda i: spans[i])

    uv = mesh.uv_layers.get(UV_NAME) or mesh.uv_layers.new(name=UV_NAME)
    mesh.uv_layers.active = uv
    mesh.uv_layers.active_index = list(mesh.uv_layers).index(uv)

    for poly in mesh.polygons:
        polygon_points = [vertices[mesh.loops[i].vertex_index]
                          for i in poly.loop_indices]
        face_spans = [max(p[i] for p in polygon_points)
                      - min(p[i] for p in polygon_points)
                      for i in range(3)]
        if face_spans[long_axis] > 1e-6:
            # Most faces put the long board/spar direction on V.
            v_axis = long_axis
            u_axis = max((i for i in range(3) if i != v_axis),
                         key=lambda i: face_spans[i])
        else:
            # End grain gets a planar map instead of collapsed UVs.
            cross_axes = sorted((i for i in range(3) if i != long_axis),
                                key=lambda i: face_spans[i], reverse=True)
            u_axis, v_axis = cross_axes
        for loop_index in poly.loop_indices:
            p = vertices[mesh.loops[loop_index].vertex_index]
            uv.data[loop_index].uv = (p[u_axis] / 0.23, p[v_axis] / 1.7)
    return True


def prepare_game_materials(output_dir=None, texture_size=1024):
    """Texture the existing fir material and UV every mesh that uses it.

    Returns a small manifest with the PNG path and mapped-object count.
    Curves must be converted to meshes by the caller before this pass.
    Other paints, sailcloth, rope and metal materials are left intact.
    """
    output_dir = (Path(output_dir) if output_dir is not None
                  else Path(__file__).resolve().parent / "game_asset")
    output_dir.mkdir(parents=True, exist_ok=True)
    texture_path = (output_dir / TEXTURE_FILENAME).resolve()

    fir = bpy.data.materials.get(FIR_MATERIAL_NAME)
    if fir is None:
        raise RuntimeError(f"Missing source fir material: {FIR_MATERIAL_NAME}")

    image = _save_fir_texture(texture_path, int(texture_size))
    fir.use_nodes = True
    nodes = fir.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    output = next((n for n in nodes if n.type == "OUTPUT_MATERIAL"), None)
    if bsdf is None or output is None:
        raise RuntimeError("Fir material needs Principled BSDF and Material Output")
    for node in tuple(nodes):
        if node not in (bsdf, output):
            nodes.remove(node)
    links = fir.node_tree.links
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    uv_node = nodes.new("ShaderNodeUVMap")
    uv_node.name = "Game Fir UV"
    uv_node.uv_map = UV_NAME
    uv_node.location = (-540, 0)
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.name = "Game Fir Base Color"
    image_node.image = image
    image_node.extension = "REPEAT"
    image_node.interpolation = "Linear"
    image_node.location = (-300, 0)
    bsdf.location = (-30, 0)
    output.location = (300, 0)
    links.new(uv_node.outputs["UV"], image_node.inputs["Vector"])
    links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Roughness"].default_value = 0.35
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 0.31
        bsdf.inputs["Coat Roughness"].default_value = 0.19
    fir.diffuse_color = (0.52, 0.30, 0.13, 1.0)
    fir["game_asset_texture"] = TEXTURE_FILENAME

    mapped = 0
    non_mesh = []
    for obj in bpy.data.objects:
        if not any(slot.material == fir for slot in obj.material_slots):
            continue
        if obj.type == "MESH":
            mapped += bool(_uv_fir_mesh(obj))
        else:
            non_mesh.append(obj.name)
    return {
        "texture": str(texture_path),
        "fir_meshes_uv_mapped": mapped,
        "fir_non_mesh_objects": non_mesh,
    }
