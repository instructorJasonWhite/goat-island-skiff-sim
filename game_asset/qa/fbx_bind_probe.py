"""Probe whether a skinned mesh keeps animation FBX bind bones in rest pose."""

import json
import math
import sys
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
import game_asset_export as export  # noqa: E402


def sample(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    rig = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
    rest = rig.data.bones['RudderYaw'].matrix_local
    action = rig.animation_data.action
    result = {
        'rest_euler': [math.degrees(x) for x in rest.to_euler()],
        'action_range': list(action.frame_range),
        'frames': {},
    }
    for frame in (round(action.frame_range[0]), round(action.frame_range[1])):
        bpy.context.scene.frame_set(frame)
        pb = rig.pose.bones['RudderYaw']
        delta = rig.matrix_world @ pb.matrix @ pb.bone.matrix_local.inverted() @ rig.matrix_world.inverted()
        result['frames'][frame] = [math.degrees(x) for x in delta.to_euler()]
    return result


def main():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'Goat_Island_Skiff_Game.blend'))
    rig = bpy.data.objects['GIS_GameRig']
    stock = bpy.data.objects['Rudder_Stock_and_Tiller']
    action = bpy.data.actions['TillerPortStarboard']
    rig.animation_data.action = action
    rig.animation_data.action_slot = [s for s in action.slots if s.target_id_type == 'OBJECT'][0]
    rig.data.pose_position = 'POSE'
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 73
    bpy.context.scene.frame_set(1)
    paths = {}
    for label, objects in [('armature_only', [rig]), ('armature_and_mesh', [rig, stock])]:
        export._select_exact(objects)
        path = Path(__file__).parent / f'probe_{label}.fbx'
        export._export_fbx(path, animation=True)
        paths[label] = path
    report = {label: sample(path) for label, path in paths.items()}
    print('GIS_FBX_PROBE=' + json.dumps(report))


if __name__ == '__main__':
    main()
