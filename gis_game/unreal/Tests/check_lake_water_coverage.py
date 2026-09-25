"""Dry-run the runtime lake tiling geometry without Unreal Editor.

This checks source-water coverage, including narrow shoreline slivers. The
engine mesh generation still requires an Unreal build and Play-in-Editor.
"""

from bisect import bisect_right
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "Content/Data/greenwood_usgs.json").read_text(encoding="utf-8"))
OUTER = DATA["water_polygon"]
RINGS = [OUTER, *DATA["islands"]]
COARSE = 30.0
FINE = 10.0


def segment_touches_cell(a, b, column, row, size):
    x0 = column * size
    y0 = row * size
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    enter, leave = 0.0, 1.0
    for p, q in ((-dx, a[0] - x0), (dx, x0 + size - a[0]),
                 (-dy, a[1] - y0), (dy, y0 + size - a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                if t > leave:
                    return False
                enter = max(enter, t)
            else:
                if t < enter:
                    return False
                leave = min(leave, t)
    return True


def edge_cells(size):
    cells = set()
    for ring in RINGS:
        for index, a in enumerate(ring):
            b = ring[(index + 1) % len(ring)]
            for row in range(math.floor((min(a[1], b[1]) - 1e-6) / size),
                             math.floor((max(a[1], b[1]) + 1e-6) / size) + 1):
                for column in range(math.floor((min(a[0], b[0]) - 1e-6) / size),
                                    math.floor((max(a[0], b[0]) + 1e-6) / size) + 1):
                    if segment_touches_cell(a, b, column, row, size):
                        cells.add((column, row))
    return cells


def crossings(ring, y):
    result = []
    for index, a in enumerate(ring):
        b = ring[(index + 1) % len(ring)]
        if (a[1] <= y < b[1]) or (b[1] <= y < a[1]):
            result.append(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
    return result


def water_intersections(y):
    return sorted(crossings(OUTER, y)), sorted(
        x for island in DATA["islands"] for x in crossings(island, y))


def is_water(x, shore, islands):
    return bool(bisect_right(shore, x) & 1) and not bool(bisect_right(islands, x) & 1)


boundary = edge_cells(COARSE)
fine_edges = edge_cells(FINE)
coarse_tiles = set()
fine_tiles = set()
bounds = DATA["bounds_m"]
for row in range(math.floor(bounds["min_y"] / COARSE), math.ceil(bounds["max_y"] / COARSE)):
    shore, islands = water_intersections((row + 0.5) * COARSE)
    fine_crossings = [water_intersections((row * 3 + subrow + 0.5) * FINE)
                      for subrow in range(3)]
    for column in range(math.floor(bounds["min_x"] / COARSE),
                        math.ceil(bounds["max_x"] / COARSE)):
        if (column, row) not in boundary:
            if is_water((column + 0.5) * COARSE, shore, islands):
                coarse_tiles.add((column, row))
            continue
        for subrow in range(3):
            fine_shore, fine_islands = fine_crossings[subrow]
            for subcolumn in range(3):
                cell = (column * 3 + subcolumn, row * 3 + subrow)
                x = (cell[0] + 0.5) * FINE
                if is_water(x, fine_shore, fine_islands) or cell in fine_edges:
                    fine_tiles.add(cell)


def covered(x, y):
    coarse_cell = (math.floor(x / COARSE), math.floor(y / COARSE))
    if coarse_cell in boundary:
        return (math.floor(x / FINE), math.floor(y / FINE)) in fine_tiles
    return coarse_cell in coarse_tiles


sampled_water_points = [(1985.23, -3138.47)]
for ring in RINGS:
    for index in range(0, len(ring), 10):
        a = ring[index]
        b = ring[(index + 1) % len(ring)]
        length = math.dist(a, b)
        if length < 1e-6:
            continue
        mid_x = (a[0] + b[0]) * 0.5
        mid_y = (a[1] + b[1]) * 0.5
        for sign in (-1, 1):
            x = mid_x + sign * 2.0 * (b[1] - a[1]) / length
            y = mid_y - sign * 2.0 * (b[0] - a[0]) / length
            shore, islands = water_intersections(y)
            if is_water(x, shore, islands):
                sampled_water_points.append((x, y))


uncovered = [p for p in sampled_water_points if not covered(*p)]
tile_area = len(coarse_tiles) * COARSE * COARSE + len(fine_tiles) * FINE * FINE


def polygon_area(ring):
    return abs(sum(a[0] * ring[(index + 1) % len(ring)][1]
                   - ring[(index + 1) % len(ring)][0] * a[1]
                   for index, a in enumerate(ring)) / 2)


source_area = polygon_area(OUTER) - sum(polygon_area(island) for island in DATA["islands"])
print(f"coarse tiles={len(coarse_tiles)} fine tiles={len(fine_tiles)} total={len(coarse_tiles) + len(fine_tiles)}")
print(f"water samples covered={len(sampled_water_points) - len(uncovered)}/{len(sampled_water_points)}")
print(f"tile area={tile_area / 1e6:.3f} km2, source area={source_area / 1e6:.3f} km2")
assert not uncovered, f"uncovered water near shoreline: {uncovered[:5]}"
assert len(coarse_tiles) + len(fine_tiles) < 150_000
assert 0 <= (tile_area - source_area) / source_area < 0.10
