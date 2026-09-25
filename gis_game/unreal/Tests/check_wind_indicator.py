"""Check the Unreal wind display's source convention without Unreal Editor.

Extract the two directional terms from the C++ helper so these cases exercise
the actual source expressions. This does not replace an Unreal build/PIE run.
"""

import math
import pathlib
import re
from types import SimpleNamespace


ROOT = pathlib.Path(__file__).resolve().parents[1]
HEADER = (ROOT / "Source/GISGame/Public/GISWindDisplay.h").read_text()
HUD = (ROOT / "Source/GISGame/Private/GISHUD.cpp").read_text()


def source_expression(name: str) -> str:
    match = re.search(rf"const double {name} = (.*?);", HEADER)
    assert match, f"missing {name} in GISWindDisplay.h"
    return match.group(1)


def indicator(air_x: float, air_y: float) -> tuple[float, float, float]:
    air = SimpleNamespace(x=air_x, y=air_y)
    speed = math.hypot(air_x, air_y)
    assert speed > 0.001
    scope = {"AirVelocityBoat": air, "Speed": speed}
    from_bow = eval(source_expression("FromBow"), {"__builtins__": {}}, scope)
    from_starboard = eval(
        source_expression("FromStarboard"), {"__builtins__": {}}, scope
    )
    assert "std::atan2(FromStarboard, FromBow)" in HEADER
    assert re.search(r"FromStarboard,\s*-FromBow,\s*Speed", HEADER)
    return (math.degrees(math.atan2(from_starboard, from_bow)),
            from_starboard, -from_bow)


def close(actual: float, expected: float) -> None:
    assert math.isclose(actual, expected, abs_tol=1e-9), (actual, expected)


for air, expected in (
    ((-5, 0), (0, 0, -1)),       # headwind, arrow at bow
    ((0, 5), (90, 1, 0)),        # wind arrives from starboard
    ((0, -5), (-90, -1, 0)),     # wind arrives from port
    ((5, 0), (180, 0, 1)),       # wind arrives from astern
):
    actual = indicator(*air)
    for observed, wanted in zip(actual, expected):
        close(observed, wanted)

# Same world wind (air moving south), different headings: the displayed arrow
# rotates relative to the fixed bow as the boat turns north -> east -> west.
def wind_in_boat(heading: float) -> tuple[float, float]:
    east, north = 0.0, -5.0
    return (math.cos(heading) * east + math.sin(heading) * north,
            -math.sin(heading) * east + math.cos(heading) * north)


close(indicator(*wind_in_boat(math.pi / 2))[0], 0)
close(indicator(*wind_in_boat(0))[0], -90)
close(indicator(*wind_in_boat(math.pi))[0], 90)

assert "Step.apparent_wind_boat" in HUD
assert "make_apparent_wind_display(AirVelocityBoat)" in HUD
assert "Wind.ScreenX" in HUD and "Wind.ScreenY" in HUD
assert 'TEXT("APPARENT WIND FROM")' in HUD
print("GIS Unreal boat-relative wind indicator checks passed")
