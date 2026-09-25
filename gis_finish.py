"""Apply the requested paint and varnished-fir finish to the GIS model.

The TotalBoat Wet Edge color selections are Flat White (inside) and Largo
Blue (outside).  The Blender colors are a visual match to the published
swatches, rather than calibrated paint samples.
"""

import bmesh
import bpy


def _set_material(obj, material, role):
    if obj.type not in {'MESH', 'CURVE'}:
        return
    obj.data.materials.clear()
    obj.data.materials.append(material)
    if obj.type == 'MESH':
        for polygon in obj.data.polygons:
            polygon.material_index = 0
    obj['finish'] = role


def apply_finish(hull_objects, materials):
    """Paint hull skins and plywood; leave the named woodwork as fir."""
    outside = materials['paint_outside']
    inside = materials['paint_inside']
    outside_exact = {
        'GIS | navy outer bottom',
        'GIS | broad timber transom with tiller slot',
        'GIS | laminated bow stem',
    }
    inside_exact = {
        'GIS | varnished inner bottom',
        'GIS | aft buoyancy bulkhead',
        'GIS | Bhd 2 with plan cutout',
        'GIS | Bhd 3 with paired plan cutouts',
        'GIS | centrecase forward triangular gusset',
    }
    for obj in hull_objects:
        name = obj.name
        if (name in outside_exact
                or 'varnished side and blue lower band' in name
                or name.endswith('chine batten')
                or name.endswith('bottom runner')):
            _set_material(obj, outside, 'Wet Edge Largo Blue outside')
        elif (name in inside_exact
              or name.endswith('inner side')
              or name.endswith('daggerboard slot lining')
              or 'centrecase' in name and 'plywood side' in name
              or name.startswith('GIS | port frame ')
              or name.startswith('GIS | starboard frame ')):
            _set_material(obj, inside, 'Wet Edge Flat White inside')
        elif obj.type in {'MESH', 'CURVE'} and any(
                mat == materials['fir'] for mat in obj.data.materials):
            obj['finish'] = 'Clear varnished fir'

    # The transom is a thin plywood surface.  A second sheet faces inward so
    # the blue exterior and white cockpit can be inspected independently.
    transom = bpy.data.objects['GIS | broad timber transom with tiller slot']
    inside_face = transom.copy()
    inside_face.data = transom.data.copy()
    inside_face.name = 'GIS | Flat White inside transom face'
    inside_face.location.x += .002
    bpy.context.collection.objects.link(inside_face)
    mesh_edit = bmesh.new()
    mesh_edit.from_mesh(inside_face.data)
    bmesh.ops.reverse_faces(mesh_edit, faces=mesh_edit.faces)
    mesh_edit.to_mesh(inside_face.data)
    mesh_edit.free()
    inside_face.data.update()
    _set_material(inside_face, inside, 'Wet Edge Flat White inside')
    hull_objects.append(inside_face)
    return hull_objects
