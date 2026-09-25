#include "../Source/GISGame/Public/GISRigSampling.h"
#include "../Source/GISGame/Public/GISCoordinates.h"
#include "../../sim_core/SailingSim.h"

#include <cassert>
#include <cmath>
#include <iostream>

namespace
{
bool near(double A, double B)
{
    return std::abs(A - B) < 1e-9;
}

double run_with_wind_from_one_stern_quarter(const double WindPortVelocity)
{
    gis::Params Params;
    Params.gust_speed_std = 0.0;
    Params.gust_direction_std = 0.0;
    Params.yaw_inertia = 1e9; // Hold heading while the boom pays out.
    gis::Input Input;
    Input.true_wind = {8.0, WindPortVelocity};
    Input.sheet_ease = 1.0;
    gis::State Boat;
    Boat.u = 2.0;
    for (int Step = 0; Step < 60; ++Step)
    {
        gis::step(Boat, Input, Params, 1.0 / 120.0);
    }
    return Boat.boom_angle;
}
}

int main()
{
    using namespace gis_unreal;

    // Imported playback also reverses the boom side: with apparent wind
    // from port, the live boom went port rather than starboard. A portward
    // solver boom angle must sample the opposite imported endpoint.
    assert(near(sail_clip_fraction(50.0), 1.0));
    assert(near(sail_clip_fraction(0.0), 0.5));
    assert(near(sail_clip_fraction(-50.0), 0.0));
    // Wide sail angles must use these same endpoints when extrapolated.
    assert(near(sail_clip_fraction(85.0), 1.0));
    assert(near(sail_clip_fraction(-85.0), 0.0));

    // Imported playback reverses the visible tiller swing: the runtime
    // positive-helm screenshot put its forward handle on port. Sampling the
    // opposite authored endpoint puts a positive-helm handle on starboard.
    assert(near(tiller_clip_fraction(-45.0), 2.0 / 3.0));
    assert(near(tiller_clip_fraction(0.0), 1.0 / 3.0));
    assert(near(tiller_clip_fraction(45.0), 0.0));
    assert(near(tiller_clip_fraction(90.0), 0.0));
    assert(near(sail_swing_extrapolation(85.0), 1.7));
    assert(near(sail_swing_extrapolation(-35.0), 0.7));

    // On a run, wind from starboard drives the boom to port and vice versa.
    // Both sides need the matching end of the *imported* animation clip.
    const double StarboardWindBoom = run_with_wind_from_one_stern_quarter(1.5);
    const double PortWindBoom = run_with_wind_from_one_stern_quarter(-1.5);
    assert(StarboardWindBoom > 50.0 * gis_unreal::Pi / 180.0);
    assert(PortWindBoom < -50.0 * gis_unreal::Pi / 180.0);
    assert(near(sail_clip_fraction(StarboardWindBoom * 180.0 / gis_unreal::Pi), 1.0));
    assert(near(sail_clip_fraction(PortWindBoom * 180.0 / gis_unreal::Pi), 0.0));

    // The imported blade and board clips run from down to up, while the
    // hoist clip runs from a full sail to the furled, lowered position.
    assert(near(lift_clip_fraction(-1.0), 0.0));
    assert(near(lift_clip_fraction(1.0), 1.0));
    assert(near(hoist_clip_fraction(1.0), 0.0));
    assert(near(hoist_clip_fraction(0.5), 0.5));
    assert(near(hoist_clip_fraction(0.0), 1.0));

    std::cout << "Rig clip sampling checks passed\n";
}
