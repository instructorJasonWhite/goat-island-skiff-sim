# Lake Greenwood aerial terrain color

`greenwood_naip_rgb_4096.png` is a 4096 × 4096 natural-color image of the
32.256 km terrain square. It is a visual terrain texture for the Unreal map.
`greenwood_naip_manifest.json` contains the exact request URL, returned extent,
pixel crop, and SHA-256 for each of the 16 source tiles. The individual
download tiles are caches and are omitted from this repository.

## Source and reuse

- [USGS National Map NAIP ImageServer](https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer) supplied the pixels. Its description identifies the USDA Farm Service Agency as the partner and lists the attribution “USGS, USDA, The National Map: Orthoimagery.”
- [USGS NAIP archive](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-aerial-photography-national-agriculture-imagery-program-naip) identifies NAIP imagery as public domain. Credit USGS and USDA when redistributing this game imagery.
- An ImageServer `identify` at the map origin returned scene `m_3408248_se_17_060_20230409`, acquired 2023-04-09, at 0.6 m source resolution. The service can mosaic multiple scenes across the 32 km square, so this date must not be assumed for every pixel.

The original 0.6 m aerial photos were downsampled to 7.875 m/pixel to keep
the whole-lake game texture practical. This texture will not show individual
docks, shallow water, current shoreline conditions, or navigational hazards.

## Alignment

The top left is west/north, and the bottom right is east/south. The image
covers local east and north coordinates from -16,128 m to +16,128 m around
longitude -82.0408735°, latitude 34.265721°. This uses the same local
equirectangular projection as `greenwood_usgs.json` and the 2017 × 2017
terrain elevation grid. The build script records the *actual* extent that
ArcGIS returned, then crops each tile to exact local metre bounds before
assembling the image; ArcGIS can adjust requested extents to fit image aspect.

In Unreal, the procedural terrain mesh must set UV0 to
`(column / (GridWidth - 1), row / (GridHeight - 1))`, where grid column 0 is
west and grid row 0 is north. Apply
`/Game/Environment/M_GreenwoodNAIP.M_GreenwoodNAIP` to those mesh sections.

`greenwood_naip_alignment_qa.jpg` overlays the USGS NHD lake shoreline in
yellow and located landmarks in orange for visual georeference inspection.
It is a QA image, not a game asset. Water level and survey date differences
can cause small local offsets between photographed and vector shorelines.

## Regeneration

Run `build_naip.py` with Python, Pillow and an internet connection. It fetches
public ImageServer exports only. The `output` image is deterministic for the
saved source tiles, but a future service update can change newly fetched
imagery. Run the content-only Unreal author's `scripts/import_naip.py` via
UnrealEditor-Cmd `-run=pythonscript` to regenerate the `/Game/Environment`
texture and material packages.
