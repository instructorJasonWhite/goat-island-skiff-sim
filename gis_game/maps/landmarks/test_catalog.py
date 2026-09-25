import json
import math
import unittest
from pathlib import Path

import build_catalog as landmarks


class LandmarkCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = landmarks.build_catalog()
        cls.lake = json.loads(landmarks.MAP_FILE.read_text(encoding="utf-8"))
        cls.contains = staticmethod(landmarks.water_mask(cls.lake))

    def test_generated_catalog_and_geojson_match_source_extracts(self):
        saved = json.loads((landmarks.HERE / "greenwood_landmarks.json").read_text(encoding="utf-8"))
        geojson = json.loads((landmarks.HERE / "greenwood_landmarks.geojson").read_text(encoding="utf-8"))
        self.assertEqual(saved, self.catalog)
        self.assertEqual(geojson, landmarks.as_geojson(self.catalog))
        self.assertEqual(len(saved["features"]), 19)

    def test_projection_is_compatible_with_lake_origin(self):
        for item in self.catalog["features"]:
            east, north = landmarks.project(item["longitude"], item["latitude"])
            self.assertAlmostEqual(east, item["east_m"], delta=0.01)
            self.assertAlmostEqual(north, item["north_m"], delta=0.01)
            lon, lat = landmarks.unproject(item["east_m"], item["north_m"])
            self.assertAlmostEqual(lon, item["longitude"], delta=1e-7)
            self.assertAlmostEqual(lat, item["latitude"], delta=1e-7)

    def test_every_feature_has_provenance_and_is_within_lake_map(self):
        features = self.catalog["features"]
        source_ids = {source["id"] for source in self.catalog["sources"]}
        self.assertEqual(len({item["id"] for item in features}), len(features))
        bounds = self.lake["bounds_m"]
        for item in features:
            with self.subTest(item=item["id"]):
                self.assertIn(item["source_id"], source_ids)
                self.assertTrue(item["source_record"])
                self.assertTrue(item["source_url"].startswith("https://"))
                self.assertIn(item["confidence"], {"high", "medium"})
                self.assertGreaterEqual(item["east_m"], bounds["min_x"])
                self.assertLessEqual(item["east_m"], bounds["max_x"])
                self.assertGreaterEqual(item["north_m"], bounds["min_y"])
                self.assertLessEqual(item["north_m"], bounds["max_y"])

    def test_bridges_and_rail_crossings_touch_mapped_water(self):
        for item in self.catalog["features"]:
            if item["type"] not in {"major-road-bridge", "road-bridge", "rail-crossing"}:
                continue
            with self.subTest(item=item["id"]):
                self.assertTrue(self.contains((item["east_m"], item["north_m"])))
                if item["type"] == "rail-crossing":
                    self.assertGreater(item["span_length_m"], 20)
                    self.assertEqual(len(item["span_endpoints_m"]), 2)
                else:
                    self.assertGreaterEqual(item["span_length_m"], 10)
                    self.assertEqual(len(item["span_endpoints_m"]), 2)
                    self.assertEqual(item["alignment_source_url"], landmarks.SOURCE_URLS["usgs_roads"])

    def test_dam_and_access_points_are_on_lake_shore(self):
        outer = self.lake["water_polygon"]

        def point_to_segment(point, a, b):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length_sq = dx * dx + dy * dy
            fraction = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_sq)) if length_sq else 0
            return math.dist(point, (a[0] + fraction * dx, a[1] + fraction * dy))

        for item in self.catalog["features"]:
            if item["type"] not in {"dam-component", "public-ramp"}:
                continue
            point = item["east_m"], item["north_m"]
            nearest = min(point_to_segment(point, a, b) for a, b in zip(outer, outer[1:] + outer[:1]))
            with self.subTest(item=item["id"]):
                self.assertLessEqual(nearest, 100)

    def test_overview_exists_at_reviewable_resolution(self):
        from PIL import Image
        with Image.open(landmarks.HERE / "greenwood_landmarks_overview.png") as image:
            self.assertGreaterEqual(image.width, 1500)
            self.assertGreaterEqual(image.height, 1000)


if __name__ == "__main__":
    unittest.main()
