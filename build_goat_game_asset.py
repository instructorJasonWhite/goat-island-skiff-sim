"""Create a compact, movable Unreal asset from the finished GIS visual model.

Run with Blender in background mode. The presentation .blend is read only;
this script saves a separate game source and exports its FBX files.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from game_asset_materials import prepare_game_materials
from game_asset_export import export_unreal_asset


SOURCE = HERE / "Goat_Island_Skiff.blend"
OUT = HERE / "game_asset"
OUT.mkdir(exist_ok=True)

ALLOWED_COLLECTIONS = {
    "01 Hull, cockpit and appendages",
    "01a Sliding rudder and shock cord",
    "02 Balanced lug rig",
}
FIR = "Clear varnished fir | warm straight grain"
GROUP_NAMES = {
    "static": "Hull_and_Fixed_Mast",
    "stock": "Rudder_Stock_and_Tiller",
    "blade": "Rudder_Sliding_Blade",
    "board": "Sliding_Centerboard",
    "boom": "Boom_and_Fittings",
    "yard": "Yard_and_Lacings",
    "sail": "Sail_Cloth",
}
DEFORM_BONE = {
    "static": "Root",
    "stock": "RudderYaw",
    "blade": "RudderBladeSlide",
    "board": "CenterboardSlide",
    "boom": "SailSwing",
    "yard": "SailHoist",
    "sail": "SailSwing",
}


def _kind(obj):
    name = obj.name
    collections = {col.name for col in obj.users_collection}
    if "01 Hull, cockpit and appendages" in collections:
        if "sliding 1265 mm centreboard" in name or "centreboard knotted" in name or "centreboard rope hole" in name:
            return "board"
        return "static"
    if "01a Sliding rudder and shock cord" in collections:
        if obj.parent and "move to lift" in obj.parent.name:
            return "blade"
        if "transom backing plate" in name:
            return "static"
        return "stock"
    if "02 Balanced lug rig" in collections:
        if name in {"Halyard to yard", "Downhaul", "Mainsheet upper fall"}:
            return "omit"
        if name.startswith("Mast ") or name in {
            "Halyard down mast", "Downhaul deck eye", "Mainsheet working fall",
            "Stern traveller", "Mainsheet stern block",
        }:
            return "static"
        if name.startswith("Boom ") or name.startswith("Boom lacing") or name in {
            "Boom tack band", "Mainsheet boom block",
        }:
            return "boom"
        if name.startswith("Yard ") or name.startswith("Yard lacing"):
            return "yard"
        return "sail"
    return "omit"


def _source_to_game_meshes():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "CYCLES"
    scene.render.film_transparent = False

    classifications = {obj.name: _kind(obj) for obj in scene.objects}
    wanted = {}
    for obj in list(scene.objects):
        allowed = bool({c.name for c in obj.users_collection} & ALLOWED_COLLECTIONS)
        kind = classifications[obj.name] if allowed else "omit"
        if allowed and obj.type == "EMPTY":
            continue
        if kind == "omit" or obj.type not in {"MESH", "CURVE"}:
            bpy.data.objects.remove(obj, do_unlink=True)
        else:
            wanted[obj.name] = kind

    # The two long chines were the largest avoidable cost in the visual model.
    # Keep the authored path while lowering the bevel tessellation.
    for obj in scene.objects:
        if "chine batten" in obj.name and obj.type == "CURVE":
            obj.data.resolution_u = 1
            obj.data.bevel_resolution = 1

    bpy.context.view_layer.update()
    original_objects = list(scene.objects)
    for obj in original_objects:
        if obj.type not in {"MESH", "CURVE"}:
            continue
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(
            evaluated, preserve_all_data_layers=True, depsgraph=depsgraph,
        )
        mesh.name = obj.name + " | game geometry"
        mesh.transform(obj.matrix_world)
        if mesh.materials.__len__() == 0:
            for slot in obj.material_slots:
                mesh.materials.append(slot.material)
        if obj.type == "CURVE":
            name = obj.name
            new_obj = bpy.data.objects.new(name + " | converted", mesh)
            for col in list(obj.users_collection):
                col.objects.link(new_obj)
            bpy.data.objects.remove(obj, do_unlink=True)
            new_obj.name = name
        else:
            obj.parent = None
            obj.matrix_world = Matrix.Identity(4)
            for modifier in list(obj.modifiers):
                obj.modifiers.remove(modifier)
            obj.data = mesh
        bpy.context.view_layer.update()

    # A single coordinate layer on all pieces, including solid-colour paint,
    # keeps the merged Unreal meshes ready for later atlasing.
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        uv = obj.data.uv_layers.get("GameUV") or obj.data.uv_layers.new(name="GameUV")
        for poly in obj.data.polygons:
            axis = max(range(3), key=lambda i: abs(poly.normal[i]))
            axes = [i for i in range(3) if i != axis]
            for loop_index in poly.loop_indices:
                vertex = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
                uv.data[loop_index].uv = (vertex[axes[0]], vertex[axes[1]])

    material_result = prepare_game_materials(OUT)
    assert not material_result["fir_non_mesh_objects"], material_result

    groups = {group: [] for group in GROUP_NAMES}
    for name, group in wanted.items():
        obj = bpy.data.objects.get(name)
        if obj is not None and obj.type == "MESH":
            groups[group].append(obj)
    for group, members in groups.items():
        if not members:
            raise RuntimeError(f"No source meshes in game group {group}")
        bpy.ops.object.select_all(action="DESELECT")
        for obj in members:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = members[0]
        bpy.ops.object.join()
        joined = members[0]
        joined.name = GROUP_NAMES[group]
        joined.data.name = GROUP_NAMES[group] + " mesh"
        groups[group] = joined

    for obj in list(scene.objects):
        if obj.type == "EMPTY":
            bpy.data.objects.remove(obj, do_unlink=True)
    return groups, material_result


def _bone(armature, name, head, tail, parent=None, deform=True):
    bone = armature.edit_bones.new(name)
    bone.head = head
    bone.tail = tail
    bone.use_deform = deform
    if parent:
        bone.parent = armature.edit_bones[parent]
        bone.use_connect = False
    return bone


def _make_rig(groups):
    arm_data = bpy.data.armatures.new("GIS_GameRig")
    rig = bpy.data.objects.new("GIS_GameRig", arm_data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    _bone(arm_data, "Root", (0, 0, 0), (0, 0, .15))
    _bone(arm_data, "RudderYaw", (-2.381, 0, .35), (-2.381, 0, .55), "Root")
    _bone(arm_data, "RudderBladeSlide", (-2.62, 0, .47), (-2.62, 0, .67), "RudderYaw")
    _bone(arm_data, "CenterboardSlide", (.15, 0, .15), (.15, 0, .35), "Root")
    _bone(arm_data, "SailSwing", (1.25, 0, .162), (1.25, 0, .362), "Root")
    _bone(arm_data, "SailHoist", (.30, -.15, 4.87), (.30, -.15, 5.07), "SailSwing")
    sockets = {
        "HalyardMast": ((1.22, 0, 4.89), "Root"),
        "HalyardYard": ((.17, -.16, 4.75), "SailHoist"),
        "SheetBoom": ((-1.54, -.148, 1.15), "SailSwing"),
        "SheetTraveller": ((-2.17, -.02, .60), "Root"),
        "DownhaulBoom": ((1.18, -.148, 1.15), "SailSwing"),
        "DownhaulDeck": ((1.14, -.08, .52), "Root"),
        "ShockCordStock": ((-2.48, -.035, .45), "RudderYaw"),
        "ShockCordBlade": ((-2.55, -.018, .78), "RudderBladeSlide"),
    }
    for name, (head, parent) in sockets.items():
        _bone(arm_data, name, head, (head[0], head[1], head[2] + .06), parent, False)
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front = True
    rig.hide_render = True
    rig["asset_units"] = "metres; FBX records 100 centimetres per metre"
    rig["orientation"] = "+X bow, +Y starboard, +Z up"

    for group, obj in groups.items():
        vertex_group = obj.vertex_groups.new(name=DEFORM_BONE[group])
        vertex_group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
        modifier = obj.modifiers.new("GIS skeletal movement", "ARMATURE")
        modifier.object = rig
        modifier.use_deform_preserve_volume = False
        obj.parent = rig
        obj.matrix_parent_inverse = rig.matrix_world.inverted()
    return rig


def _sail_uv(x, z):
    # Invert the source sail's bilinear quadrilateral in its XZ plane.
    u = max(0.0, min(1.0, (x + 1.80) / 3.283))
    v = max(0.0, min(1.0, (z - 1.15) / 4.0))
    for _ in range(9):
        left_x = -1.80 + 1.4056 * v
        right_x = 1.483 - .3686 * v
        fx = left_x + u * (right_x - left_x) - x
        fz = 1.15 + v * (5.1361 - 2.7970 * u) - z
        xu = right_x - left_x
        xv = 1.4056 - 1.7742 * u
        zv = 5.1361 - 2.7970 * u
        zu = -2.7970 * v
        determinant = xu * zv - xv * zu
        if abs(determinant) < 1e-8:
            break
        u -= (fx * zv - fz * xv) / determinant
        v -= (fz * xu - fx * zu) / determinant
    return max(0, min(1, u)), max(0, min(1, v))


def _make_furled_sail(sail):
    sail.shape_key_add(name="Basis", from_mix=False)
    furled = sail.shape_key_add(name="Furled", from_mix=False)
    for vertex, key_vertex in zip(sail.data.vertices, furled.data):
        x, y, z = vertex.co
        u, v = _sail_uv(x, z)
        rest_x = (-1.80 + 1.4056 * v) + u * (3.283 - 1.7742 * v)
        rest_z = 1.15 + v * (5.1361 - 2.7970 * u)
        camber = -0.22 * math.sin(math.pi * u) * math.sin(math.pi * v) ** .72
        camber += .010 * math.sin(7 * math.pi * v) * math.sin(math.pi * u)
        dx, dy, dz = x - rest_x, y - (-.105 + camber), z - rest_z
        pleat = math.sin(12 * math.pi * v)
        key_vertex.co = (
            -1.80 + 3.283 * u + dx * .25,
            -.105 + dy + .035 * pleat * math.sin(math.pi * u) + camber * .07,
            1.15 + .25 * v + .025 * pleat * math.sin(math.pi * u) + dz * .18,
        )
    furled.value = 0.0
    furled.keyframe_insert(data_path="value", frame=1)
    furled.value = 1.0
    furled.keyframe_insert(data_path="value", frame=61)
    action = sail.data.shape_keys.animation_data.action
    action.name = "SailFurlMorph"
    furled.value = 0.0
    return action


def _rig_pose_reset(rig):
    for bone in rig.pose.bones:
        bone.location = (0, 0, 0)
        bone.rotation_mode = "QUATERNION"
        bone.rotation_quaternion = (1, 0, 0, 0)
        bone.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def _start_action(rig, name):
    rig.animation_data_create().action = None
    _rig_pose_reset(rig)
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    rig.animation_data_create().action = action
    driven = {
        "TillerPortStarboard": "RudderYaw",
        "RudderBladeLift": "RudderBladeSlide",
        "CenterboardLift": "CenterboardSlide",
        "TackPortToStarboard": "SailSwing",
        "JibeStarboardToPort": "SailSwing",
        "SailRaiseLower": "SailHoist",
    }[name]
    # FBX bakes every bone. Key a neutral pose in each clip so a previous
    # action cannot leak its last unkeyed sail/tiller pose into the next one.
    for pose_bone in rig.pose.bones:
        if pose_bone.name == driven:
            continue
        pose_bone.keyframe_insert(data_path="location", frame=1)
        pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=1)
    return action


def _bone_world_key(rig, bone_name, world_transform, frame):
    pb = rig.pose.bones[bone_name]
    pb.matrix = world_transform @ pb.bone.matrix_local
    pb.keyframe_insert(data_path="location", frame=frame)
    pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)


def _rotate_about(pivot, axis, angle):
    return Matrix.Translation(Vector(pivot)) @ Matrix.Rotation(angle, 4, axis) @ Matrix.Translation(-Vector(pivot))


def _make_actions(rig):
    actions = {}
    identity = Matrix.Identity(4)

    action = _start_action(rig, "TillerPortStarboard")
    for frame, angle in ((1, -45), (25, 0), (49, 45), (73, 0)):
        _bone_world_key(rig, "RudderYaw", _rotate_about((-2.381, 0, .35), "Z", math.radians(angle)), frame)
    actions[action.name] = action

    action = _start_action(rig, "RudderBladeLift")
    for frame, dz in ((1, 0.0), (31, .55)):
        _bone_world_key(rig, "RudderBladeSlide", Matrix.Translation((0, 0, dz)), frame)
    actions[action.name] = action

    action = _start_action(rig, "CenterboardLift")
    for frame, dz in ((1, 0.0), (41, .72)):
        _bone_world_key(rig, "CenterboardSlide", Matrix.Translation((0, 0, dz)), frame)
    actions[action.name] = action

    swing_pivot = (1.25, 0, .162)
    action = _start_action(rig, "TackPortToStarboard")
    for frame, angle in ((1, 50), (31, 0), (61, -50)):
        _bone_world_key(rig, "SailSwing", _rotate_about(swing_pivot, "Z", math.radians(angle)), frame)
    actions[action.name] = action

    action = _start_action(rig, "JibeStarboardToPort")
    for frame, angle in ((1, -50), (11, 0), (21, 50)):
        _bone_world_key(rig, "SailSwing", _rotate_about(swing_pivot, "Z", math.radians(angle)), frame)
    actions[action.name] = action

    action = _start_action(rig, "SailRaiseLower")
    yard_a = Vector((1.1144, -.15, 3.4891))
    yard_b = Vector((-.3944, -.15, 6.2861))
    yard_direction = (yard_b - yard_a).normalized()
    yard_a -= yard_direction * .2115
    yard_b += yard_direction * .2115
    rest_center = (yard_a + yard_b) / 2
    target_center = Vector((-.18, -.15, 1.40))
    angle = math.atan2((yard_b - yard_a).z, (yard_b - yard_a).x) - math.pi
    # The lowered yard stays along the boom, just above gathered cloth.
    lowered = (Matrix.Translation(target_center)
               @ Matrix.Rotation(angle, 4, "Y")
               @ Matrix.Translation(-rest_center))
    for frame, transform in ((1, identity), (61, lowered)):
        _bone_world_key(rig, "SailHoist", transform, frame)
    actions[action.name] = action

    rig.animation_data.action = None
    _rig_pose_reset(rig)
    bpy.context.scene.frame_set(1)
    return actions


def main():
    groups, material_result = _source_to_game_meshes()
    rig = _make_rig(groups)
    morph_action = _make_furled_sail(groups["sail"])
    actions = _make_actions(rig)

    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, 73
    scene.render.film_transparent = True
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.engine = "BLENDER_EEVEE"
    # Keep a clean modelling file: only seven skinned meshes and one rig.
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = rig
    fir_image = bpy.data.images["GIS varnished fir base color"]
    fir_image.filepath = "//fir_varnished_basecolor.png"
    bpy.ops.wm.save_as_mainfile(
        filepath=str(OUT / "Goat_Island_Skiff_Game.blend"), relative_remap=False,
    )
    assert Path(bpy.path.abspath(fir_image.filepath)).is_file(), fir_image.filepath

    results = export_unreal_asset(
        rig, list(groups.values()), actions, OUT,
        asset_stem="Goat_Island_Skiff", export_glb_preview=True,
        morph_actions={"SailRaiseLower": (groups["sail"], morph_action)},
        animation_meshes={
            "TillerPortStarboard": [groups["stock"]],
            "RudderBladeLift": [groups["blade"]],
            "CenterboardLift": [groups["board"]],
            "TackPortToStarboard": [groups["boom"], groups["sail"]],
            "JibeStarboardToPort": [groups["boom"], groups["sail"]],
            "SailRaiseLower": [groups["yard"], groups["sail"]],
        },
    )
    triangles = sum(len(p.vertices) - 2 for obj in groups.values()
                    for p in obj.data.polygons)
    manifest = {
        "source": "Goat_Island_Skiff.blend",
        "game_blend": "Goat_Island_Skiff_Game.blend",
        "skeletal_mesh": results["skeletal_mesh"].name,
        "animations": {name: path.name for name, path in results["animations"].items()},
        "glb_preview": results["glb_preview"].name if results["glb_preview"] else None,
        "metres_per_unit": 1.0,
        "axes": "+X bow, +Y starboard, +Z up",
        "meshes": {group: {"name": obj.name, "vertices": len(obj.data.vertices),
                            "triangles": sum(len(p.vertices) - 2 for p in obj.data.polygons)}
                   for group, obj in groups.items()},
        "triangle_total": triangles,
        "bones": [bone.name for bone in rig.data.bones],
        "morph_targets": ["Sail_Cloth:Furled"],
        "fir_texture": Path(material_result["texture"]).name,
        "missing_dynamic_rope_meshes": ["Halyard to yard", "Downhaul", "Mainsheet upper fall"],
    }
    (OUT / "asset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("GAME_ASSET_BUILT", json.dumps({
        "triangles": triangles, "meshes": len(groups), "actions": list(actions),
        "material_result": material_result,
    }), flush=True)


if __name__ == "__main__":
    main()
