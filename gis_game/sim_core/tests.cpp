#include "SailingSim.h"

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

using gis::Input;
using gis::Params;
using gis::State;
using gis::Vec2;

constexpr double kPi = 3.14159265358979323846;
double deg(double degrees) { return degrees * kPi / 180.0; }

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

double speed(Vec2 v) { return std::hypot(v.x, v.y); }

void test_rest_without_wind() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    State s;
    Input in;
    for (int i = 0; i < 1200; ++i) gis::step(s, in, p, 1.0 / 120.0);
    require(std::abs(s.x) < 1e-9 && std::abs(s.y) < 1e-9,
            "A windless boat at rest must remain at rest");
    require(std::abs(s.heel) < 1e-9 && std::abs(s.yaw_rate) < 1e-9,
            "A windless boat must not roll or turn spontaneously");
}

void test_sail_points_of_sail() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    Input in;
    State s;

    // +X is bow, +Y is port. Air moving toward -Y is a port-side beam wind.
    in.true_wind = {0.0, -6.0};
    in.sheet_ease = 0.55;
    s.boom_angle = -deg(45.0);
    const auto beam = gis::step(s, in, p, 1.0 / 120.0);
    require(beam.sail_force.x > 10.0, "A trimmed beam reach must drive forward");
    require(beam.sail_force.y < -10.0, "Port-side wind must push leeward");

    // With wind exactly on the bow there is no source of positive drive.
    s = {};
    s.boom_angle = -deg(10.0);
    in.true_wind = {-6.0, 0.0};
    in.sheet_ease = 0.0;
    const auto head = gis::step(s, in, p, 1.0 / 120.0);
    require(head.sail_force.x <= 0.0,
            "A head-to-wind sail must not generate forward thrust");

    // A run gets its drive mainly from pressure drag rather than lift.
    s = {};
    s.boom_angle = -deg(80.0);
    in.true_wind = {6.0, -0.1};
    in.sheet_ease = 0.95;
    const auto run = gis::step(s, in, p, 1.0 / 120.0);
    require(run.sail_force.x > 10.0, "A broad run must drive forward");
}

void test_beam_wind_heels_to_leeward() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    Input in;
    in.sheet_ease = 0.55;

    // Air flowing toward starboard comes from port and lowers starboard.
    in.true_wind = {0.0, -6.0};
    State port_wind;
    port_wind.boom_angle = -deg(45.0);
    const auto port_load = gis::step(port_wind, in, p, 1.0 / 120.0);
    require(port_load.apparent_wind_boat.y < 0.0 &&
            port_load.heeling_moment > 0.0 && port_wind.heel > 0.0,
            "Port beam wind must lower the starboard rail");

    // Reverse the wind and sail; the port rail must now go down.
    in.true_wind = {0.0, 6.0};
    State starboard_wind;
    starboard_wind.boom_angle = deg(45.0);
    const auto starboard_load = gis::step(starboard_wind, in, p, 1.0 / 120.0);
    require(starboard_load.apparent_wind_boat.y > 0.0 &&
            starboard_load.heeling_moment < 0.0 && starboard_wind.heel < 0.0,
            "Starboard beam wind must lower the port rail");
}

void test_luffing_close_wind_does_not_heel_to_windward() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    Input in;
    in.sheet_ease = 0.25;
    const double WindForward = -6.0 * std::cos(deg(15.0));
    const double WindAcross = 6.0 * std::sin(deg(15.0));

    // Near the no-go zone, a loose cloth sail luffs. It cannot maintain
    // windward-facing lift that rolls the boat *toward* the wind.
    in.true_wind = {WindForward, WindAcross};
    State starboard_wind;
    starboard_wind.u = 1.2;
    starboard_wind.boom_angle = deg(29.0);
    const auto starboard_load = gis::step(starboard_wind, in, p, 1.0 / 120.0);
    require(starboard_load.sail_force.y >= 0.0 &&
            starboard_load.heeling_moment <= 0.0,
            "A luffing starboard-side wind must not tip the boat to starboard");

    in.true_wind = {WindForward, -WindAcross};
    State port_wind;
    port_wind.u = 1.2;
    port_wind.boom_angle = -deg(29.0);
    const auto port_load = gis::step(port_wind, in, p, 1.0 / 120.0);
    require(port_load.sail_force.y <= 0.0 &&
            port_load.heeling_moment >= 0.0,
            "A luffing port-side wind must not tip the boat to port");
}

void test_running_sail_seeks_the_leeward_side() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    p.yaw_inertia = 1e9;
    Input in;
    in.sheet_ease = 0.80;

    // Wind arrives from abaft starboard, so the boom belongs to port.
    in.true_wind = {5.0, 4.0};
    State starboard_wind;
    starboard_wind.boom_angle = -deg(50.0);
    for (int i = 0; i < 120; ++i)
        gis::step(starboard_wind, in, p, 1.0 / 120.0);
    require(starboard_wind.boom_angle > deg(20.0),
            "A run with starboard wind must carry the sail to port");

    in.true_wind = {5.0, -4.0};
    State port_wind;
    port_wind.boom_angle = deg(50.0);
    for (int i = 0; i < 120; ++i)
        gis::step(port_wind, in, p, 1.0 / 120.0);
    require(port_wind.boom_angle < -deg(20.0),
            "A run with port wind must carry the sail to starboard");
}

void test_backwinded_sail_has_a_gust_knockdown_risk() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    Input in;
    in.sheet_ease = 0.25;
    const double Across = std::sin(deg(45.0));

    // The boom starts on the *same* side as the incoming starboard wind.
    // It must be able to load hard before crossing to the leeward side.
    in.true_wind = {-12.0 * Across, 12.0 * Across};
    State backwinded;
    backwinded.u = 1.2;
    backwinded.boom_angle = -deg(29.0);
    const auto gust = gis::step(backwinded, in, p, 1.0 / 120.0);
    State normally_trimmed;
    normally_trimmed.u = 1.2;
    normally_trimmed.boom_angle = deg(29.0);
    const auto ordinary = gis::step(normally_trimmed, in, p, 1.0 / 120.0);
    require(gust.heeling_moment < 1.4 * ordinary.heeling_moment &&
            gust.heeling_moment < -1000.0 && !backwinded.capsized,
            "A backwinded sail must load hard without instant capsize");
    for (int i = 0; i < 240 && !backwinded.capsized; ++i)
        gis::step(backwinded, in, p, 1.0 / 120.0);
    require(backwinded.capsized,
            "A strong gust on a backwinded sail must be able to capsize");

    in.true_wind = {-12.0 * Across, -12.0 * Across};
    State port_backwinded;
    port_backwinded.u = 1.2;
    port_backwinded.boom_angle = deg(29.0);
    const auto port_gust = gis::step(port_backwinded, in, p, 1.0 / 120.0);
    require(port_gust.heeling_moment > 1000.0 && !port_backwinded.capsized,
            "A backwinded port-side sail must load toward starboard");
    for (int i = 0; i < 240 && !port_backwinded.capsized; ++i)
        gis::step(port_backwinded, in, p, 1.0 / 120.0);
    require(port_backwinded.capsized && port_backwinded.heel > 0.0,
            "A strong gust with the sail on port must be able to capsize starboard");

    // The same control mistake in ordinary wind must leave recovery time.
    in.true_wind = {-6.0 * Across, 6.0 * Across};
    State light_wind;
    light_wind.u = 1.2;
    light_wind.boom_angle = -deg(29.0);
    for (int i = 0; i < 480; ++i)
        gis::step(light_wind, in, p, 1.0 / 120.0);
    require(!light_wind.capsized,
            "Ordinary backwinding must not force an instant knockdown");
}

void test_water_foils_and_steering_reversal() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    Input in;
    in.sail_hoist = 0.0;
    in.centerboard = 1.0;
    State s;
    s.u = 2.0;
    s.v = 0.3;
    const auto board_down = gis::step(s, in, p, 1.0 / 120.0);
    s = {};
    s.u = 2.0;
    s.v = 0.3;
    in.centerboard = 0.0;
    const auto board_up = gis::step(s, in, p, 1.0 / 120.0);
    require(board_down.centerboard_force.y < -10.0,
            "A lowered centerboard must oppose port leeway");
    require(std::abs(board_up.centerboard_force.y) < 1e-8,
            "A raised centerboard must lose its foil side force");

    in.centerboard = 1.0;
    in.helm = 0.25;
    s = {};
    s.u = 2.0;
    s.rudder_angle = deg(11.25);
    const auto ahead = gis::step(s, in, p, 1.0 / 120.0);
    s = {};
    s.u = -2.0;
    s.rudder_angle = deg(11.25);
    const auto astern = gis::step(s, in, p, 1.0 / 120.0);
    require(ahead.yaw_moment > 10.0, "Positive helm must turn port ahead");
    require(astern.yaw_moment < -10.0,
            "The same rudder angle must reverse its yaw effect astern");

    s = {};
    s.u = 2.0;
    s.rudder_angle = deg(11.25);
    in.rudder_immersion = 0.0;
    const auto raised = gis::step(s, in, p, 1.0 / 120.0);
    require(std::abs(raised.rudder_force.y) < 1e-8,
            "A rudder blade lifted out of the water must lose steering force");
}

void test_hiking_and_capsize() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    Input in;
    in.sail_hoist = 0.0;
    State s;
    s.heel = deg(25.0); // Positive heel means the starboard rail is down.
    const auto centered = gis::step(s, in, p, 1.0 / 120.0);
    s = {};
    s.heel = deg(25.0);
    in.crew_shift = 0.45; // Crew moves toward the high, port rail.
    const auto hiking = gis::step(s, in, p, 1.0 / 120.0);
    require(hiking.righting_moment < centered.righting_moment - 50.0,
            "Hiking to windward must increase righting moment");

    p.yaw_inertia = 1e9; // Hold the beam-wind heading for this isolated roll test.
    in = {};
    in.true_wind = {0.0, -15.0};
    in.sheet_ease = 0.6;
    s = {};
    s.boom_angle = -deg(50.0);
    for (int i = 0; i < 2400 && !s.capsized; ++i)
        gis::step(s, in, p, 1.0 / 120.0);
    require(s.capsized, "An overpowered, un-hiked beam reach must be able to capsize");
}

void test_wind_field_is_reproducible_and_correlated() {
    Params p;
    p.wind_seed = 12345;
    p.gust_speed_std = 1.4;
    p.gust_direction_std = deg(8.0);
    Input in;
    in.true_wind = {-4.0, -5.0};
    State a;
    a.x = 100.0;
    a.y = 200.0;
    a.time = 37.0;
    const Vec2 first = gis::sample_wind(a, in, p);
    const Vec2 again = gis::sample_wind(a, in, p);
    require(first.x == again.x && first.y == again.y,
            "The same seed, place, and time must give identical wind");
    State near = a;
    near.x += 0.5;
    near.time += 0.1;
    State far = a;
    far.x += 500.0;
    far.time += 100.0;
    const Vec2 nearby = gis::sample_wind(near, in, p);
    const Vec2 distant = gis::sample_wind(far, in, p);
    require(speed({first.x - nearby.x, first.y - nearby.y}) <
                speed({first.x - distant.x, first.y - distant.y}),
            "Nearby gust samples should be more alike than distant samples");
}

void test_drag_planing_and_in_irons() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    Input in;
    in.sail_hoist = 0.0;
    State slow;
    slow.u = 1.0;
    const auto low = gis::step(slow, in, p, 1.0 / 120.0);
    State fast;
    fast.u = 4.5;
    const auto high = gis::step(fast, in, p, 1.0 / 120.0);
    require(high.planing_fraction > low.planing_fraction + 0.3,
            "Planing fraction must grow smoothly with boat speed");
    require(high.hull_force.x < low.hull_force.x,
            "Hull resistance must still increase with speed");

    in.true_wind = {-6.0, 0.0};
    in.sail_hoist = 1.0;
    in.helm = 1.0;
    State stalled;
    stalled.u = 0.05;
    stalled.boom_angle = -deg(10.0);
    const auto irons = gis::step(stalled, in, p, 1.0 / 120.0);
    require(irons.sail_force.x <= 0.0 && std::abs(irons.rudder_force.y) < 1.0,
            "Head-to-wind at low speed must have no drive and little rudder authority");
}

void test_tack_depends_on_entry_speed() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    Input in;
    in.true_wind = {-6.0, 0.0}; // Wind comes from world +X.
    in.sheet_ease = 0.0;
    in.helm = 1.0; // Turn port through the wind.

    State powered;
    powered.heading = -deg(40.0);
    powered.u = 2.4;
    powered.boom_angle = -deg(10.0);
    bool crossed = false;
    double speed_at_crossing = 0.0;
    for (int i = 0; i < 720; ++i) {
        gis::step(powered, in, p, 1.0 / 120.0);
        if (!crossed && powered.heading > deg(5.0)) {
            crossed = true;
            speed_at_crossing = powered.u;
        }
    }
    require(crossed && speed_at_crossing > 0.3,
            "A boat entering a tack with way on must cross the eye of the wind");

    State slow;
    slow.heading = -deg(15.0);
    slow.u = 0.18;
    slow.boom_angle = -deg(10.0);
    bool slow_crossed = false;
    for (int i = 0; i < 720; ++i) {
        gis::step(slow, in, p, 1.0 / 120.0);
        if (slow.heading > deg(5.0)) slow_crossed = true;
    }
    require(!slow_crossed && slow.u < 0.3,
            "A slow tack near head-to-wind must be able to hang in irons");
}

void test_jibe_swings_boom_and_reverses_heel() {
    Params p;
    p.gust_speed_std = 0.0;
    p.gust_direction_std = 0.0;
    Input in;
    in.true_wind = {-8.0, 0.0}; // Running west, with wind from the east.
    in.sheet_ease = 0.85;
    in.helm = 0.65;
    State s;
    s.heading = deg(150.0);
    s.u = 2.4;
    s.boom_angle = deg(70.0);
    bool crossed_dead_downwind = false;
    bool boom_crossed = false;
    bool port_side_load = false;
    bool starboard_side_load = false;
    for (int i = 0; i < 900; ++i) {
        const auto forces = gis::step(s, in, p, 1.0 / 120.0);
        if (forces.heeling_moment < -30.0) port_side_load = true;
        if (forces.heeling_moment > 30.0) starboard_side_load = true;
        if (s.heading < -deg(150.0)) crossed_dead_downwind = true;
        if (crossed_dead_downwind && s.boom_angle < -deg(20.0))
            boom_crossed = true;
    }
    require(crossed_dead_downwind && boom_crossed,
            "A powered jibe must pass dead downwind and swing the boom across");
    require(port_side_load && starboard_side_load,
            "The jibe must reverse the sail's heeling load");
}

} // namespace

int main() {
    try {
        test_rest_without_wind();
        test_sail_points_of_sail();
        test_beam_wind_heels_to_leeward();
        test_luffing_close_wind_does_not_heel_to_windward();
        test_running_sail_seeks_the_leeward_side();
        test_backwinded_sail_has_a_gust_knockdown_risk();
        test_water_foils_and_steering_reversal();
        test_hiking_and_capsize();
        test_wind_field_is_reproducible_and_correlated();
        test_drag_planing_and_in_irons();
        test_tack_depends_on_entry_speed();
        test_jibe_swings_boom_and_reverses_heel();
        std::cout << "SailingSim: 12 deterministic behavior tests passed\n";
    } catch (const std::exception& e) {
        std::cerr << "SailingSim failure: " << e.what() << '\n';
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
