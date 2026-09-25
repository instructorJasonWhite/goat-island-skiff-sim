"""Build and render an editable Goat Island Skiff scene in Blender 5.x.

Run: blender --background --python build_goat_island_skiff.py
The supplied assembly text/drawings informed dimensions and details; the
result is a visual model, not a lofting or construction drawing.
"""

from pathlib import Path
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gis_hull import build_hull
from gis_interior import build_interior
from gis_rudder import build_rudder
from gis_rig import build_rig
from gis_finish import apply_finish
from gis_timber_details import build_timber_details


def clean_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for col in list(bpy.data.collections):
        if col.name != bpy.context.scene.collection.name:
            bpy.data.collections.remove(col)
    working = bpy.data.collections.new('Build objects')
    bpy.context.scene.collection.children.link(working)
    bpy.context.view_layer.active_layer_collection = (
        bpy.context.view_layer.layer_collection.children[working.name]
    )


def collection(name, objects):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    for obj in objects:
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        col.objects.link(obj)
    return col


def simple_material(name, color, roughness=0.5, metallic=0.0, coat=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    if 'Coat Weight' in bsdf.inputs:
        bsdf.inputs['Coat Weight'].default_value = coat
        bsdf.inputs['Coat Roughness'].default_value = 0.19
    return mat


def wood_material(name, dark, light, roughness=0.33):
    mat = simple_material(name, light, roughness, 0.0, .31)
    nt = mat.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.location = (-800, -50)
    stretch = nt.nodes.new('ShaderNodeVectorMath')
    stretch.operation = 'MULTIPLY'
    stretch.inputs[1].default_value = (.55, 12.0, 9.0)
    stretch.location = (-600, -50)
    nt.links.new(tc.outputs['Generated'], stretch.inputs[0])
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.location = (-380, -50)
    noise.inputs['Scale'].default_value = 5.0
    noise.inputs['Detail'].default_value = 3.0
    noise.inputs['Roughness'].default_value = .62
    nt.links.new(stretch.outputs['Vector'], noise.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.location = (-130, -50)
    ramp.color_ramp.elements[0].position = .21
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].position = .78
    ramp.color_ramp.elements[1].color = (*light, 1)
    nt.links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    return mat


def make_materials():
    fir = wood_material('Clear varnished fir | warm straight grain',
                        (.27, .125, .041), (.59, .355, .142),
                        roughness=.35)
    flat_white = simple_material('TotalBoat Wet Edge | Flat White | interior',
                                 (.88, .88, .86), roughness=.82)
    largo_blue = simple_material('TotalBoat Wet Edge | Largo Blue | exterior',
                                 (.01444, .07819, .23074),
                                 roughness=.22, coat=.36)
    mats = {
        'wood': fir, 'wood_light': fir, 'wood_dark': fir,
        'deck_wood': fir, 'trim': fir, 'fir': fir,
        'paint_inside': flat_white, 'paint_outside': largo_blue,
        'navy': largo_blue, 'ivory': largo_blue,
        'metal': simple_material('Bronze and dark steel fittings', (.24, .22, .18), .28, .7),
        'rope': simple_material('Natural running rigging', (.66, .60, .45), .7),
        'shadow': simple_material('Deep recessed timber shadow', (.027, .018, .011), .75),
        'sail': simple_material('Sailcloth | warm white', (.82, .82, .78), .77),
        'sail_alt': simple_material('Sailcloth | second panel', (.76, .77, .75), .77),
        'stitch': simple_material('Sail seams and tapes', (.72, .72, .69), .85),
        'stage': simple_material('Warm slate presentation stage', (.085, .105, .115), .65),
        'backdrop': simple_material('Cool neutral backdrop', (.47, .51, .54), .87),
    }
    water = simple_material('Deep blue-grey water', (.012, .034, .055), .31, 0.0, .12)
    nt = water.node_tree
    bsdf = nt.nodes.get('Principled BSDF')
    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.location = (-540, -160)
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.location = (-330, -160)
    noise.inputs['Scale'].default_value = 2.6
    noise.inputs['Detail'].default_value = 3.0
    nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.location = (-120, -160)
    bump.inputs['Strength'].default_value = .38
    bump.inputs['Distance'].default_value = .032
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    mats['water'] = water
    return mats


def cube(name, location, scale, mat, bevel=.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Edge softening', 'BEVEL')
        mod.width = bevel
        mod.segments = 2
        obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj


def aim(obj, point):
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()


def camera(name, location, target, scale):
    cam = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)
    cam.type = 'ORTHO'
    cam.ortho_scale = scale
    cam.lens = 50
    return obj


def area_light(name, location, target, energy, size, color=(1, 1, 1)):
    light = bpy.data.lights.new(name, 'AREA')
    light.energy = energy
    light.shape = 'DISK'
    light.size = size
    light.color = color
    obj = bpy.data.objects.new(name, light)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)
    return obj


def presentation(materials):
    objs = []
    objs.append(cube('Presentation plinth', (0, 0, -.84),
                     (6.20, 2.6, .10), materials['stage'], .055))
    # Four unobtrusive display supports leave the centerboard and rudder clear.
    for x in (-1.16, 1.18):
        for y in (-.33, .33):
            objs.append(cube(f'Cradle support {x:+.2f} {y:+.2f}',
                             (x, y, -.44), (.12, .12, .69),
                             materials['stage'], .027))
    objs.append(cube('Studio floor', (0, 0, -.995),
                     (200, 200, .20), materials['backdrop']))
    return objs


def water_surface(materials):
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, .14))
    obj = bpy.context.object
    obj.name = 'Dark rippled water | display surface'
    obj.data.materials.append(materials['water'])
    return obj


def add_info_text():
    info = bpy.data.texts.new('READ ME - Goat Island Skiff')
    info.write(
        'GOAT ISLAND SKIFF - EDITABLE VISUAL MODEL\n'
        'Units: metres. +X bow, -X stern, -Y port, +Y starboard.\n'
        'HULL: 4.7 m overall length, 1.5 m beam. The drawing sheet 3 '
        'bottom-panel offsets and sheet 4 bulkhead widths guided the hull. '
        'Flat plywood offsets are not direct 3D stations, so this surface '
        'remains a visual approximation.\n'
        'COCKPIT: open floor with bow and stern tank tops and a transverse '
        '310 mm middle thwart. Bulkhead 2 has one opening; bulkhead 3 has '
        'two. The 757 mm centrecase holds a sliding daggerboard. The '
        'outer gunwale and inner inwale are separated by discrete spacer '
        'blocks.\n'
        'RUDDER: separate 22 mm sliding timber blade in a two-cheek stock, '
        'retained by shock cord. Select the movable rudder blade controller '
        'and raise it along Z to show the lifting action.\n'
        'FINISH: TotalBoat Wet Edge Flat White inside and Largo Blue on the '
        'exterior, including the bottom. Clear varnished fir on rails, '
        'breasthook, quarter knees, tank tops, rudder, centerboard, tiller, '
        'mast, yard and boom. Digital colors are visual approximations of '
        'the named product swatches.\n'
        'RIG: The drawing sheet 8 hollow square mast option is 4.730 m '
        'long, built from four 12 mm fir staves with an 82 mm square '
        'body, a 70 mm foot, and a 47.1 mm head. It includes a '
        'solid base infill and top plug, with square mast step and '
        'partner openings. The yard is 3.601 m and boom 3.548 m. '
        'Sail sheet 9 four corners and its five dimensions '
        'give 9.680 m2 projected area. The fabric mesh has illustrative '
        'camber.\n'
        'Collections separate hull, sliding rudder, rig, and presentation. '
        'Hide 02 Balanced lug rig for a clear cockpit view. Four cameras '
        'provide full sail, cockpit, bow, and rudder views.\n'
        'Reference: the user-supplied GIS Assembly Final text and drawings '
        'PDFs, plus three reference photographs.\n'
        'This is a visual design model and must not be used as boatbuilding '
        'or structural plans.\n'
    )


def main():
    clean_scene()
    scene = bpy.context.scene
    draft = os.environ.get('GIS_DRAFT', '') == '1'
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 12 if draft else 48
    scene.cycles.use_denoising = True
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.film_transparent = False
    scene.render.resolution_x = 900 if draft else 1600
    scene.render.resolution_y = 700 if draft else 1250
    scene.render.image_settings.color_mode = 'RGBA'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1
    scene.render.filepath = str(HERE / ('draft_full.png' if draft else 'Goat_Island_Skiff_render.png'))
    scene.world.color = (.40, .45, .50)
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (.42, .46, .50, 1)
    bg.inputs['Strength'].default_value = .45

    materials = make_materials()
    hull = build_hull(materials)
    replaced_hull_parts = (
        'GIS | forward buoyancy bulkhead',
        'GIS | centreboard',
        'GIS | partly lowered centreboard',
        'GIS | removable centre thwart',
        'GIS | port thwart support', 'GIS | starboard thwart support',
        'GIS | port cockpit side seat', 'GIS | starboard cockpit side seat',
        'GIS | port seat lip', 'GIS | starboard seat lip',
        'GIS | stowed',
        'GIS | timber rudder blade', 'GIS | rudder stock',
        'GIS | rudder gudgeon', 'GIS | curved varnished tiller',
        'GIS | tiller hand grip',
        'GIS | port ivory waterline', 'GIS | starboard ivory waterline',
        'GIS | transom blue edge',
        'GIS | port plank seam', 'GIS | starboard plank seam',
        'GIS | cockpit floor plank seam',
    )
    for obj in list(hull):
        if obj.name.startswith(replaced_hull_parts):
            hull.remove(obj)
            bpy.data.objects.remove(obj, do_unlink=True)
    hull.extend(build_interior(materials))
    hull.extend(build_timber_details(materials))
    apply_finish(hull, materials)
    rudder = build_rudder(materials)
    rig = build_rig(materials)
    stage = presentation(materials)
    water = water_surface(materials)
    collection('01 Hull, cockpit and appendages', hull)
    collection('01a Sliding rudder and shock cord', rudder)
    rig_col = collection('02 Balanced lug rig', rig)
    stage_col = collection('03 Optional studio display stand', stage)
    collection('04 Water setting', [water])
    studio_floor = next(obj for obj in stage if obj.name == 'Studio floor')

    main_cam = camera('Camera | full sail three-quarter',
                      (-7.6, -10.4, 5.3), (0, 0, 2.65), 10.5)
    cockpit_cam = camera('Camera | cockpit detail',
                         (-4.7, -6.1, 6.9), (0, 0, .48), 5.8)
    bow_cam = camera('Camera | triangular foredeck and fair sheer',
                     (4.2, -3.2, 3.0), (1.52, 0, .50), 3.15)
    rudder_cam = camera('Camera | sliding rudder and shock cord',
                        (-4.5, -2.7, 2.0), (-2.30, 0, .32), 2.35)
    light_objs = [
        area_light('Key softbox', (-3, -5, 8.8), (0, 0, 2), 1500, 6.0),
        area_light('Fill softbox', (4, 5, 6.5), (0, 0, 2), 1100, 5.5,
                   (.77, .85, 1.0)),
        area_light('Sail rim softbox', (-5, 4, 8.5), (0, 0, 3), 900, 4.0,
                   (1.0, .85, .69)),
    ]
    collection('05 Cameras and softboxes',
               [main_cam, cockpit_cam, bow_cam, rudder_cam, *light_objs])
    add_info_text()
    scene['Boat'] = 'Goat Island Skiff'
    scene['Overall length (m)'] = 4.7
    scene['Beam (m)'] = 1.5
    scene['Sail plan area (m2)'] = 9.68
    scene['Interior finish'] = 'TotalBoat Wet Edge Flat White'
    scene['Exterior and bottom finish'] = 'TotalBoat Wet Edge Largo Blue'
    scene['Wood finish'] = 'Clear varnished fir'
    scene['Mast construction'] = 'Hollow square fir mast, four 12 mm staves'
    scene['Model purpose'] = 'Visualisation; not construction plans'

    for obj in stage_col.objects:
        obj.hide_render = True
        obj.hide_set(True)

    if os.environ.get('GIS_SKIP_RENDERS', '') == '1':
        scene.camera = main_cam
        bpy.context.view_layer.objects.active = None
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE / 'Goat_Island_Skiff.blend'))
        print('Saved updated boat model without presentation renders', flush=True)
        return

    # Preview the full rig first.
    scene.camera = main_cam
    scene.render.filepath = str(HERE / ('draft_full.png' if draft else 'Goat_Island_Skiff_render.png'))
    print('Rendering full rig...', flush=True)
    bpy.ops.render.render(write_still=True)

    # Clear, high angle cockpit preview. Keep the saved scene rig visible.
    for obj in rig_col.objects:
        obj.hide_render = True
    water.hide_render = True
    studio_floor.hide_render = False
    studio_floor.hide_set(False)
    scene.view_settings.exposure = -0.55
    scene.camera = cockpit_cam
    scene.render.resolution_x = 900 if draft else 1600
    scene.render.resolution_y = 590 if draft else 1050
    scene.render.filepath = str(HERE / ('draft_cockpit.png' if draft else 'Goat_Island_Skiff_cockpit.png'))
    print('Rendering cockpit...', flush=True)
    bpy.ops.render.render(write_still=True)
    scene.render.resolution_x = 850 if draft else 1200
    scene.render.resolution_y = 640 if draft else 900
    scene.camera = bow_cam
    scene.render.filepath = str(HERE / ('draft_bow.png' if draft else 'Goat_Island_Skiff_bow.png'))
    print('Rendering bow detail...', flush=True)
    bpy.ops.render.render(write_still=True)
    scene.camera = rudder_cam
    scene.render.filepath = str(HERE / ('draft_rudder.png' if draft else 'Goat_Island_Skiff_rudder.png'))
    print('Rendering rudder detail...', flush=True)
    bpy.ops.render.render(write_still=True)
    for obj in rig_col.objects:
        obj.hide_render = False
    water.hide_render = False
    studio_floor.hide_render = True
    studio_floor.hide_set(True)
    scene.view_settings.exposure = 0

    scene.camera = main_cam
    scene.render.resolution_x = 900 if draft else 1600
    scene.render.resolution_y = 700 if draft else 1250
    scene.render.filepath = str(HERE / ('draft_full.png' if draft else 'Goat_Island_Skiff_render.png'))
    bpy.context.view_layer.objects.active = None
    if not draft:
        bpy.ops.wm.save_as_mainfile(filepath=str(HERE / 'Goat_Island_Skiff.blend'))
    print('Saved renders to', HERE, flush=True)


if __name__ == '__main__':
    main()
