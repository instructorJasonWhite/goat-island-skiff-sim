#include "../Source/GISGame/Public/GISMapProjection.h"

#include <cmath>
#include <iostream>

namespace
{
int Failures = 0;

void ExpectNear(const char* Label, double Actual, double Expected)
{
    if (!std::isfinite(Actual) || std::abs(Actual - Expected) > 1e-9)
    {
        std::cerr << Label << ": expected " << Expected << ", got " << Actual << '\n';
        ++Failures;
    }
}

void TestFitCentersWorldAndKeepsNorthUp()
{
    // World is 200 m east/west by 100 m north/south. After 20 px padding,
    // the 400x300 viewport admits a 360x180 drawing centered at (30, 80).
    const gis_unreal::FMapBounds World{0.0, 0.0, 200.0, 100.0};
    const gis_unreal::FMapScreenRect Viewport{10.0, 20.0, 400.0, 300.0};
    const auto Map = gis_unreal::make_north_up_map_projection(World, Viewport, 20.0);

    if (!Map.bValid)
    {
        std::cerr << "Expected a valid projection\n";
        ++Failures;
        return;
    }
    ExpectNear("draw left", Map.DrawRect.X, 30.0);
    ExpectNear("draw top", Map.DrawRect.Y, 80.0);
    ExpectNear("draw width", Map.DrawRect.Width, 360.0);
    ExpectNear("draw height", Map.DrawRect.Height, 180.0);

    const auto Northwest = Map.Project(0.0, 100.0);
    const auto Southeast = Map.Project(200.0, 0.0);
    const auto Center = Map.Project(100.0, 50.0);
    ExpectNear("northwest x", Northwest.X, 30.0);
    ExpectNear("northwest y", Northwest.Y, 80.0);
    ExpectNear("southeast x", Southeast.X, 390.0);
    ExpectNear("southeast y", Southeast.Y, 260.0);
    ExpectNear("center x", Center.X, 210.0);
    ExpectNear("center y", Center.Y, 170.0);
}

void TestBoatArrowUsesCoreHeadingWithoutMirroringNorth()
{
    const gis_unreal::FMapPoint Boat{210.0, 170.0};
    const auto East = gis_unreal::heading_tip(Boat, 0.0, 10.0);
    const auto North = gis_unreal::heading_tip(Boat, 3.14159265358979323846 / 2.0, 10.0);
    const auto West = gis_unreal::heading_tip(Boat, 3.14159265358979323846, 10.0);
    ExpectNear("east tip x", East.X, 220.0);
    ExpectNear("east tip y", East.Y, 170.0);
    ExpectNear("north tip x", North.X, 210.0);
    ExpectNear("north tip y", North.Y, 160.0);
    ExpectNear("west tip x", West.X, 200.0);
    ExpectNear("west tip y", West.Y, 170.0);
}

void TestDegenerateBoundsAndViewportAreRejected()
{
    const gis_unreal::FMapBounds ZeroWidth{1.0, 0.0, 1.0, 100.0};
    const gis_unreal::FMapBounds ValidWorld{0.0, 0.0, 200.0, 100.0};
    const gis_unreal::FMapScreenRect Viewport{10.0, 20.0, 400.0, 300.0};
    if (gis_unreal::make_north_up_map_projection(ZeroWidth, Viewport, 10.0).bValid)
    {
        std::cerr << "Zero-width world bounds should be rejected\n";
        ++Failures;
    }
    if (gis_unreal::make_north_up_map_projection(ValidWorld, Viewport, 160.0).bValid)
    {
        std::cerr << "Padding that consumes the viewport should be rejected\n";
        ++Failures;
    }
}

void TestGreenwoodTextureUVsRemainAlignedWithNorthUpLake()
{
    // The staged aerial image spans -16,128..16,128 m east and north.
    const auto Northwest = gis_unreal::greenwood_image_uv(-16128.0, 16128.0);
    const auto Center = gis_unreal::greenwood_image_uv(0.0, 0.0);
    const auto Southeast = gis_unreal::greenwood_image_uv(16128.0, -16128.0);
    ExpectNear("northwest texture u", Northwest.X, 0.0);
    ExpectNear("northwest texture v", Northwest.Y, 0.0);
    ExpectNear("center texture u", Center.X, 0.5);
    ExpectNear("center texture v", Center.Y, 0.5);
    ExpectNear("southeast texture u", Southeast.X, 1.0);
    ExpectNear("southeast texture v", Southeast.Y, 1.0);
}

void TestMinimapViewportCentersOnBoat()
{
    const auto View = gis_unreal::make_greenwood_minimap_view(0.0, 0.0);
    if (!View.bValid)
    {
        std::cerr << "Expected a valid minimap viewport\n";
        ++Failures;
        return;
    }
    ExpectNear("centered viewport min u", View.MinU, 0.42);
    ExpectNear("centered viewport min v", View.MinV, 0.42);
    ExpectNear("centered viewport max u", View.MaxU, 0.58);
    ExpectNear("centered viewport max v", View.MaxV, 0.58);
    const auto Boat = View.WorldToLocal(0.0, 0.0);
    ExpectNear("centered boat local x", Boat.X, 0.5);
    ExpectNear("centered boat local y", Boat.Y, 0.5);
}

void TestMinimapViewportClampsAtImageEdges()
{
    const auto Northwest = gis_unreal::make_greenwood_minimap_view(-16128.0, 16128.0);
    ExpectNear("northwest min u", Northwest.MinU, 0.0);
    ExpectNear("northwest min v", Northwest.MinV, 0.0);
    ExpectNear("northwest max u", Northwest.MaxU, 0.16);
    ExpectNear("northwest max v", Northwest.MaxV, 0.16);
    const auto NorthwestBoat = Northwest.WorldToLocal(-16128.0, 16128.0);
    ExpectNear("northwest boat local x", NorthwestBoat.X, 0.0);
    ExpectNear("northwest boat local y", NorthwestBoat.Y, 0.0);

    const auto Southeast = gis_unreal::make_greenwood_minimap_view(16128.0, -16128.0);
    ExpectNear("southeast min u", Southeast.MinU, 0.84);
    ExpectNear("southeast min v", Southeast.MinV, 0.84);
    ExpectNear("southeast max u", Southeast.MaxU, 1.0);
    ExpectNear("southeast max v", Southeast.MaxV, 1.0);
    const auto SoutheastBoat = Southeast.WorldToLocal(16128.0, -16128.0);
    ExpectNear("southeast boat local x", SoutheastBoat.X, 1.0);
    ExpectNear("southeast boat local y", SoutheastBoat.Y, 1.0);
}

void TestMinimapViewportPreservesNorthUp()
{
    const auto View = gis_unreal::make_greenwood_minimap_view(0.0, 0.0);
    const auto Boat = View.WorldToLocal(0.0, 0.0);
    const auto North = View.WorldToLocal(0.0, 100.0);
    const auto East = View.WorldToLocal(100.0, 0.0);
    if (!(North.Y < Boat.Y && East.X > Boat.X))
    {
        std::cerr << "North must appear above the boat and east to its right\n";
        ++Failures;
    }
    ExpectNear("north x unchanged", North.X, Boat.X);
    ExpectNear("east y unchanged", East.Y, Boat.Y);
}
} // namespace

int main()
{
    TestFitCentersWorldAndKeepsNorthUp();
    TestBoatArrowUsesCoreHeadingWithoutMirroringNorth();
    TestDegenerateBoundsAndViewportAreRejected();
    TestGreenwoodTextureUVsRemainAlignedWithNorthUpLake();
    TestMinimapViewportCentersOnBoat();
    TestMinimapViewportClampsAtImageEdges();
    TestMinimapViewportPreservesNorthUp();
    if (Failures != 0)
    {
        return 1;
    }
    std::cout << "GIS north-up map projection tests passed\n";
    return 0;
}
