#pragma once

#include <cmath>

// Pure C++ adapter for the portable solver's east/north and port-positive
// convention to Unreal's +X forward, +Y right, +Z up convention. Keeping
// these sign rules here makes them testable without an Unreal installation.
namespace gis_unreal
{
constexpr double Pi = 3.14159265358979323846;
constexpr double CentimetresPerMetre = 100.0;

inline double east_metres_to_ue_x_cm(double EastMetres)
{
    return EastMetres * CentimetresPerMetre;
}

inline double north_metres_to_ue_y_cm(double NorthMetres)
{
    return -NorthMetres * CentimetresPerMetre;
}

inline double core_heading_rad_to_ue_yaw_deg(double HeadingRadians)
{
    // Core +heading turns from east toward north; Unreal +Yaw turns right.
    return -HeadingRadians * 180.0 / Pi;
}

inline double compass_heading_deg_to_ue_yaw_deg(double ClockwiseFromNorth)
{
    return ClockwiseFromNorth - 90.0;
}

inline double east_north_segment_to_ue_yaw_deg(double EastDelta, double NorthDelta)
{
    return std::atan2(-NorthDelta, EastDelta) * 180.0 / Pi;
}

inline double core_heel_rad_to_ue_roll_deg(double StarboardDownRadians)
{
    // In Unreal's +X-forward, +Y-right frame, positive Roll tips +Y down.
    return StarboardDownRadians * 180.0 / Pi;
}

inline double core_port_angle_rad_to_ue_bone_yaw_deg(double PortRadians)
{
    // An aft-pointing boom/foil (-X) under +Yaw moves toward -Y (port).
    return PortRadians * 180.0 / Pi;
}
} // namespace gis_unreal
