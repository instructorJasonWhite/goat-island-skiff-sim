#pragma once

#include <algorithm>

namespace gis_unreal {

struct FHUDRect {
    double Left = 0.0;
    double Top = 0.0;
    double Width = 0.0;
    double Height = 0.0;

    double Right() const { return Left + Width; }
    double Bottom() const { return Top + Height; }
    bool Contains(double X, double Y) const
    {
        return X >= Left && X <= Right() && Y >= Top && Y <= Bottom();
    }
};

struct FHUDLayout {
    double Scale = 1.0;
    FHUDRect DataPanel;
    FHUDRect DataToggle;
    FHUDRect WindPanel;
    FHUDRect MenuButton;
    FHUDRect MiniMap;
    FHUDRect ExpandedMap;
    FHUDRect ExpandedMapClose;
};

enum class EHUDHit { None, MiniMap, DataToggle, MenuButton, MapClose, MapOverlay };

inline FHUDLayout make_hud_layout(double ViewWidth, double ViewHeight)
{
    const double Width = std::max(320.0, ViewWidth);
    const double Height = std::max(240.0, ViewHeight);
    const double Scale = std::clamp(
        std::min(Width / 1280.0, Height / 720.0), 0.65, 1.0);
    const double Margin = 12.0 * Scale;
    const double DataWidth = 292.0 * Scale;
    const double InstrumentWidth = 292.0 * Scale;
    const double MiniSize = 210.0 * Scale;
    const double ExpandedSize = std::min({
        630.0 * Scale, Width - 120.0 * Scale, Height - 100.0 * Scale,
    });

    FHUDLayout Layout;
    Layout.Scale = Scale;
    Layout.DataPanel = {Margin, Margin, DataWidth, 156.0 * Scale};
    Layout.DataToggle = {
        Layout.DataPanel.Right() - 34.0 * Scale,
        Layout.DataPanel.Top + 6.0 * Scale,
        28.0 * Scale, 28.0 * Scale,
    };
    Layout.WindPanel = {
        Width - Margin - InstrumentWidth, Margin,
        InstrumentWidth, 252.0 * Scale,
    };
    Layout.MenuButton = {
        (Width - 118.0 * Scale) / 2.0, Margin,
        118.0 * Scale, 34.0 * Scale,
    };
    Layout.MiniMap = {
        Width - Margin - MiniSize, Height - Margin - MiniSize,
        MiniSize, MiniSize,
    };
    Layout.ExpandedMap = {
        (Width - ExpandedSize) / 2.0,
        (Height - ExpandedSize) / 2.0,
        ExpandedSize, ExpandedSize,
    };
    Layout.ExpandedMapClose = {
        Layout.ExpandedMap.Right() - 44.0 * Scale,
        Layout.ExpandedMap.Top + 7.0 * Scale,
        36.0 * Scale, 30.0 * Scale,
    };
    return Layout;
}

inline EHUDHit hit_test_hud(const FHUDLayout& Layout, bool bMapExpanded,
                            double X, double Y)
{
    if (bMapExpanded)
    {
        return Layout.ExpandedMapClose.Contains(X, Y)
            ? EHUDHit::MapClose : EHUDHit::MapOverlay;
    }
    if (Layout.DataToggle.Contains(X, Y))
    {
        return EHUDHit::DataToggle;
    }
    if (Layout.MenuButton.Contains(X, Y))
    {
        return EHUDHit::MenuButton;
    }
    if (Layout.MiniMap.Contains(X, Y))
    {
        return EHUDHit::MiniMap;
    }
    return EHUDHit::None;
}

} // namespace gis_unreal
