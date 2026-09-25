"""Validate lake files before loading them into either game prototype."""

import argparse
import json
import math
import sys
from pathlib import Path


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _ring_issue(ring, label):
    if not isinstance(ring, list) or len(ring) < 3:
        return f"{label} must contain at least three points"
    if any(not isinstance(point, list) or len(point) != 2 or not all(map(_number, point)) for point in ring):
        return f"{label} must contain finite [x, y] points"
    area2 = sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1] for i in range(len(ring)))
    if abs(area2) < 1:
        return f"{label} has zero or negligible area"
    return None


def _inside(point, ring):
    x, y = point
    contained = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_cross:
                contained = not contained
        previous = current
    return contained


def validate_map(data):
    issues = []
    if not isinstance(data, dict):
        return ["map must be a JSON object"]
    for key in ("id", "name", "description"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            issues.append(f"{key} must be nonempty text")
    for key in ("approximate", "navigational_use"):
        if not isinstance(data.get(key), bool):
            issues.append(f"{key} must be true or false")

    water = data.get("water_polygon")
    water_issue = _ring_issue(water, "water_polygon")
    if water_issue:
        issues.append(water_issue)

    islands = data.get("islands")
    if not isinstance(islands, list):
        issues.append("islands must be a list")
        islands = []
    else:
        for index, island in enumerate(islands):
            problem = _ring_issue(island, f"islands[{index}]")
            if problem:
                issues.append(problem)
            elif not water_issue and any(not _inside(point, water) for point in island):
                issues.append(f"islands[{index}] extends beyond water_polygon")

    bounds = data.get("bounds_m")
    if not isinstance(bounds, dict) or any(not _number(bounds.get(key)) for key in ("min_x", "max_x", "min_y", "max_y")):
        issues.append("bounds_m needs finite min_x, max_x, min_y, max_y")
    elif not (bounds["min_x"] < bounds["max_x"] and bounds["min_y"] < bounds["max_y"]):
        issues.append("bounds_m minimums must be below maximums")

    spawn = data.get("spawn")
    if not isinstance(spawn, dict) or any(not _number(spawn.get(key)) for key in ("x_m", "y_m", "heading_deg")):
        issues.append("spawn needs finite x_m, y_m, heading_deg")
    elif not water_issue:
        point = (spawn["x_m"], spawn["y_m"])
        if not _inside(point, water) or any(_ring_issue(island, "island") is None and _inside(point, island) for island in islands):
            issues.append("spawn must lie in water and outside islands")

    wind = data.get("wind")
    if not isinstance(wind, dict) or any(not _number(wind.get(key)) for key in ("from_deg", "speed_mps", "gust_mps")):
        issues.append("wind needs finite from_deg, speed_mps, gust_mps")
    elif wind["speed_mps"] < 0 or wind["gust_mps"] < 0:
        issues.append("wind speed_mps and gust_mps must be nonnegative")
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Lake JSON files (default: all maps beside this script)")
    args = parser.parse_args()
    paths = args.paths or [path for path in Path(__file__).parent.glob("*.json")]
    failures = 0
    for path in paths:
        try:
            issues = validate_map(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            issues = [str(exc)]
        if issues:
            failures += 1
            for issue in issues:
                print(f"{path}: {issue}")
        else:
            print(f"{path}: valid")
    return int(failures > 0)


if __name__ == "__main__":
    sys.exit(main())
