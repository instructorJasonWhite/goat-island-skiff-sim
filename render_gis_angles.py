"""Render three additional full-sail views from the saved GIS Blender scene.

Run with Blender in the background after loading Goat_Island_Skiff.blend.
Set GIS_ANGLE_DRAFT=1 for quick composition previews.  Final runs also save
the extra editable cameras into the .blend file.
"""

import os
from pathlib import Path

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
SCENE_FILE = HERE / 'Goat_Island_Skiff.blend'
DRAFT = os.environ.get('GIS_ANGLE_DRAFT') == '1'

VIEWS = [
    ('Bow port quarter', 'bow_port_quarter',
     (6.0, -8.8, 4.6), (0, 0, 2.65), 10.2),
    ('Port beam', 'port_beam',
     (0, -11.2, 3.9), (0, 0, 2.7), 9.8),
    ('Stern starboard quarter', 'stern_starboard_quarter',
     (-7.1, 8.8, 5.1), (0, 0, 2.65), 10.4),
]


def make_camera(label, location, target, scale, collection):
    name = 'Camera | full rig | ' + label
    existing = bpy.data.objects.get(name)
    if existing is not None:
        return existing
    data = bpy.data.cameras.new(name)
    camera = bpy.data.objects.new(name, data)
    collection.objects.link(camera)
    camera.location = location
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    data.type = 'ORTHO'
    data.ortho_scale = scale
    return camera


def main():
    scene = bpy.context.scene
    cameras = bpy.data.collections.get('05 Cameras and softboxes')
    if cameras is None:
        raise RuntimeError('Open Goat_Island_Skiff.blend before rendering views')

    old_camera = scene.camera
    old_path = scene.render.filepath
    old_width = scene.render.resolution_x
    old_height = scene.render.resolution_y
    old_samples = scene.cycles.samples

    for obj in bpy.data.collections['02 Balanced lug rig'].objects:
        obj.hide_render = False
    bpy.data.objects['Dark rippled water | display surface'].hide_render = False
    bpy.data.objects['Studio floor'].hide_render = True

    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = 850 if DRAFT else 1600
    scene.render.resolution_y = 664 if DRAFT else 1250
    scene.render.resolution_percentage = 100
    scene.cycles.samples = 12 if DRAFT else 32
    scene.cycles.use_denoising = True

    for label, filename, location, target, scale in VIEWS:
        scene.camera = make_camera(label, location, target, scale, cameras)
        prefix = 'draft_angle_' if DRAFT else 'Goat_Island_Skiff_'
        scene.render.filepath = str(HERE / (prefix + filename + '.png'))
        print('Rendering', label, 'to', scene.render.filepath, flush=True)
        bpy.ops.render.render(write_still=True)

    scene.camera = old_camera
    scene.render.filepath = old_path
    scene.render.resolution_x = old_width
    scene.render.resolution_y = old_height
    scene.cycles.samples = old_samples
    if not DRAFT:
        info = bpy.data.texts.get('READ ME - Goat Island Skiff')
        if info and 'ADDITIONAL RIG VIEWS:' not in info.as_string():
            info.write('ADDITIONAL RIG VIEWS: bow port quarter, port beam, '
                       'and stern starboard quarter cameras. Select any '
                       'of these cameras to render a different viewpoint.\n')
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(SCENE_FILE))
    print('Angle renders complete.', flush=True)


if __name__ == '__main__':
    main()
