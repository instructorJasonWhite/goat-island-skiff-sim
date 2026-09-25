"""Read-only QA of the saved skiff asset and exported FBX files."""

import json
import math
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]


def activate_action(rig, name):
    action = bpy.data.actions[name]
    ad = rig.animation_data_create()
    ad.action = action
    slots = [s for s in action.slots if s.target_id_type == 'OBJECT']
    if slots:
        ad.action_slot = slots[0]
    return action


def bone_delta(rig, bone_name):
    pb = rig.pose.bones[bone_name]
    return rig.matrix_world @ pb.matrix @ pb.bone.matrix_local.inverted() @ rig.matrix_world.inverted()


def evaluated_bounds(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluation = obj.evaluated_get(depsgraph)
    mesh = evaluation.to_mesh()
    try:
        points = [evaluation.matrix_world @ v.co for v in mesh.vertices]
        return {
            'min': [min(v[i] for v in points) for i in range(3)],
            'max': [max(v[i] for v in points) for i in range(3)],
        }
    finally:
        evaluation.to_mesh_clear()


def sample_action(rig, name, bone, frames, mesh_name=None):
    action = activate_action(rig, name)
    result = {'range': list(action.frame_range), 'frames': {}}
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        delta = bone_delta(rig, bone)
        entry = {
            'translation': list(delta.translation),
            'euler_deg': [math.degrees(x) for x in delta.to_euler()],
            'all_controls': {
                other: {
                    'translation': list(bone_delta(rig, other).translation),
                    'euler_deg': [math.degrees(x) for x in bone_delta(rig, other).to_euler()],
                }
                for other in ('RudderYaw', 'RudderBladeSlide', 'CenterboardSlide',
                              'SailSwing', 'SailHoist')
            },
        }
        if mesh_name:
            entry['bounds'] = evaluated_bounds(bpy.data.objects[mesh_name])
        result['frames'][frame] = entry
    rig.animation_data.action = None
    bpy.context.scene.frame_set(1)
    return result


def summarize_import(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    result = {
        'objects': {o.name: o.type for o in bpy.data.objects},
        'actions': [a.name for a in bpy.data.actions],
        'rigs': {},
        'shape_keys': {},
    }
    rigs = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    for rig in rigs:
        result['rigs'][rig.name] = {
            'bones': [b.name for b in rig.data.bones],
            'action': rig.animation_data.action.name if rig.animation_data and rig.animation_data.action else None,
            'rest': {
                bone: {
                    'head': list(rig.data.bones[bone].head_local),
                    'euler_deg': [math.degrees(x) for x in rig.data.bones[bone].matrix_local.to_euler()],
                }
                for bone in ('RudderYaw', 'SailSwing', 'SailHoist') if bone in rig.data.bones
            },
        }
        if rig.animation_data and rig.animation_data.action:
            action = rig.animation_data.action
            frames = [round(action.frame_range[0]), round(action.frame_range[1])]
            if 'TillerPortStarboard' in path.name:
                frames = [2, 26, 50, 74]
            elif 'TackPortToStarboard' in path.name:
                frames = [2, 32, 62]
            elif 'JibeStarboardToPort' in path.name:
                frames = [2, 12, 22]
            result['rigs'][rig.name]['range'] = list(action.frame_range)
            result['rigs'][rig.name]['samples'] = {}
            for frame in frames:
                bpy.context.scene.frame_set(frame)
                sample = {
                    bone: {
                        'translation': list(bone_delta(rig, bone).translation),
                        'euler_deg': [math.degrees(x) for x in bone_delta(rig, bone).to_euler()],
                    }
                    for bone in ('RudderYaw', 'RudderBladeSlide', 'CenterboardSlide',
                                 'SailSwing', 'SailHoist') if bone in rig.pose.bones
                }
                if 'SailRaiseLower' in path.name:
                    sample['sail_bounds'] = evaluated_bounds(bpy.data.objects['Sail_Cloth'])
                    sample['yard_bounds'] = evaluated_bounds(bpy.data.objects['Yard_and_Lacings'])
                result['rigs'][rig.name]['samples'][frame] = sample
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data.shape_keys:
            keys = obj.data.shape_keys
            result['shape_keys'][obj.name] = {
                'blocks': [k.name for k in keys.key_blocks],
                'action': keys.animation_data.action.name if keys.animation_data and keys.animation_data.action else None,
            }
            if keys.animation_data and keys.animation_data.action and 'Furled' in keys.key_blocks:
                action = keys.animation_data.action
                result['shape_keys'][obj.name]['range'] = list(action.frame_range)
                result['shape_keys'][obj.name]['samples'] = {}
                for frame in (round(action.frame_range[0]), round(action.frame_range[1])):
                    bpy.context.scene.frame_set(frame)
                    result['shape_keys'][obj.name]['samples'][frame] = keys.key_blocks['Furled'].value
    return result


def main():
    bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'Goat_Island_Skiff_Game.blend'))
    rig = bpy.data.objects['GIS_GameRig']
    sail = bpy.data.objects['Sail_Cloth']
    report = {
        'scene': {
            'object_count': len(bpy.data.objects),
            'mesh_count': sum(o.type == 'MESH' for o in bpy.data.objects),
            'triangle_total': sum(len(p.vertices) - 2 for o in bpy.data.objects if o.type == 'MESH' for p in o.data.polygons),
            'sail_keys': [k.name for k in sail.data.shape_keys.key_blocks],
            'sail_key_action': sail.data.shape_keys.animation_data.action.name,
            'materials': {o.name: [m.name for m in o.data.materials] for o in bpy.data.objects if o.type == 'MESH'},
        },
        'actions': {},
    }
    cases = [
        ('TillerPortStarboard', 'RudderYaw', [1, 25, 49, 73], 'Rudder_Stock_and_Tiller'),
        ('RudderBladeLift', 'RudderBladeSlide', [1, 31], 'Rudder_Sliding_Blade'),
        ('CenterboardLift', 'CenterboardSlide', [1, 41], 'Sliding_Centerboard'),
        ('TackPortToStarboard', 'SailSwing', [1, 31, 61], 'Boom_and_Fittings'),
        ('JibeStarboardToPort', 'SailSwing', [1, 11, 21], 'Boom_and_Fittings'),
        ('SailRaiseLower', 'SailHoist', [1, 31, 61], 'Yard_and_Lacings'),
    ]
    for name, bone, frames, mesh in cases:
        report['actions'][name] = sample_action(rig, name, bone, frames, mesh)

    key_data = sail.data.shape_keys
    key_action = key_data.animation_data.action
    if key_action:
        key_data.animation_data.action = key_action
        slots = [s for s in key_action.slots if s.target_id_type == 'KEY']
        if slots:
            key_data.animation_data.action_slot = slots[0]
    report['sail_morph'] = {}
    for frame in (1, 31, 61):
        bpy.context.scene.frame_set(frame)
        report['sail_morph'][frame] = {
            'furled': key_data.key_blocks['Furled'].value,
            'bounds': evaluated_bounds(sail),
        }

    report['fbx_base'] = summarize_import(ROOT / 'SK_Goat_Island_Skiff.fbx')
    report['fbx_clips'] = {
        path.stem: summarize_import(path)
        for path in sorted(ROOT.glob('A_Goat_Island_Skiff_*.fbx'))
    }
    print('GIS_QA_JSON=' + json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
