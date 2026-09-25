"""Unreal-oriented FBX export for the Goat Island Skiff game asset.

Call :func:`export_unreal_asset` from Blender after the game meshes have been
converted to meshes, weighted to ``GIS_GameRig``, and given UVs/materials.
The authored scene uses metres: +X bow, +Y starboard, +Z up.  The FBX files
carry centimetre-based unit metadata (100 cm per authored metre).  Unreal's
FBX importer should import the base file as a *Skeletal Mesh*, then each
animation file onto the skeleton created by that import.

The base FBX contains one armature and all supplied mesh objects.  Each
animation FBX also contains the skinned meshes to anchor the same neutral
bind pose, plus exactly one sampled rig Action. In Unreal, import animation
FBXs onto the base Skeleton with "Import Mesh" disabled.
Render-only objects, lights, water and cameras are never selected for export.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Iterable, Mapping

import bpy


_FBX_COMMON = dict(
    use_selection=True,
    object_types={'ARMATURE', 'MESH'},
    global_scale=1.0,
    apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_UNITS',
    axis_forward='-Y',
    axis_up='Z',
    use_space_transform=True,
    bake_space_transform=False,  # Blender warns this breaks armatures.
    add_leaf_bones=False,
    primary_bone_axis='Y',
    secondary_bone_axis='X',
    armature_nodetype='NULL',
    use_armature_deform_only=False,
    # Applying a non-armature modifier creates a temporary evaluated mesh and
    # drops Shape Keys, including the sail's Furled morph target.  Game meshes
    # must therefore have their modelling modifiers applied before export.
    use_mesh_modifiers=False,
    mesh_smooth_type='FACE',
    path_mode='RELATIVE',
    embed_textures=False,
    use_custom_props=False,
)


def _safe_name(value: str) -> str:
    name = re.sub(r'[^A-Za-z0-9_]+', '_', value.strip()).strip('_')
    if not name:
        raise ValueError(f'No usable file name in {value!r}')
    return name


def _validate(armature, meshes, actions, scene):
    if armature.type != 'ARMATURE' or armature.name != 'GIS_GameRig':
        raise ValueError('Expected the GIS_GameRig Armature object')
    if not meshes:
        raise ValueError('Supply at least one game mesh')
    if not actions:
        raise ValueError('Supply at least one animation Action')
    if scene.unit_settings.system not in {'NONE', 'METRIC'} or not math.isclose(
        scene.unit_settings.scale_length, 1.0, abs_tol=1e-8
    ):
        raise ValueError('Authoring scene must use metre-sized Blender units (scale_length=1)')

    visible_objects = set(bpy.context.view_layer.objects)
    for obj in (armature, *meshes):
        if obj not in visible_objects:
            raise ValueError(f'{obj.name} is not in the active scene view layer')
    bone_names = {bone.name for bone in armature.data.bones}
    if not bone_names:
        raise ValueError('GIS_GameRig has no bones')

    for obj in meshes:
        if obj.type != 'MESH':
            raise ValueError(f'{obj.name} is not a mesh; convert curves before export')
        if not any(mod.type == 'ARMATURE' and mod.object == armature for mod in obj.modifiers):
            raise ValueError(f'{obj.name} lacks an Armature modifier targeting GIS_GameRig')
        pending = [
            mod.name for mod in obj.modifiers
            if mod.type != 'ARMATURE' and (mod.show_viewport or mod.show_render)
        ]
        if pending:
            raise ValueError(
                f'{obj.name} has unapplied modifiers {pending}; apply them before '
                'export so the FBX keeps the Furled shape key and final geometry'
            )
        deform_groups = {group.index for group in obj.vertex_groups if group.name in bone_names}
        if not deform_groups:
            raise ValueError(f'{obj.name} has no vertex group named for a rig bone')
        unweighted = sum(
            1 for vertex in obj.data.vertices
            if not any(group.group in deform_groups and group.weight > 0 for group in vertex.groups)
        )
        if unweighted:
            raise ValueError(f'{obj.name} has {unweighted} vertices without a bone weight')

    names = set()
    for clip_name, action in actions.items():
        safe = _safe_name(clip_name)
        if safe in names:
            raise ValueError(f'Duplicate animation file name: {safe}')
        names.add(safe)
        if not isinstance(action, bpy.types.Action):
            raise TypeError(f'{clip_name} is not a Blender Action')
        if action.frame_range[1] <= action.frame_range[0]:
            raise ValueError(f'{clip_name} must span at least two frames')


def _select_exact(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.hide_set(False)
        obj.hide_render = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def _activate_action(animated_id, action, target_id_type):
    animation_data = animated_id.animation_data_create()
    animation_data.action = action
    # Blender 4.4+ Actions can have multiple slots.  The rig owns one OBJECT
    # slot, while Shape Keys use a KEY slot. Selecting it avoids a silent clip.
    slots = [slot for slot in action.slots if slot.target_id_type == target_id_type]
    if slots:
        animation_data.action_slot = slots[0]
    if animation_data.action != action:
        raise RuntimeError(f'Could not activate Action {action.name}')
    if slots and animation_data.action_slot != slots[0]:
        raise RuntimeError(f'Could not activate Action slot for {action.name}')


def _export_fbx(path: Path, *, animation: bool):
    options = dict(_FBX_COMMON)
    options.update(
        filepath=str(path),
        bake_anim=animation,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_use_all_bones=True,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
    )
    result = bpy.ops.export_scene.fbx(**options)
    if 'FINISHED' not in result or not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f'FBX export failed: {path}')


def export_unreal_asset(
    armature: bpy.types.Object,
    meshes: Iterable[bpy.types.Object],
    actions: Mapping[str, bpy.types.Action],
    output_dir: str | Path,
    *,
    asset_stem: str = 'Goat_Island_Skiff',
    export_glb_preview: bool = False,
    morph_actions: Mapping[str, tuple[bpy.types.Object, bpy.types.Action]] | None = None,
    animation_meshes: Mapping[str, Iterable[bpy.types.Object]] | None = None,
) -> dict:
    """Export the base skeletal FBX and separate animation FBXs.

    ``meshes`` is an explicit list of skinned, UV-ready mesh objects; all
    vertices must have positive weights in a group matching a rig bone.
    Apply all non-armature modifiers to the game meshes before calling this;
    disabling FBX modifier evaluation preserves the Furled sail shape key.
    ``actions`` maps friendly clip names to Blender Actions.  The function
    ``morph_actions`` optionally maps a clip name to ``(mesh, shape_key_action)``.
    For example, pass ``{'SailRaiseLower': (sail_mesh, furled_action)}`` to
    export the sail's keyed ``Furled`` shape together with the
    SailRaiseLower bone Action in one animation FBX. ``animation_meshes`` can
    select the skinned parts for each clip, such as the rudder stock for a
    tiller clip. Every clip includes at least one skinned mesh so Blender's
    FBX exporter uses the base skeleton's neutral bind pose. Without this
    mapping, all game meshes are included. Unreal can import that
    morph curve into the clip if morph target animation import is enabled.
    The function
    selects the necessary objects, temporarily mutes NLA tracks, and restores
    the original scene selection, frame, frame range, pose mode and Action.

    Returns ``{'skeletal_mesh': Path, 'animations': {name: Path},
    'glb_preview': Path | None}``. The GLB, when requested, is a static
    inspection copy; the FBX files are the Unreal deliverables.
    """
    mesh_list = list(dict.fromkeys(meshes))
    action_map = dict(actions)
    morph_map = dict(morph_actions or {})
    animation_mesh_map = {
        clip_name: list(dict.fromkeys(objects))
        for clip_name, objects in (animation_meshes or {}).items()
    }
    scene = bpy.context.scene
    _validate(armature, mesh_list, action_map, scene)
    for clip_name, clip_meshes in animation_mesh_map.items():
        if clip_name not in action_map:
            raise ValueError(f'Animation mesh selection has no matching clip: {clip_name}')
        if not clip_meshes or any(mesh not in mesh_list for mesh in clip_meshes):
            raise ValueError(f'Animation meshes for {clip_name} must be nonempty game mesh subset')
    for clip_name, (mesh, action) in morph_map.items():
        if clip_name not in action_map:
            raise ValueError(f'Morph action has no matching bone clip: {clip_name}')
        if mesh not in mesh_list or not mesh.data.shape_keys:
            raise ValueError(f'Morph mesh for {clip_name} must be a supplied game mesh with Shape Keys')
        if 'Furled' not in mesh.data.shape_keys.key_blocks:
            raise ValueError(f'Morph mesh for {clip_name} lacks a Furled shape key')
        if not isinstance(action, bpy.types.Action):
            raise TypeError(f'Morph action for {clip_name} is not a Blender Action')
        if not any(slot.target_id_type == 'KEY' for slot in action.slots):
            raise ValueError(f'Morph action for {clip_name} has no Shape Key (KEY) slot')
    stem = _safe_name(asset_stem)
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    originally_selected = tuple(bpy.context.selected_objects)
    originally_active = bpy.context.view_layer.objects.active
    original_visibility = {
        obj: (obj.hide_get(), obj.hide_render)
        for obj in (armature, *mesh_list)
    }
    original_frame = scene.frame_current
    original_start, original_end = scene.frame_start, scene.frame_end
    original_pose_position = armature.data.pose_position
    anim_data = armature.animation_data_create()
    original_action = anim_data.action
    original_slot = anim_data.action_slot
    nla_mutes = [(track, track.mute) for track in anim_data.nla_tracks]
    key_animation_states = {}
    for obj in mesh_list:
        key_data = obj.data.shape_keys
        if not key_data or key_data in key_animation_states:
            continue
        had_animation_data = key_data.animation_data is not None
        key_anim = key_data.animation_data_create()
        key_animation_states[key_data] = (
            key_anim.action,
            key_anim.action_slot,
            [(track, track.mute) for track in key_anim.nla_tracks],
            had_animation_data,
        )
    original_shape_values = [
        (key, key.value)
        for obj in mesh_list if obj.data.shape_keys
        for key in obj.data.shape_keys.key_blocks[1:]
    ]

    skeletal_path = out / f'SK_{stem}.fbx'
    animation_paths = {}
    glb_path = None
    try:
        for track, _ in nla_mutes:
            track.mute = True
        for key_data, (_, _, key_nla_mutes, _) in key_animation_states.items():
            key_data.animation_data.action = None
            for track, _ in key_nla_mutes:
                track.mute = True
        # Base mesh must be in the skeleton's reference pose.
        anim_data.action = None
        armature.data.pose_position = 'REST'
        for key, _ in original_shape_values:
            key.value = 0.0
        scene.frame_set(original_start)
        _select_exact([armature, *mesh_list])
        _export_fbx(skeletal_path, animation=False)

        if export_glb_preview:
            glb_path = out / f'Preview_{stem}.glb'
            result = bpy.ops.export_scene.gltf(
                filepath=str(glb_path),
                export_format='GLB',
                use_selection=True,
                export_animations=False,
            )
            if 'FINISHED' not in result or not glb_path.is_file():
                raise RuntimeError(f'GLB preview export failed: {glb_path}')

        armature.data.pose_position = 'POSE'
        for clip_name, action in action_map.items():
            _activate_action(armature, action, 'OBJECT')
            for key_data in key_animation_states:
                key_data.animation_data.action = None
            if clip_name in morph_map:
                morph_mesh, morph_action = morph_map[clip_name]
                _activate_action(morph_mesh.data.shape_keys, morph_action, 'KEY')
            clip_meshes = list(animation_mesh_map.get(clip_name, mesh_list))
            if clip_name in morph_map and morph_mesh not in clip_meshes:
                clip_meshes.append(morph_mesh)
            # An armature-only FBX can derive its rest pose from the first
            # animation sample instead of the base Skeleton. Including the
            # relevant skinned mesh writes its bind pose into the clip; Unreal
            # imports only animation tracks when "Import Mesh" is disabled.
            _select_exact([armature, *clip_meshes])
            start = math.floor(action.frame_range[0])
            end = math.ceil(action.frame_range[1])
            scene.frame_start, scene.frame_end = start, end
            scene.frame_set(start)
            path = out / f'A_{stem}_{_safe_name(clip_name)}.fbx'
            _export_fbx(path, animation=True)
            animation_paths[clip_name] = path
    finally:
        anim_data.action = original_action
        if original_action is not None and original_slot is not None:
            anim_data.action_slot = original_slot
        for track, mute in nla_mutes:
            track.mute = mute
        for key_data, (key_action, key_slot, key_nla_mutes, had_animation_data) in key_animation_states.items():
            key_anim = key_data.animation_data
            key_anim.action = key_action
            if key_action is not None and key_slot is not None:
                key_anim.action_slot = key_slot
            for track, mute in key_nla_mutes:
                track.mute = mute
            if not had_animation_data:
                key_data.animation_data_clear()
        for key, value in original_shape_values:
            key.value = value
        armature.data.pose_position = original_pose_position
        scene.frame_start, scene.frame_end = original_start, original_end
        scene.frame_set(original_frame)
        bpy.ops.object.select_all(action='DESELECT')
        for obj, (hidden, hidden_render) in original_visibility.items():
            obj.hide_set(hidden)
            obj.hide_render = hidden_render
        for obj in originally_selected:
            if obj.name in bpy.context.view_layer.objects and not obj.hide_get():
                obj.select_set(True)
        bpy.context.view_layer.objects.active = originally_active

    return {
        'skeletal_mesh': skeletal_path,
        'animations': animation_paths,
        'glb_preview': glb_path,
    }
