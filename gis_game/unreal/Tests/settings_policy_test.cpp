#include "../Source/GISGame/Public/GISSettingsPolicy.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>

int main()
{
    using namespace gis_unreal;

    assert(clamp_graphics_quality(-2) == 0);
    assert(clamp_graphics_quality(2) == 2);
    assert(clamp_graphics_quality(9) == 4);

    assert(std::abs(sanitize_helm_sensitivity(0.1f) - 0.5f) < 0.001f);
    assert(std::abs(sanitize_helm_sensitivity(1.25f) - 1.25f) < 0.001f);
    assert(std::abs(sanitize_helm_sensitivity(9.0f) - 2.0f) < 0.001f);
    assert(std::abs(sanitize_helm_sensitivity(
        std::numeric_limits<float>::quiet_NaN()) - 1.0f) < 0.001f);

    std::cout << "Settings value policy passed\n";
}
