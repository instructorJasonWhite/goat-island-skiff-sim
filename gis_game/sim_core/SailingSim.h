#pragma once

#include <cstdint>

namespace gis {

// SI units throughout. World X/Y are east/north. In boat space +X is the bow,
// +Y is port; positive heading and yaw turn toward port. Positive heel puts
// the starboard rail down. Wind is the direction air MOVES, not its source.
struct Vec2 {
    double x = 0.0;
    double y = 0.0;
};

struct State {
    double x = 0.0;                 // world position, metres
    double y = 0.0;
    double heading = 0.0;           // radians counterclockwise from world +X
    double u = 0.0;                 // forward boat velocity, m/s
    double v = 0.0;                 // port boat velocity, m/s
    double yaw_rate = 0.0;          // radians/s, port-positive
    double heel = 0.0;              // radians, starboard rail down positive
    double roll_rate = 0.0;         // radians/s
    double boom_angle = 0.0;        // radians from aft toward port
    double rudder_angle = 0.0;      // trailing edge port positive
    double time = 0.0;              // seconds since wind-field origin
    bool capsized = false;          // sticky until caller resets the boat
};

struct Input {
    Vec2 true_wind;                 // world-space air velocity, m/s
    double sheet_ease = 0.0;        // 0 close hauled, 1 fully eased
    double helm = 0.0;              // -1 starboard turn, +1 port turn ahead
    double crew_shift = 0.0;        // metres from centerline toward port
    double centerboard = 1.0;       // 0 fully up, 1 fully lowered
    double rudder_immersion = 1.0;   // 0 blade clear of water, 1 fully down
    double sail_hoist = 1.0;        // 0 lowered, 1 fully hoisted
};

// Starting estimates for one Goat Island Skiff, not a measured polar or a
// hydrostatic model. Tune against real GPS, heel, and steering observations.
struct Params {
    double hull_mass = 58.0;                // kg
    double crew_mass = 80.0;                // kg
    double length = 4.73;                   // m
    double waterline_length = 4.25;        // m
    double beam = 1.52;                    // m
    double sail_area = 9.75;               // m^2
    double air_density = 1.225;            // kg/m^3
    double water_density = 998.0;          // fresh lake water, kg/m^3
    double gravity = 9.81;                 // m/s^2

    double sail_ce_x = -0.24;              // metres aft of CG
    double sail_ce_height = 2.15;          // metres above roll center
    double sail_lift_max = 1.05;
    double sail_stall_angle = 0.35;        // radians, about 20 degrees
    double sail_drag_min = 0.12;
    double sail_drag_crossflow = 1.20;
    double minimum_boom_angle = 0.174533;  // 10 degrees
    double maximum_boom_angle = 1.483530;  // 85 degrees
    double boom_rate_limit = 2.6;          // radians/s
    double boom_side_deadband = 0.12;      // m/s transverse apparent wind

    double centerboard_area = 0.34;        // m^2 when fully down
    double centerboard_x = 0.0;            // metres relative to CG
    double centerboard_z = -0.30;          // metres below roll center
    double rudder_area = 0.11;             // m^2 immersed
    double rudder_x = -2.12;               // metres aft of CG
    double rudder_z = -0.18;               // metres below roll center
    double foil_lift_max = 0.90;
    double foil_stall_angle = 0.27;        // radians, about 15 degrees
    double foil_drag_min = 0.02;
    double foil_induced_drag = 0.09;
    double foil_crossflow_drag = 0.70;
    double maximum_rudder_angle = 0.785398; // 45 degrees
    double rudder_rate_limit = 2.5;        // radians/s

    double surge_drag_linear = 15.0;       // N/(m/s)
    double surge_drag_quadratic = 35.0;    // N/(m/s)^2 displacement
    double planing_drag_quadratic = 22.0;  // N/(m/s)^2 when planing
    double planing_onset = 2.8;            // m/s
    double planing_full = 4.2;             // m/s
    double wave_hump_force = 35.0;        // N near displacement hump
    double wave_hump_speed = 2.7;         // m/s
    double wave_hump_width = 0.55;        // m/s
    double sway_drag_linear = 38.0;       // N/(m/s)
    double sway_drag_quadratic = 225.0;   // N/(m/s)^2
    double yaw_drag_linear = 75.0;        // N m/(rad/s)
    double yaw_drag_quadratic = 100.0;    // N m/(rad/s)^2
    double yaw_inertia = 320.0;           // kg m^2

    double righting_arm = 0.75;           // m coefficient of sin(heel)cos(heel)
    double roll_inertia = 100.0;          // kg m^2
    double roll_drag_linear = 180.0;      // N m/(rad/s)
    double roll_drag_quadratic = 90.0;    // N m/(rad/s)^2
    double capsize_angle = 1.396263;      // 80 degrees
    double swamped_drag_multiplier = 4.0;

    std::uint32_t wind_seed = 1939;
    double gust_speed_std = 1.0;          // approximate m/s amplitude
    double gust_direction_std = 0.087266; // radians, about 5 degrees
    double gust_spatial_scale = 120.0;    // m
    double gust_time_scale = 25.0;        // s
};

struct StepResult {
    Vec2 true_wind_world;
    Vec2 apparent_wind_boat;
    Vec2 sail_force;                       // boat-space N
    Vec2 centerboard_force;
    Vec2 rudder_force;
    Vec2 hull_force;
    double sail_incidence = 0.0;          // radians, signed
    double apparent_wind_speed = 0.0;     // m/s
    double planing_fraction = 0.0;        // 0 displacement, 1 planing
    double heeling_moment = 0.0;          // N m, starboard-down positive
    double righting_moment = 0.0;         // N m, starboard-down positive
    double yaw_moment = 0.0;              // N m, port-turn positive
    bool capsized = false;
};

Vec2 sample_wind(const State& state, const Input& input, const Params& params);

// One explicit fixed physics substep. Call at 60–120 Hz; do not pass a whole
// variable render frame here. Throws for dt outside (0, 1/30] seconds.
StepResult step(State& state, const Input& input, const Params& params, double dt);

} // namespace gis
