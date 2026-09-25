"""The Goat Island Skiff's liftable, shock-cord-retained transom rudder.

Coordinates and materials match ``build_goat_island_skiff.py``: metres,
+X toward the bow, Y to starboard, Z up.  This module does not build a
transom or alter another model component; call ``build_rudder(materials)``
after building the hull, and put its returned objects in a rudder collection.

Source: GIS assembly drawings, PDF page 6 ("Rudder Stock"); assembly text,
PDF pages 63-64 (blade outline and 22 mm foil) and 72 (stock assembly).
The drawing's millimetre callouts drive the dimensions below.  The exact
stock mounting height, blade immersion, cord route, and hardware shapes are
visual approximations fitted to the supplied model's transom.
"""

from math import cos, pi, sin


TRANSOM_X = -2.350
STOCK_AFT_X = TRANSOM_X - 0.244
# The 49 mm transom tiller slot begins about 135 mm below the 0.64 m sheer.
# Its centre is therefore around 0.480 m, with the cheek top just above it.
STOCK_TOP_FORE = 0.515
STOCK_BOTTOM_FORE = STOCK_TOP_FORE - 0.272
STOCK_TOP_AFT = STOCK_TOP_FORE + 0.016
STOCK_BOTTOM_AFT = STOCK_BOTTOM_FORE + 0.148

BLADE_TOP_Z = 0.790
BLADE_BOTTOM_Z = BLADE_TOP_Z - 1.000
BLADE_LEADING_TOP_X = -2.455  # inboard/forward edge, +X
BLADE_CHORD = 0.260
BLADE_RAKE = 0.120           # aftward travel from head to foot


def rudder_dimensions():
    """Return the plan dimensions used by this visual component, in metres."""
    return {
        "blade_thickness": 0.022,
        "blade_height": 1.000,
        "blade_chord": BLADE_CHORD,
        "blade_foot_taper": 0.040,
        "stock_chord": 0.244,
        "stock_depth": 0.272,
        "stock_aft_lower_rise": 0.148,
        "stock_aft_upper_rise": 0.016,
        "tiller_reach": 1.297,
        "stock_slot": 0.024,
    }


def _blade_edges(z):
    """Leading and trailing X for the inclined, 260 mm chord blade."""
    progress = (BLADE_TOP_Z - z) / 1.000
    leading = BLADE_LEADING_TOP_X - BLADE_RAKE * progress
    trailing = leading - BLADE_CHORD
    # The last 200 mm of the trailing edge cuts in by 40 mm (text p.63).
    trailing += 0.040 * max(0.0, min(1.0, (BLADE_BOTTOM_Z + .200 - z) / .200))
    return leading, trailing


def _blade_outline():
    """Side elevation of the static, partly lowered blade, in X,Z."""
    top_lead, top_trail = _blade_edges(BLADE_TOP_Z)
    shoulder_z = BLADE_BOTTOM_Z + 0.200
    shoulder_lead, shoulder_trail = _blade_edges(shoulder_z)
    foot_lead, foot_trail = _blade_edges(BLADE_BOTTOM_Z)
    return [
        (top_lead, BLADE_TOP_Z),
        (top_trail, BLADE_TOP_Z),
        (shoulder_trail, shoulder_z),
        (foot_trail, BLADE_BOTTOM_Z),
        (foot_lead, BLADE_BOTTOM_Z),
        (shoulder_lead, shoulder_z),
    ]


def _stock_outline():
    """The drawing's 244 x 272 mm cheek, with its rounded lower aft corner."""
    return [
        (TRANSOM_X, STOCK_TOP_FORE),
        (STOCK_AFT_X, STOCK_TOP_AFT),
        (STOCK_AFT_X, STOCK_BOTTOM_AFT + .046),
        (STOCK_AFT_X + .006, STOCK_BOTTOM_AFT + .027),
        (STOCK_AFT_X + .020, STOCK_BOTTOM_AFT + .010),
        (STOCK_AFT_X + .040, STOCK_BOTTOM_AFT),
        (TRANSOM_X, STOCK_BOTTOM_FORE),
    ]


def _mesh(name, vertices, faces, material):
    import bpy

    mesh = bpy.data.meshes.new(name + " mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _plate_xz(name, outline, y0, y1, material, bevel=0):
    n = len(outline)
    vertices = [(x, y0, z) for x, z in outline]
    vertices += [(x, y1, z) for x, z in outline]
    faces = [tuple(range(n-1, -1, -1)), tuple(range(n, n*2))]
    faces += [(i, (i+1) % n, (i+1) % n + n, i+n) for i in range(n)]
    obj = _mesh(name, vertices, faces, material)
    if bevel:
        mod = obj.modifiers.new("Soft timber edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def _box(name, x0, x1, y0, y1, z0, z1, material):
    vertices = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    faces = [(3,2,1,0), (4,5,6,7), (0,1,5,4), (1,2,6,5),
             (2,3,7,6), (3,0,4,7)]
    return _mesh(name, vertices, faces, material)


def _line(name, points, radius, material, cyclic=False):
    import bpy

    curve = bpy.data.curves.new(name + " curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    spline.points.add(len(points)-1)
    for p, xyz in zip(spline.points, points):
        p.co = (*xyz, 1.0)
    spline.use_cyclic_u = cyclic
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    return obj


def _round_bolt(name, x, z, y0, y1, radius, material):
    import bpy
    from mathutils import Vector

    start = Vector((x, y0, z))
    end = Vector((x, y1, z))
    delta = end - start
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius,
                                        depth=delta.length,
                                        location=(start+end)/2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(material)
    return obj


def _tiller(name, material):
    """Tapered 1297 mm inboard tiller, passing over the transom cutout."""
    xz = [
        (STOCK_AFT_X + .038, .482, .047, .039),
        (TRANSOM_X, .481, .043, .036),
        (TRANSOM_X + .400, .512, .037, .033),
        (TRANSOM_X + .850, .544, .032, .028),
        (TRANSOM_X + 1.297, .569, .027, .025),
    ]
    vertices = []
    for x, z, width, height in xz:
        vertices.extend([
            (x, -width/2, z-height/2), (x, width/2, z-height/2),
            (x, width/2, z+height/2), (x, -width/2, z+height/2),
        ])
    faces = [(3,2,1,0), tuple(range(4*(len(xz)-1), 4*len(xz)))]
    for i in range(len(xz)-1):
        for j in range(4):
            a, b = 4*i+j, 4*i+(j+1)%4
            faces.append((a,b,b+4,a+4))
    obj = _mesh(name, vertices, faces, material)
    mod = obj.modifiers.new("Rounded tiller edges", "BEVEL")
    mod.width = .005
    mod.segments = 2
    obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def _parent_keep_world(obj, controller):
    world = obj.matrix_world.copy()
    obj.parent = controller
    obj.matrix_world = world


def build_rudder(materials):
    """Build and return all objects of the GIS sliding rudder assembly.

    Requires the same ``wood_light``, ``wood_dark``, ``trim``, ``metal``,
    ``rope``, and ``shadow`` materials supplied to ``build_hull``.  The blade
    and its handle are parented to a movable empty for interactive lifting.
    Moving that empty +Z and slightly +X raises the blade within its stock.
    """
    import bpy

    mat = {key: materials[key] for key in (
        "wood_light", "wood_dark", "trim", "metal", "rope", "shadow")}
    objects = []
    add = objects.append

    # Two 12 mm cheeks leave a 24 mm central slot for the 22 mm blade.
    cheek = _stock_outline()
    add(_plate_xz("GIS rudder | port stock cheek", cheek,
                  -.024, -.012, mat["wood_light"], .003))
    add(_plate_xz("GIS rudder | starboard stock cheek", cheek,
                  .012, .024, mat["wood_light"], .003))
    add(_box("GIS rudder | dark slot mouth", STOCK_AFT_X + .012,
             TRANSOM_X - .037, -.0117, .0117,
             STOCK_TOP_FORE - .006, STOCK_TOP_FORE, mat["shadow"]))
    # The front spacer accepts the two sets of fitting bolts (drawing p.6).
    add(_box("GIS rudder | 24 x 45 stock spacer", TRANSOM_X-.047,
             TRANSOM_X-.023, -.012, .012,
             STOCK_BOTTOM_FORE+.014, STOCK_TOP_FORE-.015,
             mat["wood_dark"]))
    add(_box("GIS rudder | upper stock cross spacer", TRANSOM_X-.073,
             TRANSOM_X-.053, -.012, .012,
             STOCK_TOP_AFT-.037, STOCK_TOP_AFT-.018,
             mat["wood_dark"]))

    # The visual blade is set part-way down; it remains a separate, liftable
    # 22 mm foil.  The last 200 mm of the trailing edge tapers by 40 mm.
    controller = bpy.data.objects.new(
        "GIS rudder | move to lift or kick back blade", None)
    bpy.context.collection.objects.link(controller)
    controller.location = (-2.62, 0, .47)
    controller.empty_display_type = "ARROWS"
    controller.empty_display_size = .10
    controller["movement"] = "Raise along +Z and slightly +X; shock cord allows kickback"
    add(controller)
    blade_parts = []
    blade_parts.append(_plate_xz("GIS rudder | 22 mm sliding timber blade",
                                 _blade_outline(), -.011, .011,
                                 mat["wood_light"], .004))
    for sign, side in ((-1, "port"), (1, "starboard")):
        y = sign*.0128
        for fraction in (.20, .40, .60, .80):
            seam = []
            for z in (BLADE_TOP_Z-.018, .54, .29, .04, BLADE_BOTTOM_Z+.025):
                lead, trail = _blade_edges(z)
                x = lead + fraction*(trail-lead)
                seam.append((x, y, z))
            blade_parts.append(_line("GIS rudder | %s blade stave seam %.2f" %
                                     (side, fraction), seam, .0015,
                                     mat["wood_dark"]))
        # Two top lifting holes follow the two holes on the foil drawing.
        for k, x in enumerate((-2.650, -2.525)):
            blade_parts.append(_round_bolt(
                "GIS rudder | %s lifting eye %d" % (side, k+1),
                x, BLADE_TOP_Z-.041,
                sign*.0113, sign*.0143, .010, mat["shadow"]))
        # The hardwood leading stave has a contrasting, narrow varnished edge.
        edge = []
        for z in (BLADE_TOP_Z-.005, .54, .29, .04, BLADE_BOTTOM_Z+.005):
            lead, _ = _blade_edges(z)
            edge.append((lead+.001, sign*.006, z))
        blade_parts.append(_line("GIS rudder | %s hardwood leading edge" % side,
                                 edge, .004, mat["trim"]))
    blade_parts.append(_line("GIS rudder | lifting loop through blade head",
                             [(-2.650, -.013, BLADE_TOP_Z-.041),
                              (-2.652, -.018, BLADE_TOP_Z+.020),
                              (-2.588, -.018, BLADE_TOP_Z+.054),
                              (-2.525, -.018, BLADE_TOP_Z+.020),
                              (-2.525, -.013, BLADE_TOP_Z-.041)],
                             .004, mat["rope"]))
    for obj in blade_parts:
        _parent_keep_world(obj, controller)
        add(obj)

    # Wide metal straps and cross bolts on both cheeks follow RF239/RF254.
    for sign, side in ((-1, "port"), (1, "starboard")):
        y0, y1 = ((-.030, -.025) if sign < 0 else (.025, .030))
        upper = [(-2.574, .493), (-2.390, .474),
                 (-2.390, .453), (-2.574, .472)]
        lower = [(-2.558, .416), (-2.390, .297),
                 (-2.390, .275), (-2.558, .395)]
        add(_plate_xz("GIS rudder | %s RF239 upper strap" % side,
                      upper, y0, y1, mat["metal"], .001))
        add(_plate_xz("GIS rudder | %s RF254 lower strap" % side,
                      lower, y0, y1, mat["metal"], .001))
        for x,z in ((-2.545,.482),(-2.408,.463),
                    (-2.536,.405),(-2.408,.288)):
            add(_round_bolt("GIS rudder | %s strap bolt" % side,
                            x,z,sign*.031,sign*.034,.008,mat["metal"]))

    # Two transom hinges: stock-side pintle eyes and smaller transom-side
    # backing pads.  Their pin axes are vertical, like the drawing/photo.
    for z, label in ((.282, "lower"), (.463, "upper")):
        add(_box("GIS rudder | %s transom backing plate" % label,
                 TRANSOM_X-.005, TRANSOM_X+.005,
                 -.044,.044,z-.021,z+.021,mat["metal"]))
        eye = []
        for i in range(25):
            angle = 2*pi*i/24
            eye.append((TRANSOM_X-.031+.020*cos(angle),
                        .020*sin(angle), z))
        add(_line("GIS rudder | %s gudgeon eye" % label,
                  eye,.005,mat["metal"],cyclic=False))
        add(_line("GIS rudder | %s pintle pin" % label,
                  [(TRANSOM_X-.031,0,z-.030),
                   (TRANSOM_X-.031,0,z+.030)],.006,mat["metal"]))

    # The plan states a tight elastic shock cord around the stock before
    # inserting the blade.  The loop bows aft around the blade's trailing
    # edge, holding its selected height while yielding to an impact.
    zc = .428
    _, blade_trail = _blade_edges(zc)
    aft_loop_x = blade_trail - .021
    cord = [
        (TRANSOM_X-.030,-.034,zc),
        (STOCK_AFT_X+.040,-.034,zc),
        (aft_loop_x,-.034,zc),
        (aft_loop_x-.012,-.022,zc),
        (aft_loop_x-.016,0,zc),
        (aft_loop_x-.012,.022,zc),
        (aft_loop_x,.034,zc),
        (STOCK_AFT_X+.040,.034,zc),
        (TRANSOM_X-.030,.034,zc),
        (TRANSOM_X-.023,0,zc),
    ]
    add(_line("GIS rudder | elastic shock cord retention loop",
              cord,.0035,mat["shadow"],cyclic=True))
    add(_line("GIS rudder | shock cord knot",
              [(TRANSOM_X-.105,-.035,zc),
               (TRANSOM_X-.092,-.052,zc+.018),
               (TRANSOM_X-.078,-.040,zc+.004)],
              .004,mat["shadow"]))

    add(_tiller("GIS rudder | laminated 1297 mm tiller",mat["wood_dark"]))
    add(_line("GIS rudder | tiller end grip",
              [(TRANSOM_X+1.18,0,.561),
               (TRANSOM_X+1.297,0,.569)],.017,mat["trim"]))
    return objects
