"""Cross-check exported NAIP coverage against the terrain's local grid."""

import json
import math
import unittest
from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
TERRAIN = json.loads((HERE.parent / "terrain" / "greenwood_2017_s16m_manifest.json").read_text())
NAIP = json.loads((HERE / "greenwood_naip_manifest.json").read_text())


class NaipAlignmentTests(unittest.TestCase):
    def test_image_coverage_matches_terrain_vertices(self):
        bounds = NAIP["output_edge_bounds_local_m"]
        self.assertEqual(bounds, [TERRAIN["x_min_m"], TERRAIN["y_min_m"],
                                  TERRAIN["x_max_m"], TERRAIN["y_max_m"]])
        with Image.open(HERE / "greenwood_naip_rgb_4096.png") as image:
            self.assertEqual(image.size, (4096, 4096))
            self.assertEqual(image.mode, "RGB")
        self.assertAlmostEqual(NAIP["output_metres_per_pixel"], 7.875)

    def test_all_source_tiles_cover_their_requested_quadrants(self):
        tiles = NAIP["source_tiles"]
        self.assertEqual(len(tiles), 16)
        self.assertEqual({(tile["row"], tile["column"]) for tile in tiles},
                         {(r, c) for r in range(4) for c in range(4)})
        lon0, lat0 = -82.0408735, 34.265721
        m_per_degree = 111319.49
        for tile in tiles:
            row, column = tile["row"], tile["column"]
            metres = 32256 / 4
            west_m = -16128 + column * metres
            east_m = west_m + metres
            north_m = 16128 - row * metres
            south_m = north_m - metres
            expected = [
                lon0 + west_m / (m_per_degree * math.cos(math.radians(lat0))),
                lat0 + south_m / m_per_degree,
                lon0 + east_m / (m_per_degree * math.cos(math.radians(lat0))),
                lat0 + north_m / m_per_degree,
            ]
            for actual, expect in zip(tile["requested_bbox_lonlat"], expected):
                self.assertAlmostEqual(actual, expect, places=9)
            left, bottom, right, top = tile["returned_bbox_lonlat"]
            self.assertLessEqual(left, expected[0])
            self.assertLessEqual(bottom, expected[1])
            self.assertGreaterEqual(right, expected[2])
            self.assertGreaterEqual(top, expected[3])
            crop_left, crop_top, crop_right, crop_bottom = tile["crop_pixel_edges_in_source"]
            self.assertTrue(0 <= crop_left < crop_right <= 1024)
            self.assertTrue(0 <= crop_top < crop_bottom <= 847)


if __name__ == "__main__":
    unittest.main()
