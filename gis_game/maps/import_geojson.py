"""Turn a GeoJSON lake polygon into a local-metre game map."""

import argparse
import json
import math
import re
import sys
from pathlib import Path

from validate_maps import _inside, validate_map


METRES_PER_DEGREE = 111_319.49


def _area(ring):
    return abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(ring, ring[1:] + ring[:1]))) / 2


def _polygons(source):
    kind = source.get("type")
    if kind == "FeatureCollection":
        return [polygon for feature in source.get("features", []) for polygon in _polygons(feature)]
    if kind == "Feature":
        return _polygons(source.get("geometry") or {})
    if kind == "Polygon":
        return [source.get("coordinates", [])]
    if kind == "MultiPolygon":
        return source.get("coordinates", [])
    return []


def _ring(points):
    if not isinstance(points, list) or len(points) < 3 or any(
        not isinstance(point, list) or len(point) < 2 or
        not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in point[:2])
        for point in points
    ):
        raise ValueError("GeoJSON contains an invalid polygon ring")
    if len(points) > 3 and points[0][:2] == points[-1][:2]:
        points = points[:-1]
    return [[float(point[0]), float(point[1])] for point in points]


def _find_spawn(outer, holes, bounds):
    center = ((bounds[0] + bounds[1]) / 2, (bounds[2] + bounds[3]) / 2)
    for count in (1, 5, 15, 35):
        for row in range(count):
            for col in range(count):
                if count == 1:
                    point = center
                else:
                    point = (bounds[0] + (col + 0.5) * (bounds[1] - bounds[0]) / count,
                             bounds[2] + (row + 0.5) * (bounds[3] - bounds[2]) / count)
                if _inside(point, outer) and not any(_inside(point, hole) for hole in holes):
                    return point
    raise ValueError("Could not locate an open-water spawn; set spawn manually")


def convert_geojson(source, name, source_note, map_id=None, source_url=""):
    candidates = _polygons(source)
    if not candidates:
        raise ValueError("GeoJSON needs a Polygon or MultiPolygon feature")
    chosen = max(candidates, key=lambda polygon: _area(_ring(polygon[0])) if polygon else 0)
    rings = [_ring(ring) for ring in chosen]
    outer_lonlat = rings[0]
    lon0 = (min(point[0] for point in outer_lonlat) + max(point[0] for point in outer_lonlat)) / 2
    lat0 = (min(point[1] for point in outer_lonlat) + max(point[1] for point in outer_lonlat)) / 2
    east_scale = METRES_PER_DEGREE * math.cos(math.radians(lat0))
    if abs(east_scale) < 1:
        raise ValueError("Local east-west projection is unstable at this latitude")

    def project(ring):
        return [[round((lon - lon0) * east_scale, 3), round((lat - lat0) * METRES_PER_DEGREE, 3)] for lon, lat in ring]

    outer = project(rings[0])
    islands = [project(ring) for ring in rings[1:]]
    xs = [point[0] for point in outer]
    ys = [point[1] for point in outer]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    spawn_x, spawn_y = _find_spawn(outer, islands, (min_x, max_x, min_y, max_y))
    margin = max(max_x - min_x, max_y - min_y) * 0.05
    slug = map_id or re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    result = {
        "id": slug,
        "name": name,
        "approximate": True,
        "navigational_use": False,
        "description": f"A sailing-game area converted from {source_note}. Verify shoreline and scale before treating it as geographically faithful.",
        "source_note": f"{source_note}. Largest connected polygon selected; local equirectangular projection centered near {lat0:.6f}° N, {lon0:.6f}° E.",
        "source_url": source_url,
        "coordinate_system": "local metres; +x east,+y north; heading/from_deg clockwise from north",
        "bounds_m": {"min_x": min_x - margin, "max_x": max_x + margin, "min_y": min_y - margin, "max_y": max_y + margin},
        "water_polygon": outer,
        "islands": islands,
        "spawn": {"x_m": spawn_x, "y_m": spawn_y, "heading_deg": 0},
        "wind": {"from_deg": 315, "speed_mps": 5.8, "gust_mps": 2.0},
    }
    issues = validate_map(result)
    if issues:
        raise ValueError("Converted map failed validation: " + "; ".join(issues))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input GeoJSON with a Polygon or MultiPolygon")
    parser.add_argument("output", type=Path, help="Output game lake JSON")
    parser.add_argument("--name", required=True, help="Visible name of the lake")
    parser.add_argument("--source", required=True, help="Where the GeoJSON shoreline came from")
    parser.add_argument("--source-url", default="", help="Optional URL for source attribution")
    args = parser.parse_args()
    try:
        source = json.loads(args.input.read_text(encoding="utf-8"))
        result = convert_geojson(source, args.name, args.source, source_url=args.source_url)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Wrote {args.output} ({len(result['water_polygon'])} shoreline points)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
