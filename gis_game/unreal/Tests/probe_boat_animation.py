"""Read-only probe of the imported UE boat animation conventions."""

import json
from pathlib import Path
import unreal


paths = {
    "mesh": "/Game/Boat/SK_Goat_Island_Skiff",
    "tiller": "/Game/Boat/A_Goat_Island_Skiff_TillerPortStarboard",
    "tack": "/Game/Boat/A_Goat_Island_Skiff_TackPortToStarboard",
    "hoist": "/Game/Boat/A_Goat_Island_Skiff_SailRaiseLower",
    "blade": "/Game/Boat/A_Goat_Island_Skiff_RudderBladeLift",
    "board": "/Game/Boat/A_Goat_Island_Skiff_CenterboardLift",
}
assets = {name: unreal.EditorAssetLibrary.load_asset(path) for name, path in paths.items()}
report = {
    "assets_loaded": {name: asset is not None for name, asset in assets.items()},
    "animation_library_methods": [name for name in dir(unreal.AnimationLibrary)
                                  if "bone" in name.lower() or "pose" in name.lower()],
    "get_bone_pose_for_time_doc": unreal.AnimationLibrary.get_bone_pose_for_time.__doc__,
}
for clip_name, bone_name, fractions in (
    ("tiller", "RudderYaw", (0.0, 1.0 / 3.0, 2.0 / 3.0)),
    ("tack", "SailSwing", (0.0, 0.5, 1.0)),
    ("hoist", "SailHoist", (0.0, 0.5, 1.0)),
    ("blade", "RudderBladeSlide", (0.0, 1.0)),
    ("board", "CenterboardSlide", (0.0, 1.0)),
):
    clip = assets[clip_name]
    report[clip_name + "_bone_poses"] = {
        str(fraction): str(unreal.AnimationLibrary.get_bone_pose_for_time(
            clip, bone_name, fraction * clip.get_play_length(), False))
        for fraction in fractions
    }
target = Path(unreal.Paths.project_saved_dir()) / "probe_boat_animation.json"
target.write_text(json.dumps(report, indent=2), encoding="utf-8")
unreal.log("GIS_RIG_PROBE " + json.dumps(report))
