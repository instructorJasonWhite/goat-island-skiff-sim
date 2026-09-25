#include "SailingSim.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace gis {
namespace {

constexpr double kPi = 3.14159265358979323846;

double clamp01(double value) { return std::clamp(value, 0.0, 1.0); }
double length(Vec2 value) { return std::hypot(value.x, value.y); }
Vec2 add(Vec2 a, Vec2 b) { return {a.x + b.x, a.y + b.y}; }
Vec2 mul(Vec2 a, double scalar) { return {a.x * scalar, a.y * scalar}; }
double dot(Vec2 a, Vec2 b) { return a.x * b.x + a.y * b.y; }
double cross(Vec2 a, Vec2 b) { return a.x * b.y - a.y * b.x; }
Vec2 left(Vec2 direction) { return {-direction.y, direction.x}; }

Vec2 rotate_to_boat(Vec2 world, double heading) {
    const double c = std::cos(heading), s = std::sin(heading);
    return {c * world.x + s * world.y, -s * world.x + c * world.y};
}

Vec2 rotate_to_world(Vec2 boat, double heading) {
    const double c = std::cos(heading), s = std::sin(heading);
    return {c * boat.x - s * boat.y, s * boat.x + c * boat.y};
}

double smoothstep(double t) {
    t = clamp01(t);
    return t * t * (3.0 - 2.0 * t);
}

std::uint32_t hash(std::int32_t ix, std::int32_t iy, std::int32_t it,
                   std::uint32_t seed) {
    std::uint32_t h = seed ^ 0x9e3779b9u;
    h ^= static_cast<std::uint32_t>(ix) * 0x85ebca6bu;
    h ^= static_cast<std::uint32_t>(iy) * 0xc2b2ae35u;
    h ^= static_cast<std::uint32_t>(it) * 0x27d4eb2fu;
    h ^= h >> 16;
    h *= 0x7feb352du;
    h ^= h >> 15;
    h *= 0x846ca68bu;
    h ^= h >> 16;
    return h;
}

double lattice(std::int32_t x, std::int32_t y, std::int32_t z,
               std::uint32_t seed) {
    return 2.0 * (static_cast<double>(hash(x, y, z, seed)) /
                  static_cast<double>(std::numeric_limits<std::uint32_t>::max())) - 1.0;
}

double value_noise(double x, double y, double t, std::uint32_t seed) {
    const auto ix = static_cast<std::int32_t>(std::floor(x));
    const auto iy = static_cast<std::int32_t>(std::floor(y));
    const auto it = static_cast<std::int32_t>(std::floor(t));
    const double fx = smoothstep(x - static_cast<double>(ix));
    const double fy = smoothstep(y - static_cast<double>(iy));
    const double ft = smoothstep(t - static_cast<double>(it));
    double result = 0.0;
    for (int a = 0; a < 2; ++a) {
        for (int b = 0; b < 2; ++b) {
            for (int c = 0; c < 2; ++c) {
                const double weight = (a ? fx : 1.0 - fx) *
                                      (b ? fy : 1.0 - fy) *
                                      (c ? ft : 1.0 - ft);
                result += weight * lattice(ix + a, iy + b, it + c, seed);
            }
        }
    }
    return result;
}

double lift_coefficient(double incidence, double maximum, double stall) {
    const double a = std::abs(incidence);
    if (a >= kPi * 0.5) return 0.0;
    const double magnitude = a <= stall
        ? maximum * a / stall
        : maximum * std::cos((a - stall) / (kPi * 0.5 - stall) * kPi * 0.5);
    return std::copysign(magnitude, incidence);
}

double wrap_foil_incidence(double angle) {
    // A flat underwater foil can lead with either edge. Wrapping by pi gives
    // continuous transverse force and correct steering reversal while astern.
    while (angle > kPi * 0.5) angle -= kPi;
    while (angle < -kPi * 0.5) angle += kPi;
    return angle;
}

Vec2 water_foil_force(Vec2 local_water_flow, double chord_angle,
                      double immersed_area, const Params& p) {
    const double speed = length(local_water_flow);
    if (speed < 1e-5 || immersed_area <= 0.0) return {};
    const Vec2 flow = mul(local_water_flow, 1.0 / speed);
    const Vec2 chord{-std::cos(chord_angle), std::sin(chord_angle)};
    const double incidence = wrap_foil_incidence(std::atan2(cross(chord, flow),
                                                            dot(chord, flow)));
    const double cl = lift_coefficient(incidence, p.foil_lift_max,
                                       p.foil_stall_angle);
    const double cd = p.foil_drag_min + p.foil_induced_drag * cl * cl +
                      p.foil_crossflow_drag * std::pow(std::sin(incidence), 2.0);
    const double pressure_area = 0.5 * p.water_density * speed * speed * immersed_area;
    return mul(add(mul(left(flow), cl), mul(flow, cd)), pressure_area);
}

double approach(double current, double target, double maximum_change) {
    return current + std::clamp(target - current, -maximum_change, maximum_change);
}

} // namespace

Vec2 sample_wind(const State& s, const Input& in, const Params& p) {
    const double base_speed = length(in.true_wind);
    if (base_speed < 1e-9) return {};
    const double scale = std::max(p.gust_spatial_scale, 1.0);
    const double time_scale = std::max(p.gust_time_scale, 1.0);
    const double nx = s.x / scale;
    const double ny = s.y / scale;
    const double nt = s.time / time_scale;
    const double speed_noise = value_noise(nx, ny, nt, p.wind_seed);
    const double direction_noise = value_noise(nx + 31.7, ny - 19.4, nt + 8.6,
                                               p.wind_seed ^ 0xa53c9e41u);
    const double speed = std::max(0.0, base_speed + p.gust_speed_std * speed_noise);
    const double angle = p.gust_direction_std * direction_noise;
    const double c = std::cos(angle), ss = std::sin(angle);
    return {(in.true_wind.x * c - in.true_wind.y * ss) * speed / base_speed,
            (in.true_wind.x * ss + in.true_wind.y * c) * speed / base_speed};
}

StepResult step(State& s, const Input& in, const Params& p, double dt) {
    if (!(dt > 0.0 && dt <= 1.0 / 30.0) || !std::isfinite(dt))
        throw std::invalid_argument("SailingSim requires a fixed substep in (0, 1/30] s");

    StepResult out;
    const double mass = std::max(p.hull_mass + p.crew_mass, 1.0);
    out.true_wind_world = sample_wind(s, in, p);
    const Vec2 wind_boat = rotate_to_boat(out.true_wind_world, s.heading);
    const Vec2 air_at_sail{wind_boat.x - s.u,
                           wind_boat.y - (s.v + s.yaw_rate * p.sail_ce_x)};
    out.apparent_wind_boat = air_at_sail;
    out.apparent_wind_speed = length(air_at_sail);

    // Sheet controls maximum boom excursion; wind pressure chooses the side.
    double side = s.boom_angle < 0.0 ? -1.0 : 1.0;
    if (air_at_sail.y < -p.boom_side_deadband) side = -1.0;
    else if (air_at_sail.y > p.boom_side_deadband) side = 1.0;
    const double boom_limit = p.minimum_boom_angle +
        (p.maximum_boom_angle - p.minimum_boom_angle) * clamp01(in.sheet_ease);
    s.boom_angle = approach(s.boom_angle, side * boom_limit,
                            p.boom_rate_limit * dt);
    s.rudder_angle = approach(s.rudder_angle,
        std::clamp(in.helm, -1.0, 1.0) * p.maximum_rudder_angle,
        p.rudder_rate_limit * dt);

    if (out.apparent_wind_speed > 1e-5 && in.sail_hoist > 0.0) {
        const Vec2 flow = mul(air_at_sail, 1.0 / out.apparent_wind_speed);
        const Vec2 chord{-std::cos(s.boom_angle), std::sin(s.boom_angle)};
        out.sail_incidence = std::atan2(cross(chord, flow), dot(chord, flow));
        double cl = lift_coefficient(out.sail_incidence,
                                     p.sail_lift_max, p.sail_stall_angle);
        // Cloth on the backwinded face luffs instead of sustaining attached
        // lift that pulls the boat across the wind and heels it windward.
        if (cl * flow.x * flow.y < 0.0) cl = 0.0;
        const double cd = p.sail_drag_min + p.sail_drag_crossflow *
                          std::pow(std::sin(out.sail_incidence), 2.0);
        const double heel_projection = std::pow(std::max(0.0, std::cos(s.heel)), 1.2);
        const double reef = clamp01(in.sail_hoist);
        const double effective_area = p.sail_area * reef * heel_projection *
                                      (s.capsized ? 0.04 : 1.0);
        const double pressure_area = 0.5 * p.air_density *
                                     out.apparent_wind_speed * out.apparent_wind_speed *
                                     effective_area;
        out.sail_force = mul(add(mul(left(flow), cl), mul(flow, cd)), pressure_area);
    }

    const double immersion = s.capsized ? 0.1 : std::max(0.0, std::cos(s.heel));
    const double board_frac = clamp01(in.centerboard);
    const Vec2 water_at_board{-s.u, -(s.v + s.yaw_rate * p.centerboard_x)};
    const Vec2 water_at_rudder{-s.u, -(s.v + s.yaw_rate * p.rudder_x)};
    out.centerboard_force = water_foil_force(water_at_board, 0.0,
        p.centerboard_area * board_frac * immersion, p);
    out.rudder_force = water_foil_force(water_at_rudder, s.rudder_angle,
        p.rudder_area * clamp01(in.rudder_immersion) * immersion, p);

    const double speed_forward = std::abs(s.u);
    out.planing_fraction = smoothstep((speed_forward - p.planing_onset) /
                                         std::max(0.01, p.planing_full - p.planing_onset));
    const double quadratic_drag = p.surge_drag_quadratic *
        (1.0 - out.planing_fraction) + p.planing_drag_quadratic * out.planing_fraction;
    const double wave_x = (speed_forward - p.wave_hump_speed) /
                          std::max(0.01, p.wave_hump_width);
    const double wave_hump = p.wave_hump_force * std::exp(-wave_x * wave_x);
    const double swamped = s.capsized ? p.swamped_drag_multiplier : 1.0;
    out.hull_force.x = -std::copysign(swamped *
        (p.surge_drag_linear * speed_forward + quadratic_drag * speed_forward *
         speed_forward + wave_hump), s.u);
    if (speed_forward < 1e-9) out.hull_force.x = 0.0;
    out.hull_force.y = -swamped * (p.sway_drag_linear * s.v +
                        p.sway_drag_quadratic * s.v * std::abs(s.v));

    const Vec2 total_force = add(add(out.sail_force, out.centerboard_force),
                                 add(out.rudder_force, out.hull_force));
    out.yaw_moment = p.sail_ce_x * out.sail_force.y +
                     p.centerboard_x * out.centerboard_force.y +
                     p.rudder_x * out.rudder_force.y -
                     p.yaw_drag_linear * s.yaw_rate -
                     p.yaw_drag_quadratic * s.yaw_rate * std::abs(s.yaw_rate);
    out.heeling_moment = -p.sail_ce_height * out.sail_force.y -
                         p.centerboard_z * out.centerboard_force.y -
                         p.rudder_z * out.rudder_force.y;
    out.righting_moment = -mass * p.gravity * p.righting_arm *
                           std::sin(s.heel) * std::cos(s.heel) -
                           p.crew_mass * p.gravity *
                           std::clamp(in.crew_shift, -p.beam * 0.48, p.beam * 0.48) *
                           std::cos(s.heel);
    const double roll_drag = -p.roll_drag_linear * s.roll_rate -
                             p.roll_drag_quadratic * s.roll_rate *
                             std::abs(s.roll_rate);

    // Integrate velocities in rotating body coordinates, then world pose.
    const double old_u = s.u, old_v = s.v, old_yaw = s.yaw_rate;
    s.u += (total_force.x / mass + old_yaw * old_v) * dt;
    s.v += (total_force.y / mass - old_yaw * old_u) * dt;
    s.yaw_rate += out.yaw_moment / std::max(p.yaw_inertia, 1.0) * dt;
    if (!s.capsized) {
        s.roll_rate += (out.heeling_moment + out.righting_moment + roll_drag) /
                       std::max(p.roll_inertia, 1.0) * dt;
        s.heel += s.roll_rate * dt;
        if (std::abs(s.heel) >= p.capsize_angle) {
            s.capsized = true;
            s.heel = std::copysign(kPi * 0.5, s.heel);
            s.roll_rate = 0.0;
        }
    }
    s.heading = std::remainder(s.heading + s.yaw_rate * dt, 2.0 * kPi);
    const Vec2 world_velocity = rotate_to_world({s.u, s.v}, s.heading);
    s.x += world_velocity.x * dt;
    s.y += world_velocity.y * dt;
    s.time += dt;
    out.capsized = s.capsized;
    return out;
}

} // namespace gis
