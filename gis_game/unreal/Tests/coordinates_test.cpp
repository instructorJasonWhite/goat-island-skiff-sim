#include "../Source/GISGame/Public/GISCoordinates.h"

#include <cassert>
#include <cmath>
#include <iostream>

namespace
{
bool near(double A, double B)
{
    return std::abs(A - B) < 1e-9;
}
} // namespace

int main()
{
    using namespace gis_unreal;

    assert(near(east_metres_to_ue_x_cm(2.5), 250.0));
    assert(near(north_metres_to_ue_y_cm(2.5), -250.0));
    assert(near(north_metres_to_ue_y_cm(-1.0), 100.0));

    // Core east remains Unreal +X; core north becomes Unreal -Y.
    assert(near(core_heading_rad_to_ue_yaw_deg(0.0), 0.0));
    assert(near(core_heading_rad_to_ue_yaw_deg(Pi / 2.0), -90.0));
    assert(near(compass_heading_deg_to_ue_yaw_deg(0.0), -90.0));
    assert(near(compass_heading_deg_to_ue_yaw_deg(90.0), 0.0));
    assert(near(compass_heading_deg_to_ue_yaw_deg(180.0), 90.0));
    assert(near(east_north_segment_to_ue_yaw_deg(0.0, 1.0), -90.0));

    // Epic's Rotator convention: +Yaw is right and +Roll is clockwise
    // looking forward. Thus +Roll lowers +Y starboard; a +Yaw rotation
    // of an aft-facing (-X) spar points it toward -Y port.
    const double ThirtyDegrees = Pi / 6.0;
    const double Roll = core_heel_rad_to_ue_roll_deg(ThirtyDegrees);
    const double SparYaw = core_port_angle_rad_to_ue_bone_yaw_deg(ThirtyDegrees);
    assert(near(Roll, 30.0));
    assert(near(SparYaw, 30.0));
    assert(-std::sin(Roll * Pi / 180.0) < 0.0);       // starboard Z falls
    assert(-std::sin(SparYaw * Pi / 180.0) < 0.0);    // aft spar Y goes port

    std::cout << "GIS Unreal coordinate adapter tests passed\n";
    return 0;
}
