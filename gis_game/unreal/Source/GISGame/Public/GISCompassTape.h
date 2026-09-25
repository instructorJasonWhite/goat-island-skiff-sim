#pragma once

#include <cmath>
#include <vector>

namespace gis_unreal {

// Compass bearings increase clockwise. OffsetPixels is measured from the
// stationary lubber line; a higher bearing appears to its right.
struct FCompassTapeTick {
    double BearingDegrees = 0.0;
    double OffsetPixels = 0.0;
    bool bMajor = false;
};

struct FCompassTape {
    double LubberBearingDegrees = 0.0;
    std::vector<FCompassTapeTick> Ticks;
};

inline double normalize_compass_degrees(double Degrees)
{
    if (!std::isfinite(Degrees))
    {
        return 0.0;
    }
    double Wrapped = std::fmod(Degrees, 360.0);
    if (Wrapped < 0.0)
    {
        Wrapped += 360.0;
    }
    return Wrapped;
}

// Generate 10-degree ticks for a compass tape whose screen center is zero.
// The caller adds the HUD's center X to OffsetPixels and draws the fixed
// lubber line at that X. Unwrapped tick coordinates keep 359 -> 0 smooth.
inline FCompassTape make_compass_tape(
    double HeadingDegrees, double PixelsPerDegree, double HalfWidthPixels)
{
    FCompassTape Tape;
    Tape.LubberBearingDegrees = normalize_compass_degrees(HeadingDegrees);
    if (!std::isfinite(PixelsPerDegree) || !std::isfinite(HalfWidthPixels)
        || PixelsPerDegree <= 0.0 || HalfWidthPixels < 0.0)
    {
        return Tape;
    }

    constexpr double TickIntervalDegrees = 10.0;
    constexpr double MajorIntervalDegrees = 30.0;
    const double HalfSpanDegrees = HalfWidthPixels / PixelsPerDegree;
    const double FirstTick = std::ceil(
        (Tape.LubberBearingDegrees - HalfSpanDegrees) / TickIntervalDegrees)
        * TickIntervalDegrees;
    const double LastTick = std::floor(
        (Tape.LubberBearingDegrees + HalfSpanDegrees) / TickIntervalDegrees)
        * TickIntervalDegrees;

    for (double UnwrappedBearing = FirstTick;
         UnwrappedBearing <= LastTick;
         UnwrappedBearing += TickIntervalDegrees)
    {
        Tape.Ticks.push_back({
            normalize_compass_degrees(UnwrappedBearing),
            (UnwrappedBearing - Tape.LubberBearingDegrees) * PixelsPerDegree,
            std::fmod(std::abs(UnwrappedBearing), MajorIntervalDegrees) == 0.0
        });
    }
    return Tape;
}

} // namespace gis_unreal
