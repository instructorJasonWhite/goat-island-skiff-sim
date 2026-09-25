#pragma once

#include <algorithm>
#include <cmath>

// Pure C++17 map geometry. World coordinates are local metres: +east and
// +north. Screen coordinates increase right and down.
namespace gis_unreal
{
struct FMapPoint
{
    double X = 0.0;
    double Y = 0.0;
};

struct FMapBounds
{
    double MinEastMetres = 0.0;
    double MinNorthMetres = 0.0;
    double MaxEastMetres = 0.0;
    double MaxNorthMetres = 0.0;
};

struct FMapScreenRect
{
    double X = 0.0;
    double Y = 0.0;
    double Width = 0.0;
    double Height = 0.0;
};

struct FMapProjection
{
    FMapBounds WorldBounds;
    FMapScreenRect DrawRect;
    bool bValid = false;

    FMapPoint Project(double EastMetres, double NorthMetres) const
    {
        const double WorldWidth = WorldBounds.MaxEastMetres - WorldBounds.MinEastMetres;
        const double WorldHeight = WorldBounds.MaxNorthMetres - WorldBounds.MinNorthMetres;
        return {
            DrawRect.X + (EastMetres - WorldBounds.MinEastMetres) * DrawRect.Width / WorldWidth,
            DrawRect.Y + (WorldBounds.MaxNorthMetres - NorthMetres) * DrawRect.Height / WorldHeight
        };
    }
};

inline FMapProjection make_north_up_map_projection(
    FMapBounds WorldBounds, FMapScreenRect Viewport, double PaddingPixels = 0.0)
{
    const double WorldWidth = WorldBounds.MaxEastMetres - WorldBounds.MinEastMetres;
    const double WorldHeight = WorldBounds.MaxNorthMetres - WorldBounds.MinNorthMetres;
    const double AvailableWidth = Viewport.Width - 2.0 * PaddingPixels;
    const double AvailableHeight = Viewport.Height - 2.0 * PaddingPixels;
    if (!std::isfinite(WorldBounds.MinEastMetres)
        || !std::isfinite(WorldBounds.MinNorthMetres)
        || !std::isfinite(WorldBounds.MaxEastMetres)
        || !std::isfinite(WorldBounds.MaxNorthMetres)
        || !std::isfinite(Viewport.X) || !std::isfinite(Viewport.Y)
        || !std::isfinite(Viewport.Width) || !std::isfinite(Viewport.Height)
        || !std::isfinite(PaddingPixels) || PaddingPixels < 0.0
        || WorldWidth <= 0.0 || WorldHeight <= 0.0
        || AvailableWidth <= 0.0 || AvailableHeight <= 0.0)
    {
        return {WorldBounds, {}, false};
    }
    const double Scale = std::min(AvailableWidth / WorldWidth, AvailableHeight / WorldHeight);
    const double DrawWidth = WorldWidth * Scale;
    const double DrawHeight = WorldHeight * Scale;
    return {
        WorldBounds,
        {Viewport.X + (Viewport.Width - DrawWidth) * 0.5,
         Viewport.Y + (Viewport.Height - DrawHeight) * 0.5,
         DrawWidth, DrawHeight},
        true
    };
}

inline FMapPoint heading_tip(FMapPoint BoatScreen, double HeadingRadians,
                             double ArrowLengthPixels)
{
    // Core heading starts east and turns counter-clockwise toward north.
    // Screen Y increases downward, so north is a negative screen delta.
    return {
        BoatScreen.X + std::cos(HeadingRadians) * ArrowLengthPixels,
        BoatScreen.Y - std::sin(HeadingRadians) * ArrowLengthPixels
    };
}

constexpr double GreenwoodImageHalfExtentMetres = 16128.0;

inline FMapPoint greenwood_image_uv(double EastMetres, double NorthMetres)
{
    constexpr double SpanMetres = 2.0 * GreenwoodImageHalfExtentMetres;
    return {
        (EastMetres + GreenwoodImageHalfExtentMetres) / SpanMetres,
        (GreenwoodImageHalfExtentMetres - NorthMetres) / SpanMetres
    };
}

// A cropped portion of the north-up Greenwood aerial image. DrawTexture can
// use MinU/MinV as its UV origin and (MaxU-MinU, MaxV-MinV) as its UV span.
struct FMapUVViewport
{
    double MinU = 0.0;
    double MinV = 0.0;
    double MaxU = 0.0;
    double MaxV = 0.0;
    bool bValid = false;

    FMapPoint WorldToLocal(double EastMetres, double NorthMetres) const
    {
        if (!bValid)
        {
            return {};
        }
        const FMapPoint UV = greenwood_image_uv(EastMetres, NorthMetres);
        return {(UV.X - MinU) / (MaxU - MinU),
                (UV.Y - MinV) / (MaxV - MinV)};
    }
};

inline FMapUVViewport make_greenwood_minimap_view(
    double BoatEastMetres, double BoatNorthMetres, double SpanUV = 0.16)
{
    if (!std::isfinite(BoatEastMetres) || !std::isfinite(BoatNorthMetres)
        || !std::isfinite(SpanUV) || SpanUV <= 0.0 || SpanUV > 1.0)
    {
        return {};
    }
    const FMapPoint BoatUV = greenwood_image_uv(BoatEastMetres, BoatNorthMetres);
    const double MinU = std::clamp(BoatUV.X - SpanUV * 0.5, 0.0, 1.0 - SpanUV);
    const double MinV = std::clamp(BoatUV.Y - SpanUV * 0.5, 0.0, 1.0 - SpanUV);
    return {MinU, MinV, MinU + SpanUV, MinV + SpanUV, true};
}
} // namespace gis_unreal
