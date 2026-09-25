"""Render the square mast and its matching partner from the finished scene."""

import os
from pathlib import Path

import bpy
from mathutils import Vector


HERE = Path(__file__).resolve().parent
DRAFT = os.environ.get('GIS_MAST_DETAIL_DRAFT') == '1'


def main():
    scene = bpy.context.scene
    camera_name = 'Camera | hollow square mast and partner detail'
    camera = bpy.data.objects.get(camera_name)
    if camera is None:
        data = bpy.data.cameras.new(camera_name)
        camera = bpy.data.objects.new(camera_name, data)
        bpy.data.collections['05 Cameras and softboxes'].objects.link(camera)
    camera.location = (2.6, 1.45, 2.75)
    target = Vector((1.25, 0.0, 0.45))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = 1.30

    old_camera = scene.camera
    old_path = scene.render.filepath
    old_width = scene.render.resolution_x
    old_height = scene.render.resolution_y
    old_samples = scene.cycles.samples

    for obj in bpy.data.collections['02 Balanced lug rig'].objects:
        obj.hide_render = False
    bpy.data.objects['Dark rippled water | display surface'].hide_render = False
    bpy.data.objects['Studio floor'].hide_render = True

    scene.camera = camera
    scene.cycles.samples = 12 if DRAFT else 32
    scene.render.resolution_x = 800 if DRAFT else 1400
    scene.render.resolution_y = 600 if DRAFT else 1050
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(HERE / ('draft_square_mast_detail.png' if DRAFT
                                       else 'Goat_Island_Skiff_square_mast_detail.png'))
    bpy.ops.render.render(write_still=True)

    scene.camera = old_camera
    scene.render.filepath = old_path
    scene.render.resolution_x = old_width
    scene.render.resolution_y = old_height
    scene.cycles.samples = old_samples
    if not DRAFT:
        info = bpy.data.texts.get('READ ME - Goat Island Skiff')
        if info and 'SQUARE MAST DETAIL CAMERA:' not in info.as_string():
            info.write('SQUARE MAST DETAIL CAMERA: a close view of the hollow '
                       'square fir mast at its matching square partner. The '
                       'four mast staves, base infill, internal spacers, and '
                       'head plug are separate editable objects.\n')
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE / 'Goat_Island_Skiff.blend'))
    print('Square mast detail render complete.', flush=True)


if __name__ == '__main__':
    main()
