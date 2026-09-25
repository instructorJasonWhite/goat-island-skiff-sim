"""Check that the runtime terrain bytes and Greenwood map share one coordinate frame."""

import hashlib
import json
import struct
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
MAPS = PROJECT.parent / "maps"
SOURCE = MAPS / "terrain"
STAGED = PROJECT / "Content" / "Data"
NAME = "greenwood_2017_s16m"


class TerrainContractTests(unittest.TestCase):
    def test_staged_terrain_matches_surveyed_source(self):
        source_manifest = json.loads((SOURCE / f"{NAME}_manifest.json").read_text())
        stage_manifest = json.loads((STAGED / f"{NAME}_manifest.json").read_text())
        self.assertEqual(stage_manifest, source_manifest)
        source_r16 = (SOURCE / f"{NAME}.r16").read_bytes()
        stage_r16 = (STAGED / f"{NAME}.r16").read_bytes()
        self.assertEqual(hashlib.sha256(stage_r16).digest(), hashlib.sha256(source_r16).digest())
        self.assertEqual(len(stage_r16), 2 * stage_manifest["width"] * stage_manifest["height"])

        self.assertTrue(stage_manifest["row_0_is_north"])
        self.assertEqual(stage_manifest["x_min_m"], -stage_manifest["x_max_m"])
        self.assertEqual(stage_manifest["y_min_m"], -stage_manifest["y_max_m"])
        self.assertEqual((stage_manifest["width"] - 1) * stage_manifest["sample_spacing_m"],
                         stage_manifest["x_max_m"] - stage_manifest["x_min_m"])
        center = stage_manifest["height"] // 2 * stage_manifest["width"] + stage_manifest["width"] // 2
        height_code = struct.unpack_from("<H", stage_r16, center * 2)[0]
        self.assertAlmostEqual((height_code - stage_manifest["r16_zero_code"])
                               * stage_manifest["r16_world_cm_per_code"], 0, delta=25)


if __name__ == "__main__":
    unittest.main()
