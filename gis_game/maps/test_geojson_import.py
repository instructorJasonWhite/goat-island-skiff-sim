import unittest

from import_geojson import convert_geojson
from validate_maps import validate_map


class GeoJsonImportTests(unittest.TestCase):
    def test_polygon_with_hole_becomes_valid_lake_and_island(self):
        source = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [
                [[-82.1, 34.1], [-82.09, 34.1], [-82.09, 34.11], [-82.1, 34.11], [-82.1, 34.1]],
                [[-82.097, 34.104], [-82.095, 34.104], [-82.095, 34.106], [-82.097, 34.106], [-82.097, 34.104]],
            ]},
        }
        result = convert_geojson(source, "Test Lake", "local test")
        self.assertEqual(len(result["islands"]), 1)
        self.assertGreater(result["bounds_m"]["max_x"], 400)
        self.assertTrue(result["approximate"])
        self.assertEqual(validate_map(result), [])

    def test_largest_part_of_multipolygon_is_selected(self):
        source = {"type": "MultiPolygon", "coordinates": [
            [[[-82.1, 34.1], [-82.099, 34.1], [-82.099, 34.101], [-82.1, 34.101], [-82.1, 34.1]]],
            [[[-82.11, 34.1], [-82.10, 34.1], [-82.10, 34.11], [-82.11, 34.11], [-82.11, 34.1]]],
        ]}
        result = convert_geojson(source, "Test Lake", "local test")
        self.assertGreater(result["bounds_m"]["max_x"] - result["bounds_m"]["min_x"], 500)
        self.assertEqual(validate_map(result), [])

    def test_malformed_coordinate_has_readable_error(self):
        source = {"type": "Polygon", "coordinates": [[[-82.1, 34.1], ["west", 34.1], [-82.1, 34.2]]]}
        with self.assertRaisesRegex(ValueError, "invalid polygon ring"):
            convert_geojson(source, "Test Lake", "local test")


if __name__ == "__main__":
    unittest.main()
