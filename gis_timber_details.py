"""Visible varnished-fir breasthook and quarter knees for the GIS model.

Distances are metres.  X points to the bow, Y to starboard, Z upward.
The plan shapes follow figure 16 on page 35 of the supplied GIS assembly
manual.  They are visual details aligned to ``gis_hull``'s assembled sheer,
not replacement cutting templates for the construction drawings.
"""

import bpy

from gis_hull import BOW_X, LOA, _profile


def _timber_plate(name, outline, thickness, material):
    """Make a solid plate from a four-point plan outline with varying Z."""
    count = len(outline)
    vertices = list(outline)
    vertices.extend((x, y, z-thickness) for x, y, z in outline)

    # Keep the specified point sequence.  Both concave aft edges are visible
    # from point zero, so a two-triangle fan preserves their slight hollow.
    signed_area = sum(
        outline[i][0]*outline[(i+1) % count][1]
        - outline[(i+1) % count][0]*outline[i][1]
        for i in range(count)
    )
    upward = signed_area > 0
    faces = []
    for i in range(1, count-1):
        faces.append((0, i, i+1) if upward else (0, i+1, i))
        faces.append((count, count+i+1, count+i) if upward
                     else (count, count+i, count+i+1))
    for i in range(count):
        j = (i+1) % count
        faces.append((i, j, count+j, count+i) if upward
                     else (i, count+i, count+j, j))

    mesh = bpy.data.meshes.new(name + " Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    # The manual calls for lightly eased edges on these exposed timbers.
    bevel = obj.modifiers.new("Softened fir edges", "BEVEL")
    bevel.width = 0.003
    bevel.segments = 3
    bevel.limit_method = "ANGLE"
    return obj


def build_timber_details(materials):
    """Return three finished fir details, aligned to the existing hull.

    ``materials['fir']`` must be a Blender Material.  This function creates
    one bow breasthook and port/starboard stern quarter knees, and does not
    create or change scene settings, cameras, lights, or materials.
    """
    fir = materials["fir"]
    objects = []

    # Figure 16: bow knee approximately 193 mm fore-to-aft and 172 mm wide.
    # Its aft edge has the slight concavity called out on page 36.  The top
    # lies a few millimetres below the 12 mm raised tops of the gunwales.
    bow_back_x = BOW_X - 0.193
    bow_back_z = _profile(0.193)[4] + 0.008
    bow_hollow_x = bow_back_x + 0.012
    bow_outline = [
        (BOW_X, 0.0, _profile(0.0)[4] + 0.008),
        (bow_back_x, 0.086, bow_back_z),
        (bow_hollow_x, 0.0, _profile(BOW_X-bow_hollow_x)[4] + 0.008),
        (bow_back_x, -0.086, bow_back_z),
    ]
    objects.append(_timber_plate("GIS | varnished fir breasthook",
                                 bow_outline, 0.019, fir))

    # Figure 16: each quarter knee projects about 200 mm forward from the
    # transom and 172 mm inboard from the inwale.  A shallow incurve on its
    # free edge keeps the shape distinct from the low aft buoyancy tank top.
    transom_s = LOA
    forward_s = LOA - 0.200
    transom_x = BOW_X - transom_s + 0.004
    forward_x = BOW_X - forward_s
    transom_half_sheer = _profile(transom_s)[1]
    forward_half_sheer = _profile(forward_s)[1]
    transom_top = _profile(transom_s)[4] + 0.008
    forward_top = _profile(forward_s)[4] + 0.008
    outer_at_transom = transom_half_sheer - 0.052
    outer_forward = forward_half_sheer - 0.052
    for sign, side_name in ((-1, "port"), (1, "starboard")):
        outline = [
            (transom_x, sign*outer_at_transom, transom_top),
            (forward_x, sign*outer_forward, forward_top),
            (transom_x+0.085,
             sign*(outer_at_transom-0.074),
             0.50*(transom_top+forward_top)),
            (transom_x, sign*(outer_at_transom-0.172), transom_top),
        ]
        objects.append(_timber_plate("GIS | %s varnished fir quarter knee" %
                                     side_name, outline, 0.019, fir))

    return objects
