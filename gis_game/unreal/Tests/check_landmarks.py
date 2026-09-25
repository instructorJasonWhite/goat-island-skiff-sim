"""Sanity checks for staged Greenwood landmark data and Unreal scene wiring.

This is a source/data check; compile and Play-in-Editor remain separate gates.
"""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT.parent / "maps" / "landmarks"
STAGED = ROOT / "Content" / "Data" / "greenwood_landmarks.json"
SOURCE = MAPS / "greenwood_landmarks.json"
SCENE_CPP = ROOT / "Source" / "GISGame" / "Private" / "GISLandmarkScene.cpp"
SCENE_H = ROOT / "Source" / "GISGame" / "Public" / "GISLandmarkScene.h"
MODE = ROOT / "Source" / "GISGame" / "Private" / "GISGameMode.cpp"

assert STAGED.read_bytes() == SOURCE.read_bytes(), "Unreal staged landmarks are stale"
catalog = json.loads(STAGED.read_text(encoding="utf-8"))
assert catalog["map_id"] == "lake_greenwood_south_carolina"
assert catalog["navigational_use"] is False
features = catalog["features"]
assert len(features) == 19
assert len({feature["id"] for feature in features}) == 19
assert sum(feature["type"].endswith("road-bridge") for feature in features) == 9
assert sum(feature["type"] == "rail-crossing" for feature in features) == 3
assert sum(feature["type"] == "dam-component" for feature in features) == 3
assert sum(feature["type"] == "public-ramp" for feature in features) == 4
for feature in features:
    assert -20000 < feature["east_m"] < 20000
    assert -20000 < feature["north_m"] < 20000
    assert feature["source_url"].startswith("https://")
    assert feature["license"]
    if feature["type"] in {"major-road-bridge", "road-bridge", "rail-crossing"}:
        assert feature["span_length_m"] >= 10
        assert len(feature["span_endpoints_m"]) == 2

cpp = SCENE_CPP.read_text(encoding="utf-8")
header = SCENE_H.read_text(encoding="utf-8")
game_mode = MODE.read_text(encoding="utf-8")
assert "class GISGAME_API AGISLandmarkScene" in header
assert "TArray<FGISLandmarkMapMarker> MapMarkers" in header
assert "gis_unreal::east_metres_to_ue_x_cm" in cpp
assert "gis_unreal::north_metres_to_ue_y_cm" in cpp
assert "ECollisionEnabled::NoCollision" in cpp
assert "AGISLandmarkScene" in game_mode
assert "greenwood_landmarks.json" in game_mode

print("Landmark data and Unreal scene wiring: 19 sourced features, staged data matches.")
