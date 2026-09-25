"""Render temporary inspection views of the GIS game rig without editing it."""

from pathlib import Path
import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
GAME = HERE / "game_asset"
bpy.ops.wm.open_mainfile(filepath=str(GAME / "Goat_Island_Skiff_Game.blend"))
scene = bpy.context.scene
rig = bpy.data.objects["GIS_GameRig"]
sail = bpy.data.objects["Sail_Cloth"]

scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1100
scene.render.resolution_y = 780
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.world.use_nodes = True
background = scene.world.node_tree.nodes.get("Background")
background.inputs["Color"].default_value = (.19, .25, .31, 1)
background.inputs["Strength"].default_value = .45


def area(name, pos, power, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = power
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = pos
    obj.rotation_euler = (Vector((0, 0, 1.3)) - obj.location).to_track_quat("-Z", "Y").to_euler()


area("Game preview key", (1, -5, 8), 2500, 7)
area("Game preview fill", (-5, 3, 6), 1800, 6)
area("Game preview rim", (4, 5, 7), 1500, 5)

camera_data = bpy.data.cameras.new("Game preview camera")
camera = bpy.data.objects.new("Game preview camera", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera
camera_data.type = "ORTHO"
camera_data.ortho_scale = 10.6


def point_camera(pos, target=(0, 0, 2.55)):
    camera.location = pos
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


def activate(action_name, frame):
    rig.animation_data.action = None
    sail.data.shape_keys.animation_data.action = None
    for pose_bone in rig.pose.bones:
        pose_bone.location = (0, 0, 0)
        pose_bone.rotation_mode = "QUATERNION"
        pose_bone.rotation_quaternion = (1, 0, 0, 0)
    sail.data.shape_keys.key_blocks["Furled"].value = 0
    if action_name:
        action = bpy.data.actions[action_name]
        rig.animation_data.action = action
        rig.animation_data.action_slot = next(
            slot for slot in action.slots if slot.target_id_type == "OBJECT")
        if action_name == "SailRaiseLower":
            morph = bpy.data.actions["SailFurlMorph"]
            key_anim = sail.data.shape_keys.animation_data
            key_anim.action = morph
            key_anim.action_slot = next(
                slot for slot in morph.slots if slot.target_id_type == "KEY")
    scene.frame_set(frame)
    bpy.context.view_layer.update()


views = [
    ("Game_preview_raised.png", None, 1, (-6.5, -8.5, 5.1), 10.6),
    ("Game_preview_sail_lowered.png", "SailRaiseLower", 61, (-5.6, -7.0, 4.0), 9.4),
    ("Game_preview_sail_halfway.png", "SailRaiseLower", 31, (-6.5, -8.5, 5.1), 10.6),
    ("Game_preview_tack_port.png", "TackPortToStarboard", 1, (-6.5, -8.5, 5.1), 10.6),
    ("Game_preview_tack_starboard.png", "TackPortToStarboard", 61, (-6.5, -8.5, 5.1), 10.6),
    ("Game_preview_tiller_port.png", "TillerPortStarboard", 49, (-5.5, -6.5, 3.5), 8.0),
]
for filename, action, frame, pos, scale in views:
    activate(action, frame)
    point_camera(pos)
    camera_data.ortho_scale = scale
    scene.render.filepath = str(GAME / filename)
    bpy.ops.render.render(write_still=True)
    print("PREVIEW_RENDERED", filename, flush=True)
