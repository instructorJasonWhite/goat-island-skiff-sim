"""Editable balanced lug rig for the visual Goat Island Skiff model.

Coordinates are metres: +X bow, -X stern, -Y port, +Z up.
The four sail corners follow the proportions and edge lengths on sheet 9
of the supplied assembly drawings. This is a visual mesh, not sailmaking data.
"""

import math

import bpy
from mathutils import Vector


def _link(obj):
    bpy.context.collection.objects.link(obj)
    return obj


def _mesh(name, vertices, faces, material, smooth=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    _link(obj)
    obj.data.materials.append(material)
    for p in mesh.polygons:
        p.use_smooth = smooth
    return obj


def _tube(name, points, radius, material, bevel_resolution=3):
    curve = bpy.data.curves.new(name, 'CURVE')
    curve.dimensions = '3D'
    curve.resolution_u = 12
    curve.bevel_depth = radius
    curve.bevel_resolution = bevel_resolution
    poly = curve.splines.new('POLY')
    poly.points.add(len(points) - 1)
    for cp, p in zip(poly.points, points):
        cp.co = (*p, 1)
    obj = bpy.data.objects.new(name, curve)
    _link(obj)
    obj.data.materials.append(material)
    return obj


def _spar(name, a, b, r0, r1, material, segments=12):
    direction = Vector(b) - Vector(a)
    mid = (Vector(a) + Vector(b)) / 2
    bpy.ops.mesh.primitive_cone_add(
        vertices=segments, radius1=r0, radius2=r1,
        depth=direction.length, location=mid,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    obj.data.materials.append(material)
    for face in obj.data.polygons:
        face.use_smooth = True
    bevel = obj.modifiers.new('Soft spar edges', 'BEVEL')
    bevel.width = min(r0, r1) * 0.25
    bevel.segments = 2
    obj.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return obj


def _ring(name, location, radius, tube_radius, material, normal=(0, 0, 1)):
    bpy.ops.mesh.primitive_torus_add(
        major_segments=20, minor_segments=6, location=location,
        major_radius=radius, minor_radius=tube_radius,
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = Vector(normal).to_track_quat('Z', 'Y').to_euler()
    obj.data.materials.append(material)
    for face in obj.data.polygons:
        face.use_smooth = True
    return obj


# Drawing sheet 8, hollow square mast option. Dimensions are finished outside
# widths, measured along the mast from its heel. The foot stays at 70 mm
# through the 80 mm deep mast-step socket, then widens to the plan's 82 mm
# untapered section at 350 mm. Above that the four 12 mm staves follow the
# drawing's taper.
_MAST_BASE = Vector((1.25, 0.0, 0.162))
_MAST_AXIS = Vector((-0.03, 0.0, 4.730)).normalized()
_MAST_FORE = Vector((_MAST_AXIS.z, 0.0, -_MAST_AXIS.x))
_MAST_BEAM = Vector((0.0, 1.0, 0.0))
_MAST_LENGTH = 4.730
_MAST_STAVE = 0.012
_MAST_STATIONS = (
    (0.000, 0.0700),
    (0.100, 0.0700),
    (0.350, 0.0820),
    (1.114, 0.0816),
    (1.878, 0.0804),
    (2.642, 0.0783),
    (3.406, 0.0754),
    (4.170, 0.0676),
    (4.730, 0.0471),
)


def _mast_width(distance):
    """Finished outside square width at distance from the mast heel."""
    if not 0 <= distance <= _MAST_LENGTH:
        raise ValueError('Mast station must be between heel and head')
    for (s0, w0), (s1, w1) in zip(_MAST_STATIONS, _MAST_STATIONS[1:]):
        if distance <= s1:
            t = (distance - s0) / (s1 - s0)
            return w0 + (w1 - w0) * t
    return _MAST_STATIONS[-1][1]


def _mast_wall(distance, width):
    """Foot is planed outside a 58 mm infill; upper stave walls are 12 mm."""
    if distance <= 0.350:
        return (width - 0.058) / 2
    return _MAST_STAVE


def _mast_point(distance, fore, beam):
    return _MAST_BASE + _MAST_AXIS * distance + _MAST_FORE * fore + _MAST_BEAM * beam


def _mast_side_at_z(height, beam_offset):
    """A rigging point beside the starboard face of the raked mast."""
    distance = (height - _MAST_BASE.z) / _MAST_AXIS.z
    return _mast_point(distance, 0.0, beam_offset)


def _mast_prism(name, stations, profile, material):
    """Loft a closed stave or plug along the raked mast axis."""
    n = len(profile(*stations[0]))
    vertices = [tuple(_mast_point(s, x, y))
                for s, width in stations for x, y in profile(s, width)]
    faces = [tuple(reversed(range(n)))]
    for ring in range(len(stations) - 1):
        for corner in range(n):
            next_corner = (corner + 1) % n
            faces.append((ring * n + corner, ring * n + next_corner,
                          (ring + 1) * n + next_corner,
                          (ring + 1) * n + corner))
    faces.append(tuple((len(stations) - 1) * n + corner for corner in range(n)))
    return _mesh(name, vertices, faces, material)


def _mast_wide_profile(distance, width, side):
    """A full-width stave with soft exposed corners (maximum 6 mm radius)."""
    half = width / 2
    wall = _mast_wall(distance, width)
    radius = min(0.006, wall / 2)
    profile = [(-half + radius, half), (half - radius, half)]
    for step in range(1, 7):
        angle = math.pi * step / 12
        profile.append((half - radius + radius * math.sin(angle),
                        half - radius + radius * math.cos(angle)))
    profile.extend(((half, half - wall),
                    (-half, half - wall), (-half, half - radius)))
    for step in range(5, 0, -1):
        angle = math.pi * step / 12
        profile.append((-half + radius - radius * math.sin(angle),
                        half - radius + radius * math.cos(angle)))
    # The first profile runs clockwise around the port/starboard cap. Reverse
    # it so the prism has outward normals. Mirroring reverses it once more.
    profile.reverse()
    if side < 0:
        profile = [(x, -y) for x, y in reversed(profile)]
    return profile


def _mast_narrow_profile(distance, width, side):
    """A side stave fitted between the two full-width staves."""
    half = width / 2
    inner = half - _mast_wall(distance, width)
    profile = [(inner, -inner), (half, -inner),
               (half, inner), (inner, inner)]
    if side < 0:
        profile = [(-x, y) for x, y in reversed(profile)]
    return profile


def _mast_plug_profile(distance, width):
    """Square solid infill precisely fitted to the hollow between staves."""
    half = width / 2 - _mast_wall(distance, width)
    return [(-half, -half), (half, -half),
            (half, half), (-half, half)]


def _build_hollow_square_mast(wood):
    for name, side in (('Starboard', 1), ('Port', -1)):
        _mast_prism(f'Mast {name} full-width 12 mm fir stave',
                    _MAST_STATIONS,
                    lambda distance, width, s=side:
                    _mast_wide_profile(distance, width, s), wood)
    for name, side in (('Forward', 1), ('Aft', -1)):
        _mast_prism(f'Mast {name} fitted 12 mm fir stave',
                    _MAST_STATIONS,
                    lambda distance, width, s=side:
                    _mast_narrow_profile(distance, width, s), wood)

    # The manual calls for a 857 mm solid heel, spaced hollow length, and a
    # 50 mm solid head. Plugs fit the changing internal opening at each end.
    heel_stations = [(s, _mast_width(s)) for s in (0.0, 0.100, 0.350, 0.857)]
    _mast_prism('Mast solid heel plug | 857 mm', heel_stations,
                _mast_plug_profile, wood)
    for index, start in enumerate((1.55, 2.55, 3.55, 4.35), 1):
        spacer_stations = [(s, _mast_width(s)) for s in (start, start + 0.035)]
        _mast_prism(f'Mast internal spacer {index:02}', spacer_stations,
                    _mast_plug_profile, wood)
    head_stations = [(s, _mast_width(s)) for s in (4.680, _MAST_LENGTH)]
    _mast_prism('Mast solid head plug | 50 mm', head_stations,
                _mast_plug_profile, wood)


# Four sail corners, counter-clockwise from aft clew. Their X/Z coordinates
# are solved from all five dimensions on drawing sheet 9: 3283 mm foot,
# 2368 mm short edge, 3178 mm yard edge, 5325 mm long edge and 3737 mm
# diagonal. The flat polygon area is 9.680 square metres.
AFT_CLEW = Vector((-1.80, -0.105, 1.15))
FORE_TACK = Vector((1.483, -0.105, 1.15))
FORE_HEAD = Vector((1.1144, -0.105, 3.4891))
PEAK = Vector((-0.3944, -0.105, 6.2861))


def sail_point(u, v, outward=0):
    """Point within the quadrilateral; u aft to forward, v foot to head."""
    left = AFT_CLEW.lerp(PEAK, v)
    right = FORE_TACK.lerp(FORE_HEAD, v)
    p = left.lerp(right, u)
    # Wind-filled camber, strongest in the lower/middle third.
    p.y -= 0.22 * math.sin(math.pi * u) * math.sin(math.pi * v) ** 0.72
    p.y += 0.010 * math.sin(7 * math.pi * v) * math.sin(math.pi * u)
    p.y += outward
    return p


def build_rig(materials):
    """Build mast, spars, sail, seams, ropework; return created objects."""
    before = set(bpy.data.objects)
    wood = materials['wood_light']
    sail = materials['sail']
    sail_alt = materials['sail_alt']
    stitch = materials['stitch']
    rope = materials['rope']
    metal = materials['metal']

    # The mast is built from four separate editable fir staves around a
    # genuine hollow, with a fitted heel, small spacers, and a head plug.
    _build_hollow_square_mast(wood)
    _spar('Boom | 3.548 m round spar', (-1.9325, -0.148, 1.15),
          (1.6155, -0.148, 1.15), 0.020, 0.015, wood, 12)
    yard_direction = (PEAK - FORE_HEAD).normalized()
    _spar('Yard | 3.601 m round spar',
          FORE_HEAD - yard_direction * 0.2115 + Vector((0, -0.045, 0)),
          PEAK + yard_direction * 0.2115 + Vector((0, -0.045, 0)),
          0.020, 0.015, wood, 12)
    _ring('Boom tack band', (1.47, -0.148, 1.15), 0.026, 0.005, metal,
          normal=(1, 0, 0))

    nu, nv = 34, 36
    verts = [tuple(sail_point(i / nu, j / nv))
             for j in range(nv + 1) for i in range(nu + 1)]
    faces = []
    for j in range(nv):
        for i in range(nu):
            k = j * (nu + 1) + i
            faces.append((k, k + 1, k + nu + 2, k + nu + 1))
    cloth = _mesh('Balanced lug sail | 9.68 m2 plan', verts, faces, sail, True)
    cloth.data.materials.append(sail_alt)
    for p in cloth.data.polygons:
        row = p.index // nu
        p.material_index = 1 if row % 6 == 5 else 0
    cloth.modifiers.new('Canvas thickness', 'SOLIDIFY').thickness = 0.0025
    cloth.modifiers.new('Soft cloth normals', 'WEIGHTED_NORMAL')

    # Horizontal sewn panels, leech tape, foot and yard sleeves.
    for j, v in enumerate((0.15, 0.30, 0.45, 0.60, 0.75, 0.90), 1):
        pts = [sail_point(i / 30, v, -0.0030) for i in range(31)]
        _tube(f'Sail seam {j:02}', pts, 0.0023, stitch, 2)
    for label, coord_fn in (
        ('Aft leech tape', lambda t: sail_point(0, t, -0.003)),
        ('Forward luff tape', lambda t: sail_point(1, t, -0.003)),
        ('Foot tape', lambda t: sail_point(t, 0, -0.003)),
        ('Head tape', lambda t: sail_point(t, 1, -0.003)),
    ):
        _tube(label, [coord_fn(i / 30) for i in range(31)], 0.0050, stitch, 3)

    # Cloth corner patches are individually visible but subdued.
    for name, uv in (
        ('Clew reinforcement', ((0, 0), (.17, 0), (0, .13))),
        ('Tack reinforcement', ((1, 0), (.83, 0), (1, .18))),
        ('Peak reinforcement', ((0, 1), (.14, 1), (0, .84))),
        ('Throat reinforcement', ((1, 1), (.82, 1), (1, .78))),
    ):
        pts = [tuple(sail_point(u, v, -0.004)) for u, v in uv]
        _mesh(name, pts, [(0, 1, 2)], sail_alt, False)

    # Two reef rows like the drawing. A few hanging ties make scale legible.
    for ridx, v in enumerate((0.205, 0.395), 1):
        for i in range(25):
            u0 = i / 25
            u1 = min(1, u0 + .023)
            _tube(f'Reef {ridx} stitch {i:02}',
                  [sail_point(u0, v, -0.004), sail_point(u1, v, -0.004)],
                  0.002, stitch, 1)
        for k, u in enumerate((.08, .26, .44, .62, .80, .97), 1):
            p = sail_point(u, v, -.012)
            _ring(f'Reef {ridx} grommet {k}', p, .010, .0024, metal,
                  normal=(0, 1, 0))
            if k not in (1, 6):
                _tube(f'Reef {ridx} tie {k}',
                      [p, p + Vector((.025, -.018, -.09))], .0017, rope, 1)
    for name, p in [('Clew', AFT_CLEW), ('Tack', FORE_TACK),
                    ('Peak', PEAK), ('Throat', FORE_HEAD)]:
        _ring(name + ' sail cringle', p + Vector((0, -.010, 0)),
              .014, .003, metal, normal=(0, 1, 0))

    # Small lacings along both spars.
    for i in range(1, 18):
        u = i / 18
        foot = sail_point(u, 0)
        head = sail_point(u, 1)
        _tube(f'Boom lacing {i:02}',
              [foot, foot + Vector((0, -.055, -.014)),
               foot + Vector((0, -.065, .011))], .0022, rope, 2)
        _tube(f'Yard lacing {i:02}',
              [head, head + Vector((0, -.050, -.010)),
               head + Vector((0, -.065, .012))], .0022, rope, 2)

    # Halyard, downhaul, and mainsheet/traveller arrangement.
    mast_tip = _mast_point(_MAST_LENGTH, 0.0, 0.0)
    yard_hoist = sail_point(.63, 1) + Vector((0, -.050, .03))
    _tube('Halyard to yard', [mast_tip, yard_hoist], .004, rope)
    _tube('Halyard down mast', [mast_tip, _mast_side_at_z(3.2, .065),
                               _mast_side_at_z(1.0, .068),
                               (1.20, .16, .59)],
          .0035, rope)
    _tube('Downhaul', [(1.18, -.148, 1.15), (1.17, -.11, .66),
                       (1.14, -.08, .52)], .005, rope)
    _ring('Downhaul deck eye', (1.14, -.08, .54), .015, .004, metal)
    boom_sheet = Vector((-1.54, -.148, 1.15))
    aft_traveller = Vector((-2.17, -.02, .60))
    _tube('Mainsheet upper fall', [boom_sheet, (-1.65, -.1, .96),
                                    aft_traveller], .006, rope)
    _tube('Mainsheet working fall', [aft_traveller, (-1.88, .12, .86),
                                      (-1.55, .15, .49)], .006, rope)
    _tube('Stern traveller', [(-2.14, -.40, .60), (-2.17, 0, .61),
                              (-2.14, .40, .60)], .006, rope)
    _ring('Mainsheet boom block', boom_sheet, .024, .006, metal,
          normal=(0, 1, 0))
    _ring('Mainsheet stern block', aft_traveller, .024, .006, metal,
          normal=(0, 1, 0))
    return list(set(bpy.data.objects) - before)
