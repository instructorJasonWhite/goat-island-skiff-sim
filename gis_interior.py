"""Plan-informed cockpit bulkheads and centreboard case for the GIS model.

The two bulkhead opening patterns follow drawing sheet 4. The case follows
the 757 mm by 322/311 mm side profile on drawing sheet 5. Coordinates are
metres and the geometry remains an illustrative assembly.
"""

import math
import bpy

from gis_hull import (
    _curve, _inside_half_beam, _make_mesh, _profile_x, _rod, _solid_xy,
)


def _prism(name, x0, x1, yz, material):
    n = len(yz)
    vertices = [(x0, y, z) for y, z in yz]
    vertices += [(x1, y, z) for y, z in yz]
    faces = [tuple(range(n)), tuple(range(2*n-1, n-1, -1))]
    faces += [(i, (i+1) % n, (i+1) % n+n, i+n) for i in range(n)]
    return _make_mesh(name, vertices, faces, [material])


def _rounded_opening(ymin, ymax, zmin, zmax, radius, steps=4):
    # A small roundover mimics the jigsaw/sanded plywood cutouts on sheet 4.
    corners = [
        (ymax-radius, zmin+radius, -90, 0),
        (ymax-radius, zmax-radius, 0, 90),
        (ymin+radius, zmax-radius, 90, 180),
        (ymin+radius, zmin+radius, 180, 270),
    ]
    points = []
    for cy, cz, a0, a1 in corners:
        for i in range(steps+1):
            a = math.radians(a0+(a1-a0)*i/steps)
            points.append((cy+radius*math.cos(a), cz+radius*math.sin(a)))
    return points


def _open_bulkhead(name, x, top_z, openings, material):
    chine, _, bottom_z, chine_z, _ = _profile_x(x)
    z0 = min(chine_z, bottom_z) + .022
    low_width = max(.05, chine-.016)
    high_width = _inside_half_beam(x, top_z)
    yz = [(-low_width, z0), (low_width, z0),
          (high_width, top_z), (-high_width, top_z)]
    obj = _prism(name, x-.007, x+.007, yz, material)
    for idx, (ymin, ymax, zmin, zmax, radius) in enumerate(openings, 1):
        cut = _prism(name+' cutter '+str(idx), x-.08, x+.08,
                     _rounded_opening(ymin, ymax, zmin, zmax, radius),
                     material)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        boolean = obj.modifiers.new('Plan cutout '+str(idx), 'BOOLEAN')
        boolean.operation = 'DIFFERENCE'
        boolean.solver = 'EXACT'
        boolean.object = cut
        bpy.ops.object.modifier_apply(modifier=boolean.name)
        bpy.data.objects.remove(cut, do_unlink=True)
    obj.select_set(False)
    return obj


def build_interior(materials):
    """Return corrected Bhd 2/3, 757 mm case, board, gusset and middle seat."""
    m = materials
    objs = []
    add = objs.append

    # Bulkhead 2 has a single wide central rounded opening (drawing p. 4).
    bh2_x = 1.039
    _, _, bh2_floor, _, _ = _profile_x(bh2_x)
    bh2_panel_bottom = bh2_floor + .022
    bh2_top = bh2_panel_bottom + .361
    bh2_half = min(.310, _inside_half_beam(bh2_x, bh2_top)-.075)
    add(_open_bulkhead('GIS | Bhd 2 with plan cutout', bh2_x, bh2_top,
                       [(-bh2_half, bh2_half,
                         bh2_panel_bottom+.080, bh2_top-.080, .032)],
                       m['wood']))
    add(_curve('GIS | Bhd 2 seat cleat',
               [(bh2_x-.013, -_inside_half_beam(bh2_x,bh2_top), bh2_top-.016),
                (bh2_x-.013, _inside_half_beam(bh2_x,bh2_top), bh2_top-.016)],
               .009, m['trim']))

    # Bulkhead 3 has two side openings around the centreline web/case.
    # Its aft face takes the case; the 310 mm wide middle seat projects fore.
    bh3_x = -.350
    _, _, bh3_floor, _, _ = _profile_x(bh3_x)
    bh3_panel_bottom = bh3_floor + .022
    bh3_top = bh3_panel_bottom + .316
    half = _inside_half_beam(bh3_x, bh3_top)
    outer = min(.466, half-.065)
    inner = .082
    zmin, zmax = bh3_panel_bottom+.080, bh3_top-.060
    add(_open_bulkhead('GIS | Bhd 3 with paired plan cutouts',
                       bh3_x, bh3_top,
                       [(-outer, -inner, zmin, zmax, .027),
                        (inner, outer, zmin, zmax, .027)], m['wood']))
    for sign, side_name in ((-1, 'port'), (1, 'starboard')):
        y0 = sign*inner
        y1 = sign*half
        add(_curve('GIS | Bhd 3 %s seat cleat' % side_name,
                   [(bh3_x+.012, y0, bh3_top-.009),
                    (bh3_x+.012, y1, bh3_top-.009)],
                   .009, m['trim']))

    # Case side drawing: 157 + 200 + 200 + 200 = 757 mm.
    # 22 mm solid board + 2 mm clearance per side -> 25 mm spacer;
    # two 6 mm plywood sides make a 37 mm outer case.
    case_rear, case_front = bh3_x, bh3_x+.757
    half_outer, half_slot = .0185, .0125
    top_z = bh3_top+.005
    rear_bottom, front_bottom = top_z-.321, top_z-.311
    for sign, side_name in ((-1, 'port'), (1, 'starboard')):
        y = sign*half_outer
        wall = [(case_rear, y, rear_bottom),
                (case_front, y, front_bottom),
                (case_front, y, top_z),
                (case_rear, y, top_z)]
        add(_make_mesh('GIS | 757 mm centrecase %s plywood side' % side_name,
                       wall, [(0,1,2,3)], [m['wood']]))
        add(_curve('GIS | centrecase %s top cleat' % side_name,
                   [(case_rear, sign*.028, top_z+.002),
                    (case_front, sign*.028, top_z+.002)],
                   .010, m['wood_dark']))
        add(_curve('GIS | centrecase %s lower cleat' % side_name,
                   [(case_rear, sign*.028, rear_bottom+.010),
                    (case_front, sign*.028, front_bottom+.010)],
                   .009, m['trim']))
    add(_solid_xy('GIS | 25 mm open centrecase slot',
                  [(case_rear+.036,-half_slot), (case_front-.036,-half_slot),
                   (case_front-.036,half_slot), (case_rear+.036,half_slot)],
                  top_z-.004, .003, m['shadow']))

    # The forward gusset on sheet 5 ties the case to the bottom panel.
    gusset_verts = [
        (case_front-.012,-.024,rear_bottom),
        (case_front+.188,-.024,front_bottom),
        (case_front-.012,-.024,top_z-.005),
        (case_front-.012,.024,rear_bottom),
        (case_front+.188,.024,front_bottom),
        (case_front-.012,.024,top_z-.005),
    ]
    add(_make_mesh('GIS | centrecase forward triangular gusset',
                   gusset_verts, [(0,1,2),(5,4,3),(0,3,4,1),
                                  (1,4,5,2),(2,5,3,0)], [m['wood']]))

    # A partly lowered 1265 mm timber daggerboard slides in the narrow case.
    # Its 341 mm top chord and slanted long edges follow the foil illustration
    # on text-manual page 63; a rope through two 8 mm holes forms its handle.
    board_xz = [
        (-.020, .480), (.321, .480),
        (-.115, -.710), (-.160, -.785),
        (-.420, -.785), (-.405, -.708),
    ]
    verts = [(x,-.011,z) for x,z in board_xz]
    verts += [(x,.011,z) for x,z in board_xz]
    n = len(board_xz)
    faces = [tuple(range(n)), tuple(range(2*n-1,n-1,-1))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    add(_make_mesh('GIS | 22 mm sliding 1265 mm centreboard', verts, faces,
                   [m['wood_dark']]))
    add(_curve('GIS | centreboard knotted lifting rope',
               [(0.050, -.016, .430), (0.050, -.035, .545),
                (.125, -.035, .580), (.200, -.035, .545),
                (.200, -.016, .430)], .005, m['rope']))
    for i, x in enumerate((.050, .200), 1):
        add(_rod('GIS | centreboard rope hole %d shadow' % i,
                 (x, -.013, .430), (x, -.011, .430),
                 .006, m['shadow']))

    # Sheet 4 + assembly text: 310 mm fore-and-aft middle seat, split at
    # the case; its underside supports bear on the case and the hull sides.
    seat_front = bh3_x+.310
    seat_z = top_z+.008
    for sign, side_name in ((-1, 'port'), (1, 'starboard')):
        rear_w = _inside_half_beam(bh3_x, seat_z)-.013
        front_w = _inside_half_beam(seat_front, seat_z)-.013
        ys = .051
        poly = [(bh3_x,sign*rear_w),(seat_front,sign*front_w),
                (seat_front,sign*ys),(bh3_x,sign*ys)]
        add(_solid_xy('GIS | 310 mm %s middle seat panel' % side_name,
                      poly, seat_z, .012, m['wood_light']))
        add(_curve('GIS | %s middle seat front support' % side_name,
                   [(seat_front-.010,sign*.070,seat_z-.037),
                    (seat_front-.010,sign*(front_w-.025),seat_z-.037)],
                   .010, m['trim']))
    return objs
