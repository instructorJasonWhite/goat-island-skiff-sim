"""Build a sourced Lake Greenwood landmark catalog from saved public GIS extracts.

Run ``python build_catalog.py`` to regenerate the JSON, GeoJSON, and QA map.
Run ``python build_catalog.py --refresh`` to re-query the source services first.
Coordinates are for visual game placement only, never for navigation.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
MAP_FILE = HERE.parent / "greenwood_usgs.json"
ORIGIN_LON = -82.0408735
ORIGIN_LAT = 34.265721
METRES_PER_DEGREE = 111_319.49
EAST_SCALE = METRES_PER_DEGREE * math.cos(math.radians(ORIGIN_LAT))
RETRIEVED = "2026-09-24"

SOURCE_URLS = {
    "scdot_bridges": "https://gis.scdot.org/hosting/rest/services/Bridges/FeatureServer/4",
    "scdnr_ramps": "https://services.arcgis.com/F7DSX1DSNSiWmOqh/arcgis/rest/services/Boat_Ramps/FeatureServer/0",
    "usace_nid": "https://geospatial.sec.usace.army.mil/dls/rest/services/NID/National_Inventory_of_Dams_Public_Service/FeatureServer/0",
    "usgs_rail": "https://carto-wfs.nationalmap.gov/arcgis/rest/services/transportation/MapServer/6",
    "usgs_roads": "https://carto-wfs.nationalmap.gov/arcgis/rest/services/transportation/MapServer",
}
SOURCE_LICENSES = {
    "scdot_bridges": "Public SCDOT GIS service; no explicit redistribution license stated.",
    "scdnr_ramps": "Public SCDNR-derived GIS copy; no explicit license stated; credit SCDNR and The Nature Conservancy.",
    "usace_nid": "U.S. federal government public data.",
    "usgs_rail": "USGS National Map public domain; credit USGS and FRA.",
    "usgs_roads": "USGS National Map public domain; source road linework from U.S. Census Bureau TIGER/Line.",
}
BBOX = "geometry=-82.20%2C34.13%2C-81.85%2C34.36&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&returnGeometry=true&outSR=4326"
QUERIES = {
    "scdot_bridges.json": SOURCE_URLS["scdot_bridges"] + "/query?where=1%3D1&outFields=*&" + BBOX + "&f=json",
    "scdnr_ramps.json": SOURCE_URLS["scdnr_ramps"] + "/query?where=WATER_BODY%20LIKE%20%27%25GREENWOOD%25%27&outFields=*&returnGeometry=true&outSR=4326&f=json",
    "nid_dam.json": SOURCE_URLS["usace_nid"] + "/query?where=1%3D1&outFields=NIDID%2CNAME%2COTHER_NAMES%2CLATITUDE%2CLONGITUDE%2CCOUNTYSTATE%2CRIVER_OR_STREAM%2CYEAR_COMPLETED&geometry=-81.93%2C34.15%2C-81.88%2C34.19&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&returnGeometry=true&outSR=4326&f=json",
    "usgs_rail.geojson": SOURCE_URLS["usgs_rail"] + "/query?where=1%3D1&outFields=*&" + BBOX + "&f=geojson",
}

# Only these source records actually touch the mapped lake. Twin SC 72 records
# are retained separately because they represent two bridge structures.
ROAD_BRIDGES = {
    80524: ("US 221 / SC 72 Saluda River bridge", "major-road-bridge"),
    80527: ("SC 72 Cane Creek south bridge", "road-bridge"),
    80528: ("SC 72 Cane Creek north bridge", "road-bridge"),
    80525: ("S-33 upper Saluda River bridge", "road-bridge"),
    80526: ("S-29 Reedy River bridge", "road-bridge"),
    80477: ("S-91 Lake Greenwood bay bridge", "road-bridge"),
    80534: ("S-307 Rabon Creek bridge", "road-bridge"),
    80529: ("S-344 Banks Creek bridge", "road-bridge"),
    80450: ("L-95 Mulberry Creek bridge", "road-bridge"),
}
RAMPS = {
    24001: "Greenwood Shores public ramp",
    24002: "Lake Greenwood State Park ramp",
    24003: "Souls Harbor public ramp",
    24004: "Greenwood Access Area ramp",
}


def road_query_url(record: int, lon: float, lat: float) -> str:
    layer = 4 if record == 80524 else 5 if record in (80527, 80528) else 7
    radius = 0.002 if record == 80526 else 0.004
    envelope = ",".join(f"{value:.8f}" for value in
                        (lon - radius, lat - radius, lon + radius, lat + radius))
    return (f"{SOURCE_URLS['usgs_roads']}/{layer}/query?where=1%3D1&outFields=*"
            f"&geometry={quote(envelope, safe='')}&geometryType=esriGeometryEnvelope"
            "&inSR=4326&spatialRel=esriSpatialRelIntersects"
            "&returnGeometry=true&outSR=4326&f=json")


def project(lon: float, lat: float) -> tuple[float, float]:
    return ((lon - ORIGIN_LON) * EAST_SCALE, (lat - ORIGIN_LAT) * METRES_PER_DEGREE)


def unproject(east: float, north: float) -> tuple[float, float]:
    return (ORIGIN_LON + east / EAST_SCALE, ORIGIN_LAT + north / METRES_PER_DEGREE)


def refresh() -> None:
    raw = HERE / "raw"
    raw.mkdir(exist_ok=True)
    for filename, url in QUERIES.items():
        request = Request(url, headers={"User-Agent": "GIS-Sim-Landmark-Builder/1.0"})
        with urlopen(request, timeout=60) as response:
            data = response.read()
        parsed = json.loads(data)
        if "error" in parsed or not parsed.get("features"):
            raise RuntimeError(f"GIS query failed or was empty: {url}")
        (raw / filename).write_bytes(data)
    bridges = {int(f["attributes"]["ID"]): f for f in
               json.loads((raw / "scdot_bridges.json").read_text())["features"]}
    for record in ROAD_BRIDGES:
        geometry = bridges[record]["geometry"]
        url = road_query_url(record, geometry["x"], geometry["y"])
        with urlopen(Request(url, headers={"User-Agent": "GIS-Sim-Landmark-Builder/1.0"}), timeout=60) as response:
            data = response.read()
        parsed = json.loads(data)
        if "error" in parsed or not parsed.get("features"):
            raise RuntimeError(f"Road alignment query failed or was empty: {url}")
        (raw / f"usgs_road_{record}.json").write_bytes(data)


def load_raw(filename: str) -> dict:
    data = json.loads((HERE / "raw" / filename).read_text(encoding="utf-8"))
    if "error" in data or not data.get("features"):
        raise ValueError(f"Invalid source extract: {filename}")
    return data


def make_feature(feature_id: str, name: str, kind: str, lon: float, lat: float,
                 source_id: str, source_record: str, confidence: str,
                 note: str, **extra) -> dict:
    east, north = project(lon, lat)
    return {
        "id": feature_id,
        "name": name,
        "type": kind,
        "latitude": round(lat, 8),
        "longitude": round(lon, 8),
        "east_m": round(east, 3),
        "north_m": round(north, 3),
        "source_id": source_id,
        "source_record": source_record,
        "source_url": SOURCE_URLS[source_id],
        "license": SOURCE_LICENSES[source_id],
        "confidence": confidence,
        "accuracy_note": note,
        **extra,
    }


def water_mask(lake: dict, metres_per_pixel: float = 5.0):
    bounds = lake["bounds_m"]
    width = math.ceil((bounds["max_x"] - bounds["min_x"]) / metres_per_pixel) + 1
    height = math.ceil((bounds["max_y"] - bounds["min_y"]) / metres_per_pixel) + 1

    def pixel(east, north):
        return (round((east - bounds["min_x"]) / metres_per_pixel),
                round((bounds["max_y"] - north) / metres_per_pixel))

    image = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(image)
    draw.polygon([pixel(*point) for point in lake["water_polygon"]], fill=255)
    for island in lake["islands"]:
        draw.polygon([pixel(*point) for point in island], fill=0)

    def contains(point):
        x, y = pixel(*point)
        return 0 <= x < width and 0 <= y < height and image.getpixel((x, y)) > 0

    return contains


def rail_water_runs(line: list, contains) -> list[list[tuple[float, float]]]:
    samples = []
    for a, b in zip(line, line[1:]):
        start, end = project(*a), project(*b)
        divisions = max(1, math.ceil(math.dist(start, end) / 5))
        samples.extend((start[0] + (end[0] - start[0]) * i / divisions,
                        start[1] + (end[1] - start[1]) * i / divisions)
                       for i in range(divisions))
    samples.append(project(*line[-1]))
    runs, active = [], []
    for point in samples:
        if contains(point):
            active.append(point)
        elif active:
            if len(active) >= 3:
                runs.append(active)
            active = []
    if len(active) >= 3:
        runs.append(active)
    return runs


def road_span(record: int, point: tuple[float, float], contains) -> dict:
    """Approximate a deck axis where a USGS road crosses mapped water."""
    features = load_raw(f"usgs_road_{record}.json")["features"]

    def distance_to_segment(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length_sq = dx * dx + dy * dy
        t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length_sq)) if length_sq else 0
        return math.dist(p, (a[0] + t * dx, a[1] + t * dy))

    candidates = []
    for source in features:
        for path in source["geometry"].get("paths", []):
            if len(path) < 2:
                continue
            coords = [project(*p) for p in path]
            distance = min(distance_to_segment(point, a, b) for a, b in zip(coords, coords[1:]))
            candidates.append((distance, source, path))
    for distance, source, path in sorted(candidates, key=lambda row: row[0]):
        for run in sorted(rail_water_runs(path, contains),
                          key=lambda line: min(math.dist(point, p) for p in line)):
            if min(math.dist(point, p) for p in run) > 30:
                continue
            start, end = run[0], run[-1]
            span = math.dist(start, end)
            if span < 10 or span > 1500:
                continue
            bearing = math.degrees(math.atan2(end[0] - start[0], end[1] - start[1])) % 180
            return {
                "span_endpoints_m": [[round(v, 3) for v in start], [round(v, 3) for v in end]],
                "span_length_m": round(span, 1),
                "span_bearing_deg": round(bearing, 1),
                "alignment_source_url": SOURCE_URLS["usgs_roads"],
                "alignment_query_url": road_query_url(record, *unproject(*point)),
                "alignment_record": str(source["attributes"].get("OBJECTID", source["attributes"].get("objectid", ""))),
                "alignment_name": source["attributes"].get("name") or "",
                "alignment_offset_m": round(distance, 1),
            }
    raise ValueError(f"No USGS road crossing within 30 m of SCDOT bridge {record}")


def rail_feature(name: str, feature_id: str, source_records: tuple[int, ...],
                 runs: dict[int, list[list[tuple[float, float]]]],
                 selection: str = "longest") -> dict:
    candidates = [run for record in source_records for run in runs[record]
                  if len(run) >= 3]
    if not candidates:
        raise ValueError(f"No mapped water crossing for {feature_id}")
    if selection == "shortest":
        selected = [min(candidates, key=lambda run: sum(math.dist(a, b) for a, b in zip(run, run[1:])))]
    else:
        selected = [max(runs[record], key=lambda run: sum(math.dist(a, b) for a, b in zip(run, run[1:])))
                    for record in source_records]
    endpoint_candidates = [point for run in selected for point in (run[0], run[-1])]
    start, end = max(((a, b) for a in endpoint_candidates for b in endpoint_candidates),
                     key=lambda pair: math.dist(*pair))
    mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    lon, lat = unproject(*mid)
    compass = math.degrees(math.atan2(end[0] - start[0], end[1] - start[1])) % 180
    return make_feature(
        feature_id, name, "rail-crossing", lon, lat, "usgs_rail",
        ",".join(str(record) for record in source_records), "medium",
        "USGS/FRA rail centerline intersects the USGS lake polygon. Segment endpoints and length are inferred at ~5 m sampling; structural form and clearance are not verified.",
        span_endpoints_m=[[round(v, 3) for v in start], [round(v, 3) for v in end]],
        span_length_m=round(math.dist(start, end), 1),
        span_bearing_deg=round(compass, 1),
    )


def build_catalog() -> dict:
    lake = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    bridges = load_raw("scdot_bridges.json")["features"]
    ramps = load_raw("scdnr_ramps.json")["features"]
    dams = load_raw("nid_dam.json")["features"]
    rails = load_raw("usgs_rail.geojson")["features"]
    catalog = {
        "schema_version": 1,
        "map_id": lake["id"],
        "generated_from_extracts_on": RETRIEVED,
        "navigational_use": False,
        "origin": {"longitude": ORIGIN_LON, "latitude": ORIGIN_LAT},
        "coordinate_system": "local east/north metres; +east/+north; bearing clockwise from north",
        "sources": [
            {"id": "scdot_bridges", "title": "South Carolina DOT Bridges feature layer", "url": SOURCE_URLS["scdot_bridges"], "query_url": QUERIES["scdot_bridges.json"], "attribution": "South Carolina Department of Transportation", "license": "No explicit redistribution license stated by public service; factual coordinates and route identifiers extracted."},
            {"id": "scdnr_ramps", "title": "SCDNR Boat Ramps data, ArcGIS public copy", "url": SOURCE_URLS["scdnr_ramps"], "query_url": QUERIES["scdnr_ramps.json"], "attribution": "South Carolina Department of Natural Resources; ArcGIS copy by The Nature Conservancy", "license": "No explicit license on public ArcGIS item; SCDNR metadata lists no access constraint. Facility status may have changed."},
            {"id": "usace_nid", "title": "National Inventory of Dams", "url": SOURCE_URLS["usace_nid"], "query_url": QUERIES["nid_dam.json"], "attribution": "U.S. Army Corps of Engineers, National Inventory of Dams", "license": "U.S. federal government public data."},
            {"id": "usgs_rail", "title": "USGS National Transportation Dataset, FRA rail lines", "url": SOURCE_URLS["usgs_rail"], "query_url": QUERIES["usgs_rail.geojson"], "attribution": "U.S. Geological Survey; Federal Railroad Administration", "license": "USGS National Map public domain; source describes FRA Rail Lines 07/2025."},
            {"id": "usgs_roads", "title": "USGS National Transportation Dataset road centerlines", "url": SOURCE_URLS["usgs_roads"], "attribution": "U.S. Geological Survey; U.S. Census Bureau TIGER/Line", "license": "USGS National Map public domain. Bridge road-line extracts are saved in raw/usgs_road_*.json."},
            {"id": "usgs_shoreline", "title": "USGS NHD Lake Greenwood waterbody polygon", "url": lake["source_url"], "attribution": "U.S. Geological Survey", "license": "Public domain."},
        ],
        "features": [],
    }
    features = catalog["features"]
    contains = water_mask(lake)
    bridges_by_id = {int(f["attributes"]["ID"]): f for f in bridges}
    for record, (name, kind) in ROAD_BRIDGES.items():
        source = bridges_by_id[record]
        geometry, attrs = source["geometry"], source["attributes"]
        features.append(make_feature(
            f"scdot-bridge-{record}", name, kind, geometry["x"], geometry["y"],
            "scdot_bridges", str(record), "high",
            "SCDOT bridge point is sourced; depicted span follows a nearby USGS road centerline clipped against the USGS water polygon. Width, height, piers, and clearance are scenic approximations.",
            route=f"{attrs['RTE_TYPE'].strip()} {attrs['RTE_NBR']}".strip(),
            crossing=attrs["CROSSING"].strip(),
            **road_span(record, project(geometry["x"], geometry["y"]), contains),
        ))
    ramps_by_id = {int(f["attributes"]["FacilityID"]): f for f in ramps}
    for record, name in RAMPS.items():
        source = ramps_by_id[record]
        geometry, attrs = source["geometry"], source["attributes"]
        amenities = ["courtesy_dock"] if record == 24002 else []
        features.append(make_feature(
            f"scdnr-ramp-{record}", name, "public-ramp", geometry["x"], geometry["y"],
            "scdnr_ramps", str(record), "medium",
            "SCDNR-derived access point; older source and location are approximate. Verify present access before real-world use.",
            owner=attrs["Owner"], amenities=amenities,
        ))
    dam_names = {"Buzzards Roost Spillway": "spillway",
                 "Buzzards Roost Embankment": "embankment",
                 "Buzzards Roost Fuse Plug": "fuse-plug"}
    for source in dams:
        geometry, attrs = source["geometry"], source["attributes"]
        if attrs["NAME"] not in dam_names or attrs["NIDID"] != "SC00109":
            continue
        component = dam_names[attrs["NAME"]]
        features.append(make_feature(
            f"nid-sc00109-{component}", attrs["NAME"], "dam-component",
            geometry["x"], geometry["y"], "usace_nid", f"SC00109:{attrs['NAME']}", "high",
            "NID point denotes a dam component, not its full footprint or shoreline barrier geometry.",
            component=component, year_completed=attrs["YEAR_COMPLETED"],
        ))
    runs = {}
    for source in rails:
        record = int(source["properties"]["objectid"])
        if record not in {949354, 963860, 1006682, 1107407}:
            continue
        geometry = source["geometry"]
        lines = [geometry["coordinates"]] if geometry["type"] == "LineString" else geometry["coordinates"]
        runs[record] = [run for line in lines for run in rail_water_runs(line, contains)]
    features.extend([
        rail_feature("CSX upper Lake Greenwood rail crossing", "rail-upper-lake", (949354, 963860), runs),
        rail_feature("CSX lower Lake Greenwood rail crossing", "rail-lower-lake", (1107407, 1006682), runs),
        rail_feature("CSX eastern inlet rail crossing", "rail-eastern-inlet", (1006682,), runs, selection="shortest"),
    ])
    return catalog


def as_geojson(catalog: dict) -> dict:
    features = []
    for item in catalog["features"]:
        geometry = {"type": "Point", "coordinates": [item["longitude"], item["latitude"]]}
        if "span_endpoints_m" in item:
            geometry = {"type": "LineString", "coordinates": [list(unproject(*point)) for point in item["span_endpoints_m"]]}
        features.append({"type": "Feature", "id": item["id"], "geometry": geometry,
                         "properties": {key: value for key, value in item.items()
                                        if key not in {"latitude", "longitude"}}})
    return {"type": "FeatureCollection", "name": "Lake Greenwood verified landmarks",
            "navigational_use": False, "features": features}


def draw_overview(catalog: dict) -> None:
    lake = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    bounds = lake["bounds_m"]
    width, height, map_left, map_top, map_width, map_height = 1700, 1320, 45, 115, 1200, 1040
    scale = min(map_width / (bounds["max_x"] - bounds["min_x"]),
                map_height / (bounds["max_y"] - bounds["min_y"]))

    def pixel(east, north):
        return (round(map_left + (east - bounds["min_x"]) * scale),
                round(map_top + (bounds["max_y"] - north) * scale))

    image = Image.new("RGB", (width, height), "#f7f4ea")
    draw = ImageDraw.Draw(image)
    draw.text((45, 30), "LAKE GREENWOOD  |  SOURCED LANDMARK PLACEMENT", fill="#163445", font=ImageFont.truetype("arialbd.ttf", 30))
    draw.polygon([pixel(*point) for point in lake["water_polygon"]], fill="#579bb5", outline="#246179", width=2)
    for island in lake["islands"]:
        draw.polygon([pixel(*point) for point in island], fill="#f7f4ea", outline="#246179")
    colors = {"major-road-bridge": "#fa721b", "road-bridge": "#fa721b",
              "rail-crossing": "#8e44ad", "dam-component": "#d33937", "public-ramp": "#308d38"}
    font = ImageFont.truetype("arial.ttf", 17)
    bold = ImageFont.truetype("arialbd.ttf", 17)
    for number, item in enumerate(catalog["features"], 1):
        x, y = pixel(item["east_m"], item["north_m"])
        color = colors[item["type"]]
        if "span_endpoints_m" in item:
            draw.line([pixel(*point) for point in item["span_endpoints_m"]], fill=color, width=5)
        draw.text((1270, 125 + (number - 1) * 36), f"{number:02d}  {item['name']}", fill="#163445", font=font)
        if number == 2:
            # The twin Cane Creek deck centres are only 22 m apart: at this
            # overview scale their two numbered bubbles cannot be separated.
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
            continue
        draw.ellipse((x - 13, y - 13, x + 13, y + 13), fill=color, outline="white", width=2)
        label = "2/3" if number == 3 else str(number)
        box = draw.textbbox((0, 0), label, font=bold)
        draw.text((x - (box[2] - box[0]) / 2, y - (box[3] - box[1]) / 2 - 2), label, fill="white", font=bold)
    sx, sy = pixel(lake["spawn"]["x_m"], lake["spawn"]["y_m"])
    draw.ellipse((sx - 9, sy - 9, sx + 9, sy + 9), fill="white", outline="#16415d", width=3)
    draw.text((sx + 12, sy - 10), "spawn", fill="#16415d", font=bold)
    draw.text((1270, 880), "Orange  road bridge", fill=colors["road-bridge"], font=bold)
    draw.text((1270, 910), "Purple  inferred rail span", fill=colors["rail-crossing"], font=bold)
    draw.text((1270, 940), "Red  dam component", fill=colors["dam-component"], font=bold)
    draw.text((1270, 970), "Green  public ramp", fill=colors["public-ramp"], font=bold)
    draw.text((45, 1275), "Source: SCDOT, SCDNR, USACE NID, USGS/FRA, USGS NHD. Visual simulation only; not for navigation.", fill="#45565b", font=font)
    image.save(HERE / "greenwood_landmarks_overview.png", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="query public GIS services before rebuilding")
    args = parser.parse_args()
    if args.refresh:
        refresh()
    catalog = build_catalog()
    (HERE / "greenwood_landmarks.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    (HERE / "greenwood_landmarks.geojson").write_text(json.dumps(as_geojson(catalog), indent=2) + "\n", encoding="utf-8")
    draw_overview(catalog)
    print(f"Wrote {len(catalog['features'])} features in JSON, GeoJSON, and QA overview")


if __name__ == "__main__":
    main()
