"""Checks for geographic alignment and Unreal Landscape height encoding."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_terrain import (
    GeoRaster, TerrainGrid, encode_unreal_r16, estimate_water_level,
    resample_to_local_grid,
)


class TerrainGridTests(unittest.TestCase):
    def test_grid_covers_lake_and_keeps_map_origin_at_center_vertex(self):
        lake = {
            "origin_lon_deg": -82.0,
            "origin_lat_deg": 34.0,
            "bounds_m": {"min_x": -16000, "max_x": 16000,
                         "min_y": -12000, "max_y": 12000},
        }
        grid = TerrainGrid.for_lake(lake, size=2017, spacing_m=16)

        self.assertEqual(grid.local_bounds_m, (-16128, -16128, 16128, 16128))
        self.assertEqual(grid.pixel_to_local(1008, 1008), (0, 0))
        self.assertEqual(grid.pixel_to_local(0, 0), (-16128, 16128))
        self.assertEqual(grid.pixel_to_local(2016, 2016), (16128, -16128))
        west, south, east, north = grid.bbox_lonlat
        self.assertLess(west, -82.0)
        self.assertGreater(east, -82.0)
        self.assertLess(south, 34.0)
        self.assertGreater(north, 34.0)
        self.assertAlmostEqual(grid.lonlat_to_local(-82.0, 34.0)[0], 0, places=6)
        self.assertAlmostEqual(grid.lonlat_to_local(-82.0, 34.0)[1], 0, places=6)

    def test_geotiff_cells_are_resampled_using_header_coordinates(self):
        # Values follow z = 100 + 10*longitude_millideg + 20*latitude_millideg.
        source = GeoRaster(
            np.array([[110, 120, 130], [90, 100, 110], [70, 80, 90]],
                     dtype=np.float32),
            west_edge_deg=-0.0015, north_edge_deg=0.0015,
            pixel_lon_deg=0.001, pixel_lat_deg=0.001,
        )
        target = TerrainGrid(0.0, 0.0, 3, 55.659745)

        actual = resample_to_local_grid(source, target)

        np.testing.assert_allclose(
            actual,
            [[105, 110, 115], [95, 100, 105], [85, 90, 95]],
            rtol=0, atol=1e-5,
        )


class UnrealHeightEncodingTests(unittest.TestCase):
    def test_r16_centers_known_elevations_without_losing_sign(self):
        metres = np.array([[-256, -1, 0, 1, 255.9921875]], dtype=np.float32)
        encoded = encode_unreal_r16(metres, zero_elevation_m=0, z_scale=100)

        self.assertEqual(encoded.dtype, np.dtype("uint16"))
        self.assertEqual(encoded.tolist(), [[0, 32640, 32768, 32896, 65535]])

    def test_r16_rejects_nonfinite_and_out_of_range_heights(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            encode_unreal_r16(np.array([[np.nan]], dtype=np.float32), 0, 100)
        with self.assertRaisesRegex(ValueError, "range"):
            encode_unreal_r16(np.array([[256]], dtype=np.float32), 0, 100)


class WaterLevelTests(unittest.TestCase):
    def test_estimate_uses_water_polygon_and_excludes_island_and_land(self):
        heights = np.full((9, 9), 180.0, dtype=np.float32)
        heights[1:8, 1:8] = 133.0
        heights[4, 4] = 220.0
        grid = TerrainGrid(-82.0, 34.0, 9, 1)
        water = [[-3, -3], [3, -3], [3, 3], [-3, 3]]
        island = [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]

        estimate = estimate_water_level(heights, grid, water, [island])

        self.assertEqual(estimate["median_m"], 133.0)
        self.assertGreater(estimate["sample_count"], 0)
        self.assertLess(estimate["sample_count"], 81)

    def test_reference_area_ignores_higher_upstream_water(self):
        heights = np.full((9, 9), 160.0, dtype=np.float32)
        heights[2:7, 2:7] = 133.0
        heights[4, 4] = 220.0
        grid = TerrainGrid(-82.0, 34.0, 9, 1)
        water = [[-4, -4], [4, -4], [4, 4], [-4, 4]]
        island = [[-0.5, -0.5], [0.5, -0.5], [0.5, 0.5], [-0.5, 0.5]]

        estimate = estimate_water_level(
            heights, grid, water, [island], reference_local_xy=(0, 0),
            radius_m=2.5, shore_buffer_pixels=0,
        )

        self.assertEqual(estimate["median_m"], 133.0)


if __name__ == "__main__":
    unittest.main()
