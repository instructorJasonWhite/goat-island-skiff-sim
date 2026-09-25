#pragma once

#include "SailingSim.h"

#include <cmath>

namespace gis_unreal {

// Screen X increases toward starboard and screen Y increases toward the stern.
// The solver stores the direction air MOVES, so negate it to show where the
// apparent wind COMES FROM. The bow stays at the top of this boat-fixed dial.
struct FBoatRelativeWindDisplay {
    double BearingDegreesStarboard = 0.0;
    double ScreenX = 0.0;
    double ScreenY = 0.0;
    double SpeedMetresPerSecond = 0.0;
    bool bValid = false;
};

inline FBoatRelativeWindDisplay make_apparent_wind_display(gis::Vec2 AirVelocityBoat)
{
    const double Speed = std::hypot(AirVelocityBoat.x, AirVelocityBoat.y);
    if (Speed < 0.001)
    {
        return {};
    }

    const double FromBow = -AirVelocityBoat.x / Speed;
    const double FromStarboard = AirVelocityBoat.y / Speed;
    constexpr double RadiansToDegrees = 180.0 / 3.14159265358979323846;
    return {
        std::atan2(FromStarboard, FromBow) * RadiansToDegrees,
        FromStarboard,
        -FromBow,
        Speed,
        true
    };
}

} // namespace gis_unreal
