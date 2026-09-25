# Lake files

The game reads one JSON file per sailing area. `greenwood_usgs.json` is the
Lake Greenwood, South Carolina, map derived from a U.S. Geological Survey
shoreline polygon. `greenwood_prototype.json` remains an original,
**schematic** training reach. Neither map is for navigation.

## Lake Greenwood GIS map

`greenwood_usgs.json` uses the [USGS National Hydrography Dataset Waterbody -
Large Scale layer](https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/12),
feature `GNIS_ID 01237668` / `OBJECTID 5125269`, retrieved 2026-09-24. The
source feature reports an area of 41.93845325 square kilometres. Its main
shoreline has 13,714 points after removal of the duplicate closing point,
plus 35 island rings with 507 points. The local projected area is about
42.037 square kilometres. The projection origin is longitude -82.0408735°,
latitude 34.265721°; `x` is east and `y` is north in metres. This simple local
projection places the source polygon within about 29 km east-west and 22 km
north-south. The spawn point is inside the water polygon, outside every
island, and approximately 186 metres from the nearest shoreline segment.

The exact [USGS query](https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/12/query?where=GNIS_ID%3D%2701237668%27&outFields=GNIS_NAME%2CGNIS_ID%2CAREASQKM%2COBJECTID&returnGeometry=true&outSR=4326&geometryPrecision=6&f=geojson)
is recorded in the map as `source_query_url`, and the returned WGS84 feature
is saved as `greenwood_usgs_source.geojson` to allow a reproducible conversion.
[USGS identifies NHD data as public domain](https://www.usgs.gov/media/files/national-hydrography-product-information-document)
and asks for source credit. Credit: U.S. Geological Survey.

The polygon represents the source shoreline, not a current water level or
soundings. The game does not model depth, shoals, docks, buoys, hazards, or
bridge clearance. The starting wind is a scenario setting, not live weather.

## Add a lake

1. Copy `greenwood_prototype.json` and give the copy a new `id` and `name`.
2. Edit `water_polygon` as a clockwise or counterclockwise outline in local
   metres. Points are `[east, north]`; the game closes the last edge to the
   first point automatically. Add zero or more `islands` in the same form.
3. Set `bounds_m` large enough to contain the entire lake, a `spawn` point in
   open water, and the starting `wind`. Wind `from_deg` and spawn
   `heading_deg` are compass bearings: 0 north, 90 east.
4. Describe the source and accuracy in `description` and `source_note`.
   Keep `navigational_use` false for game maps. If the coastline is an
   artistic approximation, set `approximate` true.
5. Run `python validate_maps.py your_lake.json`. In the browser game, select
   that JSON using the map picker or load `?map=../maps/your_lake.json` while
   serving the `gis_game` folder.

The polygon is surface art and a shore boundary. It is **not** a bathymetry,
current, bridge clearance, or hazard model. The USGS Lake Greenwood map above
replaces the original schematic default; the original remains available as a
small practice course.

If you have a lake outline as GeoJSON, `import_geojson.py` converts its
largest Polygon or MultiPolygon part to this format. For example:

```text
python import_geojson.py shoreline.geojson my_lake.json --name "My Lake" --source "County GIS export" --source-url "https://example.org/data"
python validate_maps.py my_lake.json
```

It converts longitude and latitude to a local metre grid, retains polygon
holes as islands, and chooses an initial open-water spawn. Review the output
map, particularly when the source has multiple disconnected water bodies or
complex shoreline geometry. The exporter labels converted maps approximate.

## Format

| Field | Meaning |
| --- | --- |
| `id`, `name`, `description` | Stable map identifier and visible text |
| `approximate`, `navigational_use` | Accuracy and safety labels |
| `coordinate_system` | Explanation of point and bearing units |
| `bounds_m` | View/world bounds `{min_x,max_x,min_y,max_y}` |
| `water_polygon` | Outer water ring of `[east_m,north_m]` points |
| `islands` | Zero or more land rings inside the water ring |
| `spawn` | `{x_m,y_m,heading_deg}` initial boat position |
| `wind` | `{from_deg,speed_mps,gust_mps}` initial conditions |

The validator checks types, nonzero polygon area, island containment, and a
spawn point in open water. It does not detect every self-intersection or
prove that a GIS shoreline is geographically correct.
