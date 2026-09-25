#pragma once

#include <algorithm>
#include <cmath>

// The clips supplied with the Blender boat have specific key positions.
// Convert controls to clip time independently, so every part can move at once.
namespace gis_unreal
{
inline double tiller_clip_fraction(double Degrees)
{
    const double Clamped = std::clamp(Degrees, -45.0, 45.0);
    // The imported clip plays across the rendered boat with its side reversed.
    // Positive helm should swing the forward tiller handle starboard.
    return (45.0 - Clamped) / 135.0;
}

inline double sail_clip_fraction(double Degrees)
{
    const double Clamped = std::clamp(Degrees, -50.0, 50.0);
    // Match the rendered boom to the solver's port-positive angle.
    return (50.0 + Clamped) / 100.0;
}

inline double sail_swing_extrapolation(double Degrees)
{
    return std::clamp(std::abs(Degrees), 0.0, 85.0) / 50.0;
}

inline double lift_clip_fraction(double Lift)
{
    return std::clamp(Lift, 0.0, 1.0);
}

inline double hoist_clip_fraction(double Hoist)
{
    return 1.0 - std::clamp(Hoist, 0.0, 1.0);
}
} // namespace gis_unreal
