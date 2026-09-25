import json
import unittest
from pathlib import Path

from validate_maps import validate_map


ROOT = Path(__file__).resolve().parent


class MapValidationTests(unittest.TestCase):
    def test_greenwood_training_reach_is_valid(self):
        data = json.loads((ROOT / "greenwood_prototype.json").read_text())
        self.assertEqual(validate_map(data), [])

    def test_spawn_on_land_is_rejected(self):
        data = json.loads((ROOT / "greenwood_prototype.json").read_text())
        data["spawn"] = {"x_m": 5000, "y_m": 0, "heading_deg": 0}
        self.assertTrue(any("spawn" in issue for issue in validate_map(data)))

    def test_island_under_spawn_is_rejected(self):
        data = json.loads((ROOT / "greenwood_prototype.json").read_text())
        data["islands"] = [[[-500, -100], [-350, -100], [-350, 50], [-500, 50]]]
        self.assertTrue(any("spawn" in issue for issue in validate_map(data)))

    def test_degenerate_water_polygon_is_rejected(self):
        data = json.loads((ROOT / "greenwood_prototype.json").read_text())
        data["water_polygon"] = [[0, 0], [1, 0], [2, 0]]
        self.assertTrue(any("water_polygon" in issue for issue in validate_map(data)))


if __name__ == "__main__":
    unittest.main()
