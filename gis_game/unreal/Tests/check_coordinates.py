"""Static coordinate-contract check when an Unreal/Windows C++ toolchain is absent.

This evaluates the simple return expressions in GISCoordinates.h directly;
it does not replace compiling or running the C++/Unreal project.
"""

import math
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = (ROOT / "Source/GISGame/Public/GISCoordinates.h").read_text()
PAWN = (ROOT / "Source/GISGame/Private/GISBoatPawn.cpp").read_text()
GAME_MODE = (ROOT / "Source/GISGame/Private/GISGameMode.cpp").read_text()


def result(function_name: str, **arguments: float) -> float:
    match = re.search(
        rf"inline double {function_name}\([^)]*\)\s*\{{(.*?)\}}",
        HEADER,
        re.S,
    )
    assert match, function_name
    expression = re.search(r"return\s+([^;]+);", match.group(1))
    assert expression, function_name
    source = expression.group(1).replace("std::atan2", "math.atan2")
    scope = {"math": math, "Pi": math.pi, "CentimetresPerMetre": 100.0}
    return eval(source, {"__builtins__": {}}, scope | arguments)


def close(actual: float, expected: float) -> None:
    assert math.isclose(actual, expected, abs_tol=1e-9), (actual, expected)


close(result("east_metres_to_ue_x_cm", EastMetres=2.5), 250.0)
close(result("north_metres_to_ue_y_cm", NorthMetres=2.5), -250.0)
close(result("core_heading_rad_to_ue_yaw_deg", HeadingRadians=math.pi / 2), -90.0)
close(result("compass_heading_deg_to_ue_yaw_deg", ClockwiseFromNorth=0.0), -90.0)
close(result("compass_heading_deg_to_ue_yaw_deg", ClockwiseFromNorth=90.0), 0.0)
close(result("east_north_segment_to_ue_yaw_deg", EastDelta=0.0, NorthDelta=1.0), -90.0)
close(result("core_heel_rad_to_ue_roll_deg", StarboardDownRadians=math.pi / 6), 30.0)
close(result("core_port_angle_rad_to_ue_bone_yaw_deg", PortRadians=math.pi / 6), 30.0)

# With Epic's positive +Yaw toward +Y-right, the mirrored north-facing bow
# points -Y. Positive +Roll tips +Y starboard below the deck plane. Positive
# yaw of an aft-pointing spar sends it to -Y port.
assert math.sin(math.radians(-90.0)) < 0.0
assert -math.sin(math.radians(30.0)) < 0.0
assert -math.sin(math.radians(30.0)) < 0.0

# The tiller handle points forward (+X) while the rudder blade trails aft
# (-X). Dragging the mouse right must move the handle toward +Y starboard;
# the shared stock then sends the blade toward port and the bow turns port.
mouse_helm = re.search(
    r"void AGISBoatPawn::OnMouseHelmAxis\(float Value\)\s*\{(.*?)\n\}",
    PAWN,
    re.S,
)
assert mouse_helm, "mouse helm handler missing"
mouse_increment = re.search(
    r"MouseHelm\s*=\s*FMath::Clamp\(MouseHelm\s*([+-])\s*Value\s*\*\s*([\d.]+)f",
    mouse_helm.group(1),
)
assert mouse_increment, "mouse helm mapping missing"
mouse_sign = 1 if mouse_increment.group(1) == "+" else -1
mouse_sensitivity = float(mouse_increment.group(2))
assert mouse_sign * mouse_sensitivity > 0, "right drag must push the tiller handle starboard"
assert mouse_sign * -mouse_sensitivity < 0, "left drag must push the tiller handle port"
assert "bMouseHelmHeld ? MouseHelm : HelmAxis" in PAWN
assert "core_port_angle_rad_to_ue_bone_yaw_deg(BoatState.rudder_angle)" in PAWN
assert math.sin(mouse_sign * mouse_sensitivity) > 0, "forward tiller must swing starboard"
assert -math.sin(mouse_sign * mouse_sensitivity) < 0, "aft rudder must swing port"

for required in (
    "north_metres_to_ue_y_cm(BoatState.y)",
    "core_heading_rad_to_ue_yaw_deg(BoatState.heading)",
    "core_heel_rad_to_ue_roll_deg(BoatState.heel)",
    "core_port_angle_rad_to_ue_bone_yaw_deg(BoatState.rudder_angle)",
    "core_port_angle_rad_to_ue_bone_yaw_deg(BoatState.boom_angle)",
):
    assert required in PAWN, required

for required in (
    "north_metres_to_ue_y_cm(LakeMap.SpawnMetres.Y)",
    "north_metres_to_ue_y_cm(Midpoint.Y)",
    "north_metres_to_ue_y_cm(Y)",
    "east_north_segment_to_ue_yaw_deg(Difference.X, Difference.Y)",
):
    assert required in GAME_MODE, required

print("GIS Unreal static coordinate checks passed")
