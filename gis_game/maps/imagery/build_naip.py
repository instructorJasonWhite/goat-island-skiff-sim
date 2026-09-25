"""Fetch and align public-domain USGS/USDA NAIP imagery to the GIS terrain grid.

The USGS ImageServer is asked for a natural-color JPEG in EPSG:4326.  ArcGIS
may expand a requested bounding box to match the output aspect ratio, so this
script uses the *returned* extent when resampling to our local metre grid.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
MAPS = ROOT.parent
SERVICE = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer"
LON0 = -82.0408735
LAT0 = 34.265721
METRES_PER_DEGREE = 111319.49
EXTENT_M = 16128.0
SIZE = 4096
TILE_COUNT = 4
TILE_PIXELS = SIZE // TILE_COUNT
EXPORT_SIZE = (1024, 847)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def local_to_lonlat(east: float, north: float) -> tuple[float, float]:
    return (
        LON0 + east / (METRES_PER_DEGREE * math.cos(math.radians(LAT0))),
        LAT0 + north / METRES_PER_DEGREE,
    )


def fetch(url: str, destination: Path) -> None:
    for attempt in range(4):
        try:
            request = Request(url, headers={"User-Agent": "GISGame/1.0 (USGS NAIP terrain visual)"})
            with urlopen(request, timeout=180) as response, destination.open("wb") as target:
                for block in iter(lambda: response.read(1024 * 1024), b""):
                    target.write(block)
            return
        except Exception:
            destination.unlink(missing_ok=True)
            if attempt == 3:
                raise
            time.sleep((attempt + 1) * 3)


def download_tile(row: int, column: int) -> dict:
    tile_metres = 2 * EXTENT_M / TILE_COUNT
    east_min = -EXTENT_M + column * tile_metres
    east_max = east_min + tile_metres
    north_max = EXTENT_M - row * tile_metres
    north_min = north_max - tile_metres
    west, south = local_to_lonlat(east_min, north_min)
    east, north = local_to_lonlat(east_max, north_max)
    # ArcGIS adjusts the requested extent to its output pixel aspect.  A small
    # perimeter gives the precise terrain crop source pixels on every edge.
    pad_lon = (east - west) * 0.01
    pad_lat = (north - south) * 0.01
    query = {
        "bbox": f"{west-pad_lon:.12f},{south-pad_lat:.12f},{east+pad_lon:.12f},{north+pad_lat:.12f}",
        "bboxSR": "4326",
        "imageSR": "4326",
        "size": f"{EXPORT_SIZE[0]},{EXPORT_SIZE[1]}",
        "format": "jpg",
        "interpolation": "RSP_BilinearInterpolation",
        "renderingRule": json.dumps({"rasterFunction": "NaturalColor"}, separators=(",", ":")),
        "f": "json",
    }
    request_url = SERVICE + "/exportImage?" + urlencode(query)
    stem = f"usgs_naip_pad01_r{row}_c{column}"
    response_file = ROOT / (stem + "_response.json")
    if not response_file.exists():
        fetch(request_url, response_file)
    response = json.loads(response_file.read_text(encoding="utf-8"))
    if "error" in response:
        raise RuntimeError(f"USGS NAIP export failed: {response['error']}")
    if (response["width"], response["height"]) != EXPORT_SIZE:
        raise RuntimeError(f"Unexpected export size: {response}")
    source_file = ROOT / (stem + ".jpg")
    if not source_file.exists():
        fetch(response["href"], source_file)
    image = Image.open(source_file).convert("RGB")
    if image.size != EXPORT_SIZE:
        raise RuntimeError(f"Downloaded image size {image.size} differs from metadata")

    extent = response["extent"]
    actual = [extent["xmin"], extent["ymin"], extent["xmax"], extent["ymax"]]
    if not (actual[0] <= west < east <= actual[2] and actual[1] <= south < north <= actual[3]):
        raise RuntimeError(f"Returned extent does not contain tile bounds: {actual}")
    left = (west - actual[0]) / (actual[2] - actual[0]) * image.width
    top = (actual[3] - north) / (actual[3] - actual[1]) * image.height
    right = (east - actual[0]) / (actual[2] - actual[0]) * image.width
    bottom = (actual[3] - south) / (actual[3] - actual[1]) * image.height
    fitted = image.transform(
        (TILE_PIXELS, TILE_PIXELS), Image.Transform.EXTENT,
        (left, top, right, bottom), resample=Image.Resampling.BICUBIC,
    )
    return {
        "row": row, "column": column, "request_url": request_url,
        "requested_bbox_lonlat": [west, south, east, north],
        "returned_bbox_lonlat": actual,
        "crop_pixel_edges_in_source": [left, top, right, bottom],
        "source_jpg": source_file.name,
        "source_jpg_sha256": sha256(source_file),
        "source_jpg_bytes": source_file.stat().st_size,
        "fitted": fitted,
    }


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    west, south = local_to_lonlat(-EXTENT_M, -EXTENT_M)
    east, north = local_to_lonlat(EXTENT_M, EXTENT_M)
    target = Image.new("RGB", (SIZE, SIZE))
    tiles = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(download_tile, row, column): (row, column)
                   for row in range(TILE_COUNT) for column in range(TILE_COUNT)}
        for future in as_completed(futures):
            tile = future.result()
            target.paste(tile.pop("fitted"), (tile["column"] * TILE_PIXELS,
                                             tile["row"] * TILE_PIXELS))
            tiles.append(tile)
            print(f"NAIP tile {len(tiles)}/{TILE_COUNT * TILE_COUNT}: "
                  f"row {tile['row']} column {tile['column']}", flush=True)
    tiles.sort(key=lambda item: (item["row"], item["column"]))
    output_file = ROOT / "greenwood_naip_rgb_4096.png"
    target.save(output_file, optimize=True)

    # The shoreline QA confirms orientation and that the geographic crop lands
    # on the same local coordinates as the NHD polygon and landmark catalog.
    qa = target.resize((1536, 1536), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(qa)
    map_data = json.loads((MAPS / "greenwood_usgs.json").read_text(encoding="utf-8"))

    def pixel(point: list[float] | tuple[float, float]) -> tuple[float, float]:
        return (
            (point[0] + EXTENT_M) / (2 * EXTENT_M) * qa.width,
            (EXTENT_M - point[1]) / (2 * EXTENT_M) * qa.height,
        )

    for ring in [map_data["water_polygon"], *map_data["islands"]]:
        if len(ring) > 1:
            draw.line([pixel(point) for point in ring], fill=(255, 215, 28), width=2, joint="curve")
    landmarks = json.loads((MAPS / "landmarks" / "greenwood_landmarks.json").read_text(encoding="utf-8"))
    for feature in landmarks["features"]:
        point = feature.get("local_xy_m") or [feature.get("east_m"), feature.get("north_m")]
        if point[0] is None:
            continue
        px, py = pixel(point)
        draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=(255, 64, 22))
    qa_file = ROOT / "greenwood_naip_alignment_qa.jpg"
    qa.save(qa_file, quality=90)

    metadata = {
        "name": "Lake Greenwood NAIP aerial terrain color",
        "source": "USGS National Map NAIP Imagery, USDA Farm Service Agency",
        "service_url": SERVICE,
        "terms_url": "https://www.usgs.gov/centers/eros/science/usgs-eros-archive-aerial-photography-national-agriculture-imagery-program-naip",
        "license": "Public domain (USGS states its NAIP imagery download is public domain)",
        "attribution": "USGS, USDA, The National Map: Orthoimagery",
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "request_bbox_lonlat": [west, south, east, north],
        "source_tile_grid": [TILE_COUNT, TILE_COUNT],
        "source_tile_pixels": list(EXPORT_SIZE),
        "source_tiles": tiles,
        "output_pixels": [SIZE, SIZE],
        "output_metres_per_pixel": 2 * EXTENT_M / SIZE,
        "output_edge_bounds_local_m": [-EXTENT_M, -EXTENT_M, EXTENT_M, EXTENT_M],
        "output_orientation": "top row north; left column west",
        "unreal_uv": "U=(column/(GridWidth-1)); V=(row/(GridHeight-1)) on terrain vertices",
        "output_png_sha256": sha256(output_file),
        "qa_image": qa_file.name,
        "note": "NAIP is historic aerial photography. Road/shoreline changes after acquisition are possible. The image is a downsampled visual texture, not a navigational chart.",
    }
    (ROOT / "greenwood_naip_manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output_file),
                      "source_bytes": sum(t["source_jpg_bytes"] for t in tiles),
                      "output_bytes": output_file.stat().st_size,
                      "tile_count": len(tiles)}, indent=2))


if __name__ == "__main__":
    main()
