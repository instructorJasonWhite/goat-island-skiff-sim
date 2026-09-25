#pragma once

#include <cmath>

namespace gis_unreal
{

inline int clamp_graphics_quality(int quality)
{
    return quality < 0 ? 0 : (quality > 4 ? 4 : quality);
}

inline float sanitize_helm_sensitivity(float sensitivity)
{
    if (!std::isfinite(sensitivity))
    {
        return 1.0f;
    }
    return sensitivity < 0.5f ? 0.5f : (sensitivity > 2.0f ? 2.0f : sensitivity);
}

} // namespace gis_unreal
