"""Goat Island Skiff hull and cockpit for a Blender scene.

All distances are metres.  X points toward the bow, Y to starboard, and Z
up.  ``build_hull(materials)`` leaves scene, camera, lights, and materials to
the caller and returns every object it creates.

The bottom half widths below come from the supplied GIS assembly drawing.
The assembled flare, rocker, sheer, and fittings are visual approximations,
not a set of construction plans.
"""

from bisect import bisect_right
from math import cos, exp, pi, sin

import bpy
from mathutils import Vector


# Distance aft from the 4.70 m bow, followed by measured half widths of the
# developed bottom panel.  The final 44 mm to the transom keeps its width.
BOTTOM_STATIONS = [i * 0.30 for i in range(16)] + [4.656, 4.700]
BOTTOM_HALF_WIDTHS = [
    0.000, 0.079, 0.155, 0.225, 0.289, 0.345, 0.393, 0.433,
    0.465, 0.488, 0.503, 0.509, 0.504, 0.487, 0.459, 0.418,
    0.393, 0.393,
]
LOA = 4.70
BOW_X = LOA / 2
BOARD_SLOT_AFT_X = -.314
BOARD_SLOT_FORE_X = .371
BOARD_SLOT_HALF_WIDTH = .0125


def _interpolate(xs, ys, x):
    """Shape-preserving cubic interpolation through the measured offsets.

    The drawing's points remain exact, while the derivatives at each station
    agree on both sides.  The monotone slopes avoid a bulge beside the bow.
    """
    x = max(xs[0], min(xs[-1], x))
    i = min(len(xs) - 2, max(0, bisect_right(xs, x) - 1))
    widths = [xs[j + 1] - xs[j] for j in range(len(xs) - 1)]
    secants = [(ys[j + 1] - ys[j]) / widths[j]
                for j in range(len(widths))]

    def endpoint(first, second, h_first, h_second):
        slope = ((2*h_first + h_second)*first - h_first*second) / (h_first+h_second)
        if slope*first <= 0:
            return 0.0
        if first*second < 0 and abs(slope) > 3*abs(first):
            return 3*first
        return slope

    slopes = [endpoint(secants[0], secants[1], widths[0], widths[1])]
    for j in range(1, len(xs)-1):
        before, after = secants[j-1], secants[j]
        if before*after <= 0:
            slopes.append(0.0)
        else:
            w_before = 2*widths[j] + widths[j-1]
            w_after = widths[j] + 2*widths[j-1]
            slopes.append((w_before+w_after) /
                          (w_before/before + w_after/after))
    slopes.append(endpoint(secants[-1], secants[-2],
                           widths[-1], widths[-2]))

    h = widths[i]
    t = (x - xs[i]) / h
    return ((2*t**3 - 3*t**2 + 1)*ys[i]
            + (t**3 - 2*t**2 + t)*h*slopes[i]
            + (-2*t**3 + 3*t**2)*ys[i+1]
            + (t**3 - t**2)*h*slopes[i+1])


def _profile(s):
    """Return chine half beam, sheer half beam, and bottom/chine/sheer Z."""
    s = max(0.0, min(LOA, s))
    chine = _interpolate(BOTTOM_STATIONS, BOTTOM_HALF_WIDTHS, s)
    # Exponential taper has a finite opening angle at the stem and eases
    # steadily aft.  A squared exponent starts flat, then accelerates, which
    # makes an S-shaped shoulder in the first metre of the sheer.
    bow_taper = 1.0 - exp(-s / 0.35)
    flare = (0.1825 + 0.07 * sin(pi * s / LOA)) * bow_taper
    sheer_beam = chine + flare
    rocker = abs(s - 2.25) / 2.35
    bottom_z = 0.015 + 0.112 * rocker ** 2.2
    bottom_z += 0.13 * max(0.0, 1.0 - s / 0.95) ** 2
    chine_z = bottom_z + 0.033 * (1.0 - exp(-s / 0.25))
    sheer_z = 0.57
    sheer_z += 0.20 * max(0.0, (2.3 - s) / 2.3) ** 2
    sheer_z += 0.07 * max(0.0, (s - 2.3) / 2.4) ** 2
    return chine, sheer_beam, bottom_z, chine_z, sheer_z


def _profile_x(x):
    return _profile(BOW_X - x)


def _inside_half_beam(x, z):
    chine, sheer, _, chine_z, sheer_z = _profile_x(x)
    t = max(0.0, min(1.0, (z - chine_z) / max(0.01, sheer_z - chine_z)))
    return max(0.003, (chine + (sheer - chine) * t) - 0.022)


def _make_mesh(name, vertices, faces, materials, face_materials=None):
    mesh = bpy.data.meshes.new(name + " Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.clear()
    for mat in materials:
        mesh.materials.append(mat)
    mesh.update()
    if face_materials:
        for polygon, material_index in zip(mesh.polygons, face_materials):
            polygon.material_index = material_index
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def _loft(name, lower, upper, material, reverse_faces=False):
    vertices = lower + upper
    count = len(lower)
    faces = [(i, i + 1, count + i + 1, count + i) for i in range(count - 1)]
    if reverse_faces:
        faces = [tuple(reversed(face)) for face in faces]
    return _make_mesh(name, vertices, faces, [material])


def _curve(name, points, radius, material, smooth=False):
    curve = bpy.data.curves.new(name + " Curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 8 if smooth else 2
    curve.bevel_depth = radius
    curve.bevel_resolution = 3
    if smooth:
        spline = curve.splines.new("BEZIER")
        spline.bezier_points.add(len(points) - 1)
        for i, (point, coordinate) in enumerate(zip(spline.bezier_points, points)):
            lo, hi = max(0, i-1), min(len(points)-1, i+1)
            dx = points[hi][0] - points[lo][0]
            derivative = [(points[hi][axis] - points[lo][axis]) / dx
                          for axis in range(3)]
            before_dx = points[i][0] - points[i-1][0] if i else points[1][0]-points[0][0]
            after_dx = points[i+1][0] - points[i][0] if i < len(points)-1 else before_dx
            point.co = coordinate
            point.handle_left_type = "FREE"
            point.handle_right_type = "FREE"
            point.handle_left = tuple(coordinate[axis] - derivative[axis]*before_dx/3
                                      for axis in range(3))
            point.handle_right = tuple(coordinate[axis] + derivative[axis]*after_dx/3
                                       for axis in range(3))
    else:
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for point, coordinate in zip(spline.points, points):
            point.co = (coordinate[0], coordinate[1], coordinate[2], 1.0)
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    return obj


def _rail_basis(s, sign):
    """Sheer point and horizontal outward unit normal at distance ``s``."""
    s = max(0.0, min(LOA, s))
    step = 0.0005
    lo, hi = max(0.0, s-step), min(LOA, s+step)
    sheer_slope = (_profile(hi)[1] - _profile(lo)[1]) / (hi-lo)
    unit = (1.0 + sheer_slope*sheer_slope) ** 0.5
    _, half_beam, _, _, z = _profile(s)
    return BOW_X-s, sign*half_beam, z, sheer_slope/unit, sign/unit


def _rail_section(inner, outer, bottom, top, corner_radius):
    """Width/height outline with the exposed top corners eased to 6 mm."""
    if corner_radius <= 0:
        return [(inner, bottom), (outer, bottom),
                (outer, top), (inner, top)]
    r = min(corner_radius, (outer-inner)/2)
    section = [(inner, bottom), (outer, bottom), (outer, top-r)]
    for angle in (pi/6, pi/3, pi/2):
        section.append((outer-r+r*cos(angle), top-r+r*sin(angle)))
    section.append((inner+r, top))
    for angle in (2*pi/3, 5*pi/6, pi):
        section.append((inner+r+r*cos(angle), top-r+r*sin(angle)))
    return section


def _swept_rail(name, stations, sign, inner, outer, bottom, top,
                corner_radius, material, taper_at_stem=False):
    """One continuous timber sweep following the fair sheer centreline."""
    section = _rail_section(inner, outer, bottom, top, corner_radius)
    ring_count = len(section)
    vertices = []
    for s in stations:
        x, y, z, nx, ny = _rail_basis(s, sign)
        # Bring both halves of the outer rail into the pointed stem.
        taper = (0.025 + 0.975*(1.0 - exp(-s/0.075))) if taper_at_stem else 1.0
        vertices.extend((x + distance*taper*nx,
                         y + distance*taper*ny,
                         z + height)
                        for distance, height in section)
    faces = [tuple(range(ring_count-1, -1, -1))]
    for i in range(len(stations)-1):
        for j in range(ring_count):
            next_j = (j+1) % ring_count
            faces.append((i*ring_count+j,
                          (i+1)*ring_count+j,
                          (i+1)*ring_count+next_j,
                          i*ring_count+next_j))
    last = (len(stations)-1)*ring_count
    faces.append(tuple(last+j for j in range(ring_count)))
    # Mirroring the rail across the centreline reverses its handedness.
    if sign < 0:
        faces = [tuple(reversed(face)) for face in faces]
    return _make_mesh(name, vertices, faces, [material])


def _rod(name, a, b, radius, material, vertices=12):
    start, end = Vector(a), Vector(b)
    d = end - start
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                        depth=d.length, location=(start + end) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(material)
    return obj


def _solid_xy(name, xy, top, thickness, material):
    # A mirrored seat outline can arrive clockwise.  Keep the exposed top
    # facing upward on either side of the boat.
    area_twice = sum(
        xy[i][0]*xy[(i+1) % len(xy)][1]
        - xy[(i+1) % len(xy)][0]*xy[i][1]
        for i in range(len(xy))
    )
    if area_twice < 0:
        xy = list(reversed(xy))
    count = len(xy)
    vertices = [(x, y, top) for x, y in xy]
    vertices += [(x, y, top - thickness) for x, y in xy]
    faces = [tuple(range(count)), tuple(range(2 * count - 1, count - 1, -1))]
    faces += [
        (i, (i + 1) % count, (i + 1) % count + count, i + count)
        for i in range(count)
    ]
    return _make_mesh(name, vertices, faces, [material])


def _bulkhead(name, x, top_z, material):
    chine, _, bottom_z, chine_z, _ = _profile_x(x)
    top_half = _inside_half_beam(x, top_z)
    vertices = [
        (x, -top_half, top_z),
        (x, -max(0.003, chine - 0.015), chine_z + 0.020),
        (x, 0.0, bottom_z + 0.022),
        (x, max(0.003, chine - 0.015), chine_z + 0.020),
        (x, top_half, top_z),
    ]
    return _make_mesh(name, vertices, [tuple(range(5))], [material])


def _deck_width(x, z):
    return max(0.0, _inside_half_beam(x, z) - 0.009)


def _deck_segment(name, x_values, z_at, material, cutout_side=None,
                  cutout_half_width=0.060):
    """Solid, tapered fore or aft tank top; optional port/starboard strip."""
    verts = []
    for x in x_values:
        z = z_at(x)
        w = _deck_width(x, z)
        if cutout_side == "port":
            verts.extend([(x, -w, z), (x, -cutout_half_width, z)])
        elif cutout_side == "starboard":
            verts.extend([(x, cutout_half_width, z), (x, w, z)])
        else:
            verts.extend([(x, -w, z), (x, w, z)])
    # X increases across each strip; this winding faces the deck upward.
    faces = [(2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1)
             for i in range(len(x_values) - 1)]
    return _make_mesh(name, verts, faces, [material])


def _ring(name, centre, inner_radius, outer_radius, z, material, segments=32):
    cx, cy = centre
    verts = []
    for i in range(segments):
        a = 2 * pi * i / segments
        ca, sa = cos(a), sin(a)
        verts.append((cx + inner_radius * ca, cy + inner_radius * sa, z))
        verts.append((cx + outer_radius * ca, cy + outer_radius * sa, z))
    faces = [(2*i, 2*i+1, (2*((i+1) % segments))+1,
              2*((i+1) % segments)) for i in range(segments)]
    return _make_mesh(name, verts, faces, [material])


def _rounded_square_loop(cx, cy, half_width, corner_radius, segments=4):
    """A square outline with small, smoothly eased corners, counterclockwise."""
    radius = min(corner_radius, half_width)
    corners = ((half_width-radius, half_width-radius),
               (-half_width+radius, half_width-radius),
               (-half_width+radius, -half_width+radius),
               (half_width-radius, -half_width+radius))
    return [(cx + ox + radius*cos((corner*0.5 + j*0.5/segments)*pi),
             cy + oy + radius*sin((corner*0.5 + j*0.5/segments)*pi))
            for corner, (ox, oy) in enumerate(corners)
            for j in range(segments+1)]


def _square_socket(name, centre, outer_width, opening_width, top_z,
                   bottom_z, material, recess_floor=None):
    """Square timber partner or blind mast-step socket with rounded corners."""
    cx, cy = centre
    outside = _rounded_square_loop(cx, cy, outer_width/2, 0.007)
    inside = _rounded_square_loop(cx, cy, opening_width/2, 0.004)
    count = len(outside)
    inner_bottom = bottom_z if recess_floor is None else recess_floor
    vertices = ([(x, y, top_z) for x, y in outside] +
                [(x, y, top_z) for x, y in inside] +
                [(x, y, bottom_z) for x, y in outside] +
                [(x, y, inner_bottom) for x, y in inside])
    faces = []
    for i in range(count):
        j = (i+1) % count
        faces.extend(((i, j, count+j, count+i),
                      (2*count+i, 2*count+j, j, i),
                      (count+i, count+j, 3*count+j, 3*count+i)))
        if recess_floor is None:
            faces.append((3*count+i, 3*count+j, 2*count+j, 2*count+i))
    if recess_floor is not None:
        faces.append(tuple(3*count+i for i in range(count)))
        faces.append(tuple(2*count+i for i in range(count-1, -1, -1)))
    return _make_mesh(name, vertices, faces, [material])


def build_hull(materials):
    """Build a visual GIS hull and return its Blender objects.

    ``materials`` must map wood, wood_light, wood_dark, deck_wood, trim, navy,
    ivory, metal, rope, and shadow to Blender Material objects.  The hull occupies
    X -2.35..+2.35, reaches about 1.5 m across, and its lowest hull point is
    close to Z=0.  A separately supplied rig should place the mast at
    X=+1.25, Y=0 with its square partner on the fore tank top.
    """
    mat = {key: materials[key] for key in (
        "wood", "wood_light", "wood_dark", "deck_wood", "trim", "navy", "ivory",
        "metal", "rope", "shadow",
    )}
    objects = []
    add = objects.append

    # Closely spaced samples make the bottom and topside skin fair in plan
    # and elevation; the measured stations are included exactly as vertices.
    hull_stations = sorted({round(s, 6) for s in BOTTOM_STATIONS} |
                           {round(i*0.025, 6) for i in range(round(LOA/0.025)+1)} |
                           {round(BOW_X-x, 6) for x in
                            (BOARD_SLOT_AFT_X, BOARD_SLOT_FORE_X)})
    profiles = [(BOW_X - s, *_profile(s)) for s in hull_stations]
    count = len(profiles)

    # The developed bottom panel width drives the assembled chine.  Its
    # centreline and chines make a subtle V, with bow and stern rocker.
    bottom_vertices = []
    for x, chine, _, bottom_z, chine_z, _ in profiles:
        edge = min(BOARD_SLOT_HALF_WIDTH, max(.0004, chine*.4))
        slot_z = bottom_z + (chine_z-bottom_z)*edge/max(.001, chine)
        bottom_vertices.extend([
            (x, -max(0.001, chine), chine_z),
            (x, -edge, slot_z),
            (x, 0.0, bottom_z),
            (x, edge, slot_z),
            (x, max(0.001, chine), chine_z),
        ])
    bottom_faces = []
    for i in range(count - 1):
        xmid = (profiles[i][0]+profiles[i+1][0])/2
        through_case = BOARD_SLOT_AFT_X < xmid < BOARD_SLOT_FORE_X
        for j in range(4):
            if through_case and j in (1, 2):
                continue
            a = 5*i+j
            bottom_faces.append((a, a+5, a+6, a+1))
    add(_make_mesh("GIS | navy outer bottom", bottom_vertices, bottom_faces,
                   [mat["navy"]]))
    interior_bottom = [(x, y, z+0.018) for x, y, z in bottom_vertices]
    add(_make_mesh("GIS | varnished inner bottom", interior_bottom,
                   [tuple(reversed(face)) for face in bottom_faces],
                   [mat["wood_dark"]]))
    # Keep the narrow daggerboard passage genuinely open through both skins.
    for row, side_name in ((1, "port"), (3, "starboard")):
        section_ids = [i for i, p in enumerate(profiles)
                       if BOARD_SLOT_AFT_X-1e-6 <= p[0] <= BOARD_SLOT_FORE_X+1e-6]
        outside = [bottom_vertices[5*i+row] for i in section_ids]
        inside = [(x,y,z+.018) for x,y,z in outside]
        add(_loft("GIS | %s daggerboard slot lining" % side_name,
                  outside, inside, mat["wood_dark"]))

    for sign, side_name in ((-1, "port"), (1, "starboard")):
        outer_vertices = []
        inner_lower, inner_upper = [], []
        seam_points = [[], []]
        stripe_line = []
        for x, chine, sheer, bottom_z, chine_z, sheer_z in profiles:
            chine = max(0.001, chine)
            # Three vertical rows permit a genuine, narrow blue paint band.
            stripe_z = chine_z + 0.076
            stripe_y = chine + (sheer - chine) * ((stripe_z - chine_z) /
                                                max(0.01, sheer_z - chine_z))
            outer_vertices.extend([
                (x, sign*chine, chine_z),
                (x, sign*stripe_y, stripe_z),
                (x, sign*sheer, sheer_z),
            ])
            stripe_line.append((x, sign*(stripe_y+0.003), stripe_z))
            inner_lower.append((x, sign*max(0.001, chine-0.013), chine_z+0.020))
            inner_upper.append((x, sign*max(0.001, sheer-0.018), sheer_z-0.013))
            for seam, fraction in zip(seam_points, (0.41, 0.72)):
                z = stripe_z + fraction*(sheer_z-stripe_z)
                y = stripe_y + fraction*(sheer-stripe_y)
                seam.append((x, sign*(y+0.003), z))
        faces, indexes = [], []
        for i in range(count - 1):
            for j, material_index in ((0, 1), (1, 0)):
                a = 3*i+j
                face = (a, a+3, a+4, a+1)
                faces.append(tuple(reversed(face)) if sign < 0 else face)
                indexes.append(material_index)
        add(_make_mesh("GIS | %s varnished side and blue lower band" % side_name,
                       outer_vertices, faces, [mat["wood"], mat["navy"]], indexes))
        add(_loft("GIS | %s inner side" % side_name,
                  inner_lower, inner_upper, mat["wood_light"],
                  reverse_faces=sign > 0))
        add(_curve("GIS | %s ivory waterline" % side_name,
                   stripe_line, 0.004, mat["ivory"], smooth=True))
        for k, points in enumerate(seam_points):
            add(_curve("GIS | %s plank seam %d" % (side_name, k+1),
                       points, 0.0028, mat["wood_dark"], smooth=True))
        # A continuous 19 x 45 mm outer gunwale has its underside 33 mm
        # below the plywood sheer.  The exposed upper corners are rounded
        # 6 mm, as in the assembly manual.  The bow end tapers into the stem.
        add(_swept_rail("GIS | %s broad gunwale" % side_name,
                        hull_stations, sign, 0.000, 0.019,
                        -0.033, 0.012, 0.006,
                        mat["wood_dark"], taper_at_stem=True))
        # The 15 x 45 mm inwale stops where the bow and stern knees will
        # occupy the rail.  Its 19 x 45 x 70 mm spacers leave drainage gaps.
        inwale_stations = sorted({0.145, 4.600} |
                                 {s for s in hull_stations if 0.145 < s < 4.600})
        add(_swept_rail("GIS | %s inwale" % side_name,
                        inwale_stations, sign, -0.052, -0.037,
                        -0.033, 0.012, 0.006, mat["trim"]))
        spacer_index = 0
        spacer_start = 0.145
        while spacer_start + 0.070 <= 4.600:
            spacer_end = spacer_start + 0.070
            # Shift the rhythm at transverse side frames, as the manual
            # instructs, by omitting any block that would straddle one.
            frames = (1.08, 1.77, 2.68, 3.65)
            if not any(spacer_start-0.012 <= frame <= spacer_end+0.012
                       for frame in frames):
                spacer_index += 1
                add(_swept_rail("GIS | %s inwale spacer %02d" %
                                (side_name, spacer_index),
                                [spacer_start, spacer_end], sign,
                                -0.037, -0.018, -0.040, 0.005,
                                0.0, mat["wood_light"]))
            spacer_start += 0.160
        chine_line = [(x, sign*max(0.001, chine), chine_z)
                      for x, chine, _, _, chine_z, _ in profiles]
        add(_curve("GIS | %s chine batten" % side_name,
                   chine_line, 0.009, mat["wood_dark"], smooth=True))

    # Pointed stem and square, nearly vertical transom.
    bow = profiles[0]
    add(_rod("GIS | laminated bow stem",
             (BOW_X+0.008, 0, bow[3]-0.01),
             (BOW_X+0.008, 0, bow[5]+0.015),
             0.020, mat["wood_dark"]))
    tx, tch, tsh, tbz, tcz, tsz = profiles[-1]
    # Drawing sheet 6 locates a 49 mm high tiller passage 135 mm below the
    # sheer.  The sheet depicts half of the transom: the 100 mm dimension
    # runs from the centreline to the rounded end of the opening.
    slot_top, slot_bottom = tsz - .135, tsz - .184
    def transom_half_width(z):
        return tch + (tsh - tch) * (z - tcz) / (tsz - tcz)
    upper_width = transom_half_width(slot_top)
    lower_width = transom_half_width(slot_bottom)
    transom_vertices = [
        (tx, -tsh, tsz), (tx, tsh, tsz),
        (tx, upper_width, slot_top), (tx, -upper_width, slot_top),
        (tx, lower_width, slot_bottom), (tx, -lower_width, slot_bottom),
        (tx, tch, tcz), (tx, 0, tbz), (tx, -tch, tcz),
        (tx, -.100, slot_top), (tx, .100, slot_top),
        (tx, .100, slot_bottom), (tx, -.100, slot_bottom),
    ]
    transom_faces = [
        (0, 1, 2, 3),          # above the opening
        (3, 9, 12, 5),         # port side of the opening
        (10, 2, 4, 11),        # starboard side of the opening
        (5, 12, 11, 4, 6, 7, 8),  # below the opening and along the V
    ]
    add(_make_mesh("GIS | broad timber transom with tiller slot",
                   transom_vertices, transom_faces, [mat["wood"]]))
    add(_curve("GIS | transom cap",
               [(tx-0.015, -tsh, tsz+0.008),
                (tx-0.015, tsh, tsz+0.008)],
               0.022, mat["wood_dark"]))
    add(_curve("GIS | transom blue edge",
               [(tx-0.003, -tch, tcz+0.060),
                (tx-0.003, tch, tcz+0.060)],
               0.012, mat["navy"]))

    # Enclosed buoyancy at the bow and stern, with a clear mast opening in
    # the forward tank top.  The mast itself belongs to the rig module.
    # Seat tops are well below the sheer: drawing bulkhead body heights and
    # the manual's 365 mm bow drop set these nearly level tank surfaces.
    fore_bhd_top = _profile_x(1.039)[2] + 0.022 + 0.361
    fore_stem_top = _profile(0.0)[4] - 0.365
    fore_top = lambda x: fore_bhd_top + (fore_stem_top-fore_bhd_top) * (
        (x-1.039)/(2.35-1.039))
    mast_x = 1.25
    mast_partner_opening = 0.085  # 85 mm square opening shown in the plans.
    mast_opening_half = mast_partner_opening/2
    mast_slot_aft = mast_x - mast_opening_half
    mast_slot_fore = mast_x + mast_opening_half
    add(_deck_segment("GIS | fore tank top aft", [1.039, 1.10, mast_slot_aft],
                      fore_top, mat["deck_wood"]))
    add(_deck_segment("GIS | fore tank top ahead of mast",
                      [mast_slot_fore, 1.48, 1.70, 1.94, 2.15, 2.25, 2.30, 2.35],
                      fore_top, mat["deck_wood"]))
    for side in ("port", "starboard"):
        add(_deck_segment("GIS | fore deck at mast %s" % side,
                          [mast_slot_aft, mast_x, mast_slot_fore], fore_top,
                          mat["deck_wood"], cutout_side=side,
                          cutout_half_width=mast_opening_half))
    add(_bulkhead("GIS | forward buoyancy bulkhead", 1.039,
                  fore_top(1.039), mat["wood"]))
    mast_partner_z = fore_top(mast_x) + 0.020
    add(_square_socket("GIS | 180 mm fir mast partner with 85 mm opening",
                       (mast_x, 0), 0.180, mast_partner_opening,
                       mast_partner_z, mast_partner_z-0.028,
                       mat["wood_dark"]))
    add(_square_socket("GIS | fir mast step with 72 mm square socket",
                       (mast_x, 0), 0.180, 0.072, 0.240, 0.140,
                       mat["wood_dark"], recess_floor=0.160))

    aft_bhd_top = _profile_x(-1.55)[2] + 0.022 + 0.241
    aft_transom_top = _profile_x(-2.35)[2] + 0.022 + 0.180
    aft_top = lambda x: aft_bhd_top + (aft_transom_top-aft_bhd_top) * (
        (-x-1.55)/0.80)
    add(_deck_segment("GIS | aft buoyancy tank top",
                      [-2.34, -2.18, -1.96, -1.72, -1.55],
                      aft_top, mat["deck_wood"]))
    add(_bulkhead("GIS | aft buoyancy bulkhead", -1.55,
                  aft_top(-1.55), mat["wood"]))
    add(_ring("GIS | aft tank inspection rim", (-1.89, 0.0),
              0.112, 0.128, aft_top(-1.89)+0.006, mat["metal"]))
    add(_ring("GIS | aft tank inspection lid", (-1.89, 0.0),
              0.0, 0.110, aft_top(-1.89)+0.003, mat["wood_dark"]))

    # Side seats follow the narrowing inner hull instead of using rectangular
    # planks that would poke through the topsides.
    seat_z = 0.382
    seat_xs = [-1.43, -1.20, -0.85, -0.50, -0.15, 0.20, 0.55, 0.86]
    for sign, side_name in ((-1, "port"), (1, "starboard")):
        outer = []
        inner = []
        for x in seat_xs:
            beam = _inside_half_beam(x, seat_z)
            outer.append((x, sign*(beam-0.018)))
            inner.append((x, sign*max(0.16, beam-0.23)))
        polygon = outer + list(reversed(inner))
        add(_solid_xy("GIS | %s cockpit side seat" % side_name,
                      polygon, seat_z, 0.026, mat["deck_wood"]))
        add(_curve("GIS | %s seat lip" % side_name,
                   [(x, y, seat_z+0.004) for x, y in inner],
                   0.008, mat["wood_dark"]))

    # Midships thwart, its supports, and the slotted centreboard trunk.
    cross_x = -0.24
    thwart_z = 0.415
    cross_half = _inside_half_beam(cross_x, thwart_z)-0.016
    add(_solid_xy("GIS | removable centre thwart",
                  [(cross_x-0.12, -cross_half),
                   (cross_x+0.12, -cross_half),
                   (cross_x+0.12, cross_half),
                   (cross_x-0.12, cross_half)],
                  thwart_z, 0.034, mat["wood_light"]))
    for sign, side_name in ((-1, "port"), (1, "starboard")):
        add(_rod("GIS | %s thwart support" % side_name,
                 (cross_x, sign*0.42, 0.18),
                 (cross_x, sign*0.42, thwart_z-0.025),
                 0.017, mat["wood_dark"]))
    trunk_front, trunk_rear = 0.55, -0.69
    for sign, side_name in ((-1, "port"), (1, "starboard")):
        add(_make_mesh("GIS | centreboard trunk %s wall" % side_name,
                       [(trunk_rear, sign*0.056, 0.045),
                        (trunk_front, sign*0.056, 0.045),
                        (trunk_front, sign*0.056, 0.408),
                        (trunk_rear, sign*0.056, 0.408)],
                       [(0, 1, 2, 3)], [mat["wood"]]))
        add(_curve("GIS | centreboard trunk %s cap" % side_name,
                   [(trunk_rear, sign*0.058, 0.414),
                    (trunk_front, sign*0.058, 0.414)],
                   0.017, mat["wood_dark"]))
    add(_solid_xy("GIS | centreboard slot shadow",
                  [(trunk_rear+0.025, -0.027), (trunk_front-0.025, -0.027),
                   (trunk_front-0.025, 0.027), (trunk_rear+0.025, 0.027)],
                  0.407, 0.002, mat["shadow"]))
    add(_rod("GIS | centreboard lifting toggle",
             (0.39, 0, 0.414), (0.39, 0, 0.49),
             0.012, mat["rope"]))

    # A partly lowered board gives the model its visible working profile.
    board_outline = [(-0.49, 0.035), (0.35, 0.035), (0.24, -0.40),
                     (0.07, -0.58), (-0.37, -0.48)]
    board_vertices = [(x, -0.014, z) for x, z in board_outline]
    board_vertices += [(x, 0.014, z) for x, z in board_outline]
    board_faces = [tuple(range(5)), tuple(range(9, 4, -1))]
    board_faces += [(i, (i+1)%5, (i+1)%5+5, i+5) for i in range(5)]
    add(_make_mesh("GIS | partly lowered centreboard",
                   board_vertices, board_faces, [mat["wood_dark"]]))

    # Slender floors and transverse frames make the open cockpit legible.
    for s in (1.08, 1.77, 2.68, 3.65):
        x = BOW_X - s
        chine, sheer, bottom_z, chine_z, sheer_z = _profile(s)
        for sign, side_name in ((-1, "port"), (1, "starboard")):
            add(_curve("GIS | %s frame %.2f" % (side_name, s),
                       [(x, 0, bottom_z+0.026),
                        (x, sign*(chine-0.012), chine_z+0.025),
                        (x, sign*(sheer-0.027), sheer_z-0.028)],
                       0.010, mat["trim"]))
    for fraction in (-0.55, 0.0, 0.55):
        points = []
        for s in (0.45, 0.75, 1.05, 1.35, 1.65, 1.95, 2.25, 2.55,
                  2.85, 3.15, 3.45, 3.75, 4.05, 4.35, 4.65):
            chine, _, bottom_z, chine_z, _ = _profile(s)
            points.append((BOW_X-s, fraction*chine,
                           bottom_z+abs(fraction)*(chine_z-bottom_z)+0.021))
        add(_curve("GIS | cockpit floor plank seam %+.2f" % fraction,
                   points, 0.0025, mat["wood_dark"]))

    # Two narrow protective runners under the bottom panel.
    for sign, side_name in ((-1, "port"), (1, "starboard")):
        points = []
        for s in (0.7, 1.0, 1.3, 1.6, 1.9, 2.2, 2.5, 2.8,
                  3.1, 3.4, 3.7, 4.0, 4.3, 4.6):
            chine, _, bottom_z, chine_z, _ = _profile(s)
            points.append((BOW_X-s, sign*0.60*chine,
                           bottom_z+0.60*(chine_z-bottom_z)-0.014))
        add(_curve("GIS | %s bottom runner" % side_name,
                   points, 0.015, mat["wood_dark"]))

    # Pintles, rudder stock, a broad rudder blade, and an inboard tiller.
    rudder_outline = [(-2.41, 0.44), (-2.60, 0.44), (-2.67, 0.07),
                      (-2.86, -0.46), (-2.68, -0.49), (-2.43, -0.19)]
    rudder_verts = [(x, -0.019, z) for x, z in rudder_outline]
    rudder_verts += [(x, 0.019, z) for x, z in rudder_outline]
    nr = len(rudder_outline)
    rudder_faces = [tuple(range(nr)), tuple(range(2*nr-1, nr-1, -1))]
    rudder_faces += [(i, (i+1)%nr, (i+1)%nr+nr, i+nr) for i in range(nr)]
    add(_make_mesh("GIS | timber rudder blade", rudder_verts,
                   rudder_faces, [mat["wood_light"]]))
    add(_rod("GIS | rudder stock", (-2.46, 0, -0.12),
             (-2.46, 0, 0.64), 0.032, mat["wood_dark"]))
    for z in (0.03, 0.32):
        add(_rod("GIS | rudder gudgeon %.2f" % z,
                 (-2.38, 0, z), (-2.48, 0, z),
                 0.022, mat["metal"]))
    add(_curve("GIS | curved varnished tiller",
               [(-2.52, 0, 0.63), (-2.32, 0, 0.67),
                (-1.94, 0, 0.65), (-1.46, 0, 0.59),
                (-1.00, 0, 0.54)],
               0.023, mat["wood_dark"]))
    add(_rod("GIS | tiller hand grip", (-1.08, 0, 0.55),
             (-0.94, 0, 0.535), 0.028, mat["trim"]))

    # A pair of simple 2.7 m oars lies along the side seats and fore tank,
    # echoing the sailing/rowing dual use visible in the reference boat.
    for sign, side_name in ((-1, "port"), (1, "starboard")):
        y_grip = sign * 0.44
        y_blade = sign * 0.31
        add(_rod("GIS | stowed %s oar shaft" % side_name,
                 (-1.23, y_grip, 0.465), (1.05, y_blade, 0.552),
                 0.016, mat["trim"]))
        add(_rod("GIS | stowed %s oar grip" % side_name,
                 (-1.37, y_grip, 0.460), (-1.18, y_grip, 0.467),
                 0.020, mat["trim"]))
        add(_solid_xy("GIS | stowed %s oar blade" % side_name,
                      [(1.02, y_blade-0.020), (1.18, y_blade-0.050),
                       (1.43, y_blade-0.058), (1.43, y_blade+0.058),
                       (1.18, y_blade+0.050), (1.02, y_blade+0.020)],
                      0.574, 0.012, mat["trim"]))

    return objects
