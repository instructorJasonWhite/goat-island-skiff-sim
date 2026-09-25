"""Fetch USGS 3DEP elevations and make a Lake Greenwood Unreal R16 heightmap.

The grid deliberately uses the same local east/north metres as
``greenwood_usgs.json``. The TIFF is a float32 source; the R16 is a derived
Unreal Landscape vertex grid. No synthetic elevations are inserted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


SERVICE_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer"
METRES_PER_DEGREE = 111_319.49  # The lake JSON's original local projection.


@dataclass(frozen=True)
class TerrainGrid:
    origin_lon_deg: float
    origin_lat_deg: float
    size: int
    spacing_m: float

    def __post_init__(self):
        if self.size < 3 or self.size % 2 != 1:
            raise ValueError("Unreal terrain size must be odd and at least three")
        if self.spacing_m <= 0 or not math.isfinite(self.spacing_m):
            raise ValueError("Terrain spacing must be positive and finite")

    @classmethod
    def for_lake(cls, lake: dict, size: int = 2017, spacing_m: float = 16):
        grid = cls(lake["origin_lon_deg"], lake["origin_lat_deg"], size, spacing_m)
        min_x, min_y, max_x, max_y = grid.local_bounds_m
        bounds = lake["bounds_m"]
        if (min_x > bounds["min_x"] or max_x < bounds["max_x"] or
                min_y > bounds["min_y"] or max_y < bounds["max_y"]):
            raise ValueError("Terrain grid does not cover the lake map bounds")
        return grid

    @property
    def half_span_m(self) -> float:
        return (self.size - 1) * self.spacing_m / 2

    @property
    def local_bounds_m(self) -> tuple[float, float, float, float]:
        half = self.half_span_m
        return (-half, -half, half, half)

    @property
    def bbox_lonlat(self) -> tuple[float, float, float, float]:
        # ImageServer's bounding box describes *pixel edges*. Expand by half
        # a pixel so first/last returned cell centres land on Landscape vertices.
        half_edge = self.half_span_m + self.spacing_m / 2
        west, south = self.local_to_lonlat(-half_edge, -half_edge)
        east, north = self.local_to_lonlat(half_edge, half_edge)
        return (west, south, east, north)

    def local_to_lonlat(self, east_m: float, north_m: float) -> tuple[float, float]:
        east_scale = METRES_PER_DEGREE * math.cos(math.radians(self.origin_lat_deg))
        return (self.origin_lon_deg + east_m / east_scale,
                self.origin_lat_deg + north_m / METRES_PER_DEGREE)

    def lonlat_to_local(self, lon_deg: float, lat_deg: float) -> tuple[float, float]:
        east_scale = METRES_PER_DEGREE * math.cos(math.radians(self.origin_lat_deg))
        return ((lon_deg - self.origin_lon_deg) * east_scale,
                (lat_deg - self.origin_lat_deg) * METRES_PER_DEGREE)

    def pixel_to_local(self, row: int, col: int) -> tuple[float, float]:
        return ((col - (self.size - 1) / 2) * self.spacing_m,
                ((self.size - 1) / 2 - row) * self.spacing_m)

    def local_to_pixel(self, east_m: float, north_m: float) -> tuple[float, float]:
        middle = (self.size - 1) / 2
        return (middle + east_m / self.spacing_m, middle - north_m / self.spacing_m)


@dataclass(frozen=True)
class GeoRaster:
    elevations_m: np.ndarray
    west_edge_deg: float
    north_edge_deg: float
    pixel_lon_deg: float
    pixel_lat_deg: float

    @property
    def extent_lonlat(self) -> tuple[float, float, float, float]:
        height, width = self.elevations_m.shape
        return (self.west_edge_deg,
                self.north_edge_deg - height * self.pixel_lat_deg,
                self.west_edge_deg + width * self.pixel_lon_deg,
                self.north_edge_deg)


def resample_to_local_grid(source: GeoRaster, grid: TerrainGrid) -> np.ndarray:
    """Bilinearly sample the *actual* GeoTIFF coordinates at lake grid vertices.

    ArcGIS ImageServer may expand an export bbox to square degree pixels. The
    GeoTIFF's tiepoint/pixel scale, not the requested bbox, are authoritative.
    """
    height, width = source.elevations_m.shape
    centre = (grid.size - 1) / 2
    east_m = (np.arange(grid.size) - centre) * grid.spacing_m
    lon_deg = grid.origin_lon_deg + east_m / (
        METRES_PER_DEGREE * math.cos(math.radians(grid.origin_lat_deg)))
    src_col = (lon_deg - source.west_edge_deg) / source.pixel_lon_deg - 0.5
    north_m = (centre - np.arange(grid.size)) * grid.spacing_m
    lat_deg = grid.origin_lat_deg + north_m / METRES_PER_DEGREE
    src_row = (source.north_edge_deg - lat_deg) / source.pixel_lat_deg - 0.5
    if (src_col.min() < -0.001 or src_col.max() > width - 1 + 0.001 or
            src_row.min() < -0.001 or src_row.max() > height - 1 + 0.001):
        raise ValueError("Source GeoTIFF does not cover every target terrain vertex")
    src_col = np.clip(src_col, 0, width - 1)
    src_row = np.clip(src_row, 0, height - 1)
    c0 = np.floor(src_col).astype(np.int32)
    c1 = np.minimum(c0 + 1, width - 1)
    wx = (src_col - c0).astype(np.float32)
    output = np.empty((grid.size, grid.size), dtype=np.float32)
    for target_row, source_row in enumerate(src_row):
        r0 = int(math.floor(source_row))
        r1 = min(r0 + 1, height - 1)
        wy = np.float32(source_row - r0)
        upper = source.elevations_m[r0, c0] * (1 - wx) + source.elevations_m[r0, c1] * wx
        lower = source.elevations_m[r1, c0] * (1 - wx) + source.elevations_m[r1, c1] * wx
        output[target_row] = upper * (1 - wy) + lower * wy
    return output


def encode_unreal_r16(elevations_m: np.ndarray, zero_elevation_m: float,
                      z_scale: float) -> np.ndarray:
    """Map elevations to Unreal Landscape uint16 height samples.

    At Z scale 100, code 32768 is 0 m, code 0 is -256 m, and each code is
    1/128 m. The Landscape actor's Z location stays at zero; zero_elevation_m
    is an absolute NAVD88 offset recorded in the manifest.
    """
    if not math.isfinite(zero_elevation_m) or not math.isfinite(z_scale) or z_scale <= 0:
        raise ValueError("Zero elevation and Z scale must be finite; Z scale positive")
    values = np.asarray(elevations_m, dtype=np.float64)
    if not np.isfinite(values).all():
        raise ValueError("Every source elevation must be finite")
    raw = 32768 + (values - zero_elevation_m) * 100 * 128 / z_scale
    if raw.min() < -1e-6 or raw.max() > 65535 + 1e-6:
        raise ValueError("Source elevation is outside Unreal R16 range")
    return np.rint(raw).astype("<u2")


def water_mask(grid: TerrainGrid, outer: list, islands: list) -> np.ndarray:
    mask = Image.new("L", (grid.size, grid.size), 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon([grid.local_to_pixel(x, y) for x, y in outer], fill=255)
    for ring in islands:
        draw.polygon([grid.local_to_pixel(x, y) for x, y in ring], fill=0)
    return np.asarray(mask) != 0


def estimate_water_level(elevations_m: np.ndarray, grid: TerrainGrid,
                         outer: list, islands: list,
                         reference_local_xy: tuple[float, float] | None = None,
                         radius_m: float | None = None,
                         shore_buffer_pixels: int = 0) -> dict:
    mask = water_mask(grid, outer, islands)
    if shore_buffer_pixels:
        if shore_buffer_pixels < 0:
            raise ValueError("Shore buffer must be nonnegative")
        mask = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).filter(
            ImageFilter.MinFilter(shore_buffer_pixels * 2 + 1))) != 0
    if reference_local_xy is not None and radius_m is not None:
        if radius_m <= 0:
            raise ValueError("Reference radius must be positive")
        px, py = grid.local_to_pixel(*reference_local_xy)
        rows, cols = np.ogrid[:grid.size, :grid.size]
        mask &= ((cols - px) * grid.spacing_m) ** 2 + ((rows - py) * grid.spacing_m) ** 2 <= radius_m ** 2
    samples = np.asarray(elevations_m)[mask]
    samples = samples[np.isfinite(samples)]
    if samples.size < 1:
        raise ValueError("No finite DEM samples inside lake water polygon")
    return {
        "median_m": float(np.median(samples)),
        "p05_m": float(np.percentile(samples, 5)),
        "p95_m": float(np.percentile(samples, 95)),
        "sample_count": int(samples.size),
        "method": "median of USGS hydroflattened DEM cells inside lake polygon, islands excluded",
        "reference_local_xy_m": reference_local_xy,
        "reference_radius_m": radius_m,
        "shore_buffer_m": shore_buffer_pixels * grid.spacing_m,
    }


def export_url(grid: TerrainGrid) -> str:
    params = {
        "bbox": ",".join(f"{n:.12f}" for n in grid.bbox_lonlat),
        "bboxSR": "4326", "imageSR": "4326",
        "size": f"{grid.size},{grid.size}",
        "pixelType": "F32", "format": "tiff", "f": "image",
        "interpolation": "RSP_BilinearInterpolation",
    }
    return SERVICE_URL + "/exportImage?" + urllib.parse.urlencode(params)


def fetch_dem(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "GIS-Sailing-Prototype/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=240) as response, partial.open("wb") as out:
            if "image/tiff" not in response.headers.get("Content-Type", ""):
                raise RuntimeError("USGS did not return a TIFF image")
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        partial.replace(destination)
    finally:
        if partial.exists():
            partial.unlink()


def read_dem(path: Path, size: int) -> GeoRaster:
    with Image.open(path) as image:
        if image.mode != "F" or image.size != (size, size):
            raise ValueError(f"Expected {size}x{size} float32 TIFF, got {image.mode} {image.size}")
        pixel_size = image.tag_v2.get(33550)
        tiepoint = image.tag_v2.get(33922)
        geo_keys = image.tag_v2.get(34735)
        if (not pixel_size or not tiepoint or not geo_keys or
                (2048, 0, 1, 4326) not in [tuple(geo_keys[n:n + 4]) for n in range(4, len(geo_keys), 4)]):
            raise ValueError("DEM must have a WGS84 EPSG:4326 GeoTIFF header")
        if pixel_size[0] <= 0 or pixel_size[1] <= 0:
            raise ValueError("DEM GeoTIFF pixel size must be positive")
        elevations = np.asarray(image, dtype=np.float32)
    if not np.isfinite(elevations).all() or elevations.min() < -1000 or elevations.max() > 9000:
        raise ValueError("DEM has missing or implausible elevation cells; no values were fabricated")
    return GeoRaster(elevations, float(tiepoint[3]), float(tiepoint[4]),
                     float(pixel_size[0]), float(pixel_size[1]))


def choose_z_scale(elevations_m: np.ndarray, zero_m: float) -> float:
    most_extreme_m = max(abs(float(elevations_m.min()) - zero_m),
                         abs(float(elevations_m.max()) - zero_m))
    return float(max(100, math.ceil((most_extreme_m / 255.5) * 100 / 10) * 10))


def save_qa(path: Path, elevations_m: np.ndarray, mask: np.ndarray) -> None:
    # A shaded, colour-coded diagnostic preview, not a terrain texture.
    lo, hi = np.percentile(elevations_m, [2, 98])
    tone = np.clip((elevations_m - lo) / max(hi - lo, 1), 0, 1)
    gy, gx = np.gradient(elevations_m.astype(np.float32))
    shade = np.clip(0.73 + (gx - gy) * 0.11, 0.35, 1.15)
    rgb = np.stack((90 + tone * 91, 112 + tone * 94, 77 + tone * 78), axis=-1) * shade[..., None]
    rgb[mask] = (46, 112, 163)
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
    img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    img.save(path)


def build(lake_path: Path, output_dir: Path, size: int, spacing_m: float,
          existing_tiff: Path | None = None) -> dict:
    lake = json.loads(lake_path.read_text(encoding="utf-8"))
    grid = TerrainGrid.for_lake(lake, size=size, spacing_m=spacing_m)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"greenwood_{size}_s{spacing_m:g}m"
    tiff_path = output_dir / f"{stem}_3dep_f32.tif"
    if existing_tiff:
        tiff_path = existing_tiff
    elif not tiff_path.exists():
        fetch_dem(export_url(grid), tiff_path)
    source_raster = read_dem(tiff_path, size)
    elevations = resample_to_local_grid(source_raster, grid)
    lake_mask = water_mask(grid, lake["water_polygon"], lake.get("islands", []))
    water = estimate_water_level(
        elevations, grid, lake["water_polygon"], lake.get("islands", []),
        reference_local_xy=(lake["spawn"]["x_m"], lake["spawn"]["y_m"]),
        radius_m=1500, shore_buffer_pixels=3,
    )
    zero_m = water["median_m"]
    z_scale = choose_z_scale(elevations, zero_m)
    encoded = encode_unreal_r16(elevations, zero_m, z_scale)
    r16_path = output_dir / f"{stem}.r16"
    r16_path.write_bytes(encoded.tobytes(order="C"))
    qa_path = output_dir / f"{stem}_qa.png"
    save_qa(qa_path, elevations, lake_mask)
    manifest = {
        "lake_id": lake["id"],
        "width": size,
        "height": size,
        "x_min_m": grid.local_bounds_m[0],
        "y_min_m": grid.local_bounds_m[1],
        "x_max_m": grid.local_bounds_m[2],
        "y_max_m": grid.local_bounds_m[3],
        "sample_spacing_m": spacing_m,
        "row_0_is_north": True,
        "water_elevation_m": zero_m,
        "water_plane_world_z_m": 0.0,
        "r16_file": r16_path.name,
        "r16_zero_code": 32768,
        "r16_world_cm_per_code": z_scale / 128,
        "source": {
            "name": "USGS 3DEP Bare Earth DEM Dynamic ImageServer",
            "service_url": SERVICE_URL,
            "request_url": export_url(grid),
            "retrieved_utc": datetime.fromtimestamp(
                tiff_path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds"),
            "raw_tiff": tiff_path.name,
            "raw_tiff_sha256": hashlib.sha256(tiff_path.read_bytes()).hexdigest(),
            "actual_tiff_extent_lonlat": source_raster.extent_lonlat,
            "actual_tiff_pixel_size_degrees": [source_raster.pixel_lon_deg,
                                                 source_raster.pixel_lat_deg],
            "alignment": "GeoTIFF tiepoint and pixel scale used to resample each Landscape vertex",
            "vertical_datum": "NAVD88 metres is standard for CONUS 3DEP; inspect source raster metadata for exact source lineage",
            "license": "USGS 3DEP: public domain, no use restrictions; credit USGS",
        },
        "grid": {
            "width_vertices": size, "height_vertices": size,
            "vertex_spacing_m": spacing_m,
            "local_origin_lon_deg": grid.origin_lon_deg,
            "local_origin_lat_deg": grid.origin_lat_deg,
            "local_vertex_bounds_m": grid.local_bounds_m,
            "request_bbox_lonlat_pixel_edges": grid.bbox_lonlat,
            "row_zero_is_north": True,
            "column_zero_is_west": True,
            "center_vertex_row_col": [(size - 1) // 2, (size - 1) // 2],
            "coordinate_system": "same local equirectangular east/north metres as greenwood_usgs.json",
        },
        "elevation": {
            "min_m": float(elevations.min()),
            "max_m": float(elevations.max()),
            "water_level_estimate": water,
            "note": "DEM is hydroflattened terrain, not bathymetry or a current lake gauge reading",
        },
        "unreal_landscape_import": {
            "heightmap_file": r16_path.name,
            "format": "R16 unsigned little-endian, row-major",
            "x_scale_cm": spacing_m * 100,
            "y_scale_cm": spacing_m * 100,
            "z_scale": z_scale,
            "actor_location_z_cm": 0,
            "zero_elevation_m_navd88": zero_m,
            "height_formula": "world_z_cm = (R16 - 32768) * z_scale / 128",
            "water_plane_world_z_cm": 0,
            "orientation_note": "Grid columns increase east and rows increase south; check Unreal Flip Y Axis so north is +world Y",
        },
        "qa_image": qa_path.name,
    }
    manifest_path = output_dir / f"{stem}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lake", type=Path, default=Path(__file__).resolve().parent.parent / "greenwood_usgs.json")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--size", type=int, choices=(2017, 4033), default=2017)
    parser.add_argument("--spacing-m", type=float, default=16)
    parser.add_argument("--existing-tiff", type=Path, help="Use a previously fetched float32 GeoTIFF")
    args = parser.parse_args()
    try:
        result = build(args.lake, args.output_dir, args.size, args.spacing_m, args.existing_tiff)
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
        print(f"Terrain build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"min_m": result["elevation"]["min_m"],
                      "max_m": result["elevation"]["max_m"],
                      "water_m": result["elevation"]["water_level_estimate"]["median_m"],
                      "r16": result["unreal_landscape_import"]["heightmap_file"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
