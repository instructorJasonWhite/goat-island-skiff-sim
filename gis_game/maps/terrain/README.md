# Lake Greenwood terrain for Unreal

`greenwood_2017_s16m.r16` is a real-elevation Landscape heightmap covering the
complete Lake Greenwood map. Its 2,017 × 2,017 vertices are 16 m apart, for a
32.256 km square centered on the origin in `../greenwood_usgs.json`. The companion
manifest has explicit fields for the C++ terrain importer as well as Unreal
Landscape import settings.

## Build or refresh

Run with Python 3 and `numpy` and `Pillow` installed:

```powershell
python .\output\gis_game\maps\terrain\build_terrain.py
python -m unittest discover -s .\output\gis_game\maps\terrain -p 'test_*.py' -v
```

The script reuses a locally cached Float32 GeoTIFF when present. That download
cache is omitted from this repository, so a fresh clone fetches the
[USGS 3DEP elevation export](https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer).
`--existing-tiff` can point to a copy of the same export. The raw TIFF, the
request URL, its retrieval timestamp, and its SHA-256 digest are recorded in
the manifest. The service may update its underlying terrain over time.

## Import alignment

- `greenwood_2017_s16m.r16` is raw, unsigned little-endian 16-bit, west to east
  in each row, with the first row at the **north** edge.
- The manifest's top-level `x_min_m`, `y_min_m`, `x_max_m`, `y_max_m` use the
  same east/north local metres as `greenwood_usgs.json`. The center vertex
  (row 1008, column 1008) is local (0, 0).
- In Landscape import, set X and Y Scale to **1600 cm**, Z Scale to **100**,
  and location Z to **0 cm**. The exact code mapping is
  `world_z_cm = (R16 - 32768) × 0.78125`. The world water plane is Z = 0.
  Check the `Flip Y Axis` setting against a known north-shore feature before
  adding scenery; the raw rows themselves run north to south.
- The estimated water zero corresponds to **132.649230957 m NAVD88**, derived
  from hydroflattened USGS elevation cells in the main basin near the map
  spawn. It is not a live lake gauge reading.
- [Unreal 5.8 heightmap import](https://dev.epicgames.com/documentation/unreal-engine/importing-and-exporting-landscape-heightmaps-in-unreal-engine)
  supports R16 and `Flip Y Axis`. Use a Landscape with World Partition for the
  full map, or create a smaller playable sector while keeping these local
  coordinates.

## Data and limits

The source is the [USGS 3DEP bare-earth DEM service](https://www.usgs.gov/3d-elevation-program/about-3dep-products-services).
The [underlying 1/3 arc-second 3DEP product](https://data.usgs.gov/datacatalog/data/USGS%3A3a81321b-c153-416f-98b7-cc8e5f0e17c3)
is public domain, around 10 m nominal resolution, and uses NAVD88 metres in
the continental US. The dynamic service rasterizes the request to a square
degree-pixel GeoTIFF; this export's sampled spacing is approximately 19.4 m
north/south and 16.0 m east/west. The processor reads its *actual* georeference
and resamples onto the 16 m local game grid. This resampling does not create
additional terrain detail. The QA image overlays the existing USGS-derived
lake polygon on shaded elevations for alignment review.

The DEM is hydroflattened: it does **not** contain lake bathymetry, navigable
depths, underwater shore slopes, bridge geometry, docks, dam structures,
trees, or buildings. Keep water/boat collision behavior separate from this
terrain heightmap. The main-basin water zero is an estimate; verify it against
a gauge with compatible vertical datum before treating it as a surveyed water
surface or importing surveyed objects.
