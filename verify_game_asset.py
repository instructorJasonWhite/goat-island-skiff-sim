"""Blender-side acceptance checks for the GIS moving game asset."""

from pathlib import Path
import math
import bpy


HERE = Path(__file__).resolve().parent
GAME = HERE / "game_asset"
blend = GAME / "Goat_Island_Skiff_Game.blend"
assert blend.is_file(), f"Game source missing: {blend}"
bpy.ops.wm.open_mainfile(filepath=str(blend))

rig = bpy.data.objects["GIS_GameRig"]
assert rig.type == "ARMATURE"
required = {
    "Root", "RudderYaw", "RudderBladeSlide", "CenterboardSlide",
    "SailSwing", "SailHoist", "HalyardYard", "HalyardMast",
    "SheetBoom", "SheetTraveller", "ShockCordStock", "ShockCordBlade",
}
assert required <= {bone.name for bone in rig.data.bones}

meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert len(meshes) <= 12, [o.name for o in meshes]
assert not [o.name for o in bpy.context.scene.objects if o.type == "CURVE"]
assert not [o.name for o in bpy.context.scene.objects if o.type == "LIGHT"]
assert not [o.name for o in bpy.context.scene.objects if o.type == "CAMERA"]
tris = sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons)
assert tris < 70000, f"Triangle count unexpectedly high: {tris}"

for obj in meshes:
    assert any(m.type == "ARMATURE" and m.object == rig for m in obj.modifiers), obj.name
    assert obj.data.uv_layers, f"No UV coordinates: {obj.name}"

sail = bpy.data.objects["Sail_Cloth"]
assert sail.data.shape_keys is not None
assert "Furled" in sail.data.shape_keys.key_blocks
basis = sail.data.shape_keys.key_blocks["Basis"]
furled = sail.data.shape_keys.key_blocks["Furled"]
basis_height = max(v.co.z for v in basis.data) - min(v.co.z for v in basis.data)
furled_height = max(v.co.z for v in furled.data) - min(v.co.z for v in furled.data)
assert basis_height > 4.5 and furled_height < 0.5, (basis_height, furled_height)

actions = {
    "SailRaiseLower", "TackPortToStarboard", "JibeStarboardToPort",
    "TillerPortStarboard", "RudderBladeLift", "CenterboardLift",
}
assert actions <= {a.name for a in bpy.data.actions}
for action in actions:
    assert (GAME / f"A_Goat_Island_Skiff_{action}.fbx").is_file(), action
assert (GAME / "SK_Goat_Island_Skiff.fbx").is_file()
assert (GAME / "fir_varnished_basecolor.png").is_file()
fir_image = bpy.data.images["GIS varnished fir base color"]
assert fir_image.filepath == "//fir_varnished_basecolor.png"
assert Path(bpy.path.abspath(fir_image.filepath)).is_file()


def activate(name, frame):
    action = bpy.data.actions[name]
    rig.animation_data.action = action
    rig.animation_data.action_slot = next(
        slot for slot in action.slots if slot.target_id_type == "OBJECT")
    bpy.context.scene.frame_set(frame)
    bpy.context.view_layer.update()


def world_yaw(name):
    pose = rig.pose.bones[name]
    movement = pose.matrix @ pose.bone.matrix_local.inverted()
    return math.degrees(math.atan2(movement[1][0], movement[0][0]))


def head_delta_z(name):
    pose = rig.pose.bones[name]
    return pose.matrix.translation.z - pose.bone.matrix_local.translation.z


for name, bone, frames, wanted in (
    ("TillerPortStarboard", "RudderYaw", (1, 49), (-45, 45)),
    ("TackPortToStarboard", "SailSwing", (1, 61), (50, -50)),
    ("JibeStarboardToPort", "SailSwing", (1, 21), (-50, 50)),
):
    for frame, target in zip(frames, wanted):
        activate(name, frame)
        actual = world_yaw(bone)
        assert abs(actual - target) < 1.5, (name, frame, actual, target)

for name, bone, frame, target in (
    ("RudderBladeLift", "RudderBladeSlide", 31, .55),
    ("CenterboardLift", "CenterboardSlide", 41, .72),
):
    activate(name, frame)
    assert abs(head_delta_z(bone) - target) < .015, (name, head_delta_z(bone))

# A previous tack or jibe must not affect the separate hoist clip.
activate("JibeStarboardToPort", 21)
activate("SailRaiseLower", 1)
assert abs(world_yaw("SailSwing")) < .01
activate("SailRaiseLower", 61)
assert abs(world_yaw("SailSwing")) < .01
assert head_delta_z("SailHoist") < -2.5
shape = sail.data.shape_keys
morph = bpy.data.actions["SailFurlMorph"]
shape.animation_data.action = morph
shape.animation_data.action_slot = next(
    slot for slot in morph.slots if slot.target_id_type == "KEY")
bpy.context.scene.frame_set(1)
assert shape.key_blocks["Furled"].value < .01
bpy.context.scene.frame_set(61)
assert shape.key_blocks["Furled"].value > .99

print(f"GAME_ASSET_OK meshes={len(meshes)} triangles={tris} bones={len(rig.data.bones)}")
