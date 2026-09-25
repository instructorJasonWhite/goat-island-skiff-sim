#include "../Source/GISGame/Public/GISCompassTape.h"

#include <cmath>
#include <cstdlib>
#include <iostream>

namespace
{
void expect_near(double Actual, double Expected, const char* Case)
{
    if (std::abs(Actual - Expected) > 1e-9)
    {
        std::cerr << Case << ": expected " << Expected << ", got " << Actual << '\n';
        std::exit(EXIT_FAILURE);
    }
}

const gis_unreal::FCompassTapeTick& find_tick(
    const gis_unreal::FCompassTape& Tape, double Bearing)
{
    for (const auto& Tick : Tape.Ticks)
    {
        if (std::abs(Tick.BearingDegrees - Bearing) < 1e-9)
        {
            return Tick;
        }
    }
    std::cerr << "Missing compass tape tick at " << Bearing << " degrees\n";
    std::exit(EXIT_FAILURE);
}
} // namespace

int main()
{
    using namespace gis_unreal;

    // A 359-degree course and a 1-degree course straddle the same north tick.
    expect_near(normalize_compass_degrees(360.0), 0.0, "full turn");
    expect_near(normalize_compass_degrees(-1.0), 359.0, "negative turn");
    expect_near(normalize_compass_degrees(721.25), 1.25, "multiple turns");

    const FCompassTape BeforeNorth = make_compass_tape(359.0, 4.0, 48.0);
    const FCompassTape AfterNorth = make_compass_tape(1.0, 4.0, 48.0);
    expect_near(BeforeNorth.LubberBearingDegrees, 359.0, "359 lubber bearing");
    expect_near(AfterNorth.LubberBearingDegrees, 1.0, "1 lubber bearing");
    expect_near(find_tick(BeforeNorth, 350.0).OffsetPixels, -36.0,
                "350 before north");
    expect_near(find_tick(BeforeNorth, 0.0).OffsetPixels, 4.0,
                "north before crossing");
    expect_near(find_tick(AfterNorth, 0.0).OffsetPixels, -4.0,
                "north after crossing");
    expect_near(find_tick(AfterNorth, 10.0).OffsetPixels, 36.0,
                "10 after north");

    const FCompassTape MidCourse = make_compass_tape(45.0, 3.0, 50.0);
    expect_near(find_tick(MidCourse, 40.0).OffsetPixels, -15.0,
                "lower bearing left of lubber");
    expect_near(find_tick(MidCourse, 50.0).OffsetPixels, 15.0,
                "higher bearing right of lubber");
    if (!find_tick(BeforeNorth, 0.0).bMajor
        || find_tick(MidCourse, 40.0).bMajor)
    {
        std::cerr << "Major ticks must identify the 30-degree marks\n";
        return EXIT_FAILURE;
    }

    std::cout << "GIS compass tape math tests passed\n";
    return EXIT_SUCCESS;
}
