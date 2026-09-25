#pragma once

#include "GISUILayout.h"

#include <algorithm>

namespace gis_unreal {

enum class EMenuPage { Pause, Settings };

enum class EMenuHit {
    Overlay,
    Resume,
    OpenSettings,
    Quit,
    GraphicsPrevious,
    GraphicsNext,
    DisplayPrevious,
    DisplayNext,
    SensitivityPrevious,
    SensitivityNext,
    Back,
};

struct FMenuLayout {
    double Scale = 1.0;

    FHUDRect PausePanel;
    FHUDRect Resume;
    FHUDRect OpenSettings;
    FHUDRect Quit;

    FHUDRect SettingsPanel;
    FHUDRect GraphicsRow;
    FHUDRect GraphicsPrevious;
    FHUDRect GraphicsValue;
    FHUDRect GraphicsNext;
    FHUDRect DisplayRow;
    FHUDRect DisplayPrevious;
    FHUDRect DisplayValue;
    FHUDRect DisplayNext;
    FHUDRect SensitivityRow;
    FHUDRect SensitivityPrevious;
    FHUDRect SensitivityValue;
    FHUDRect SensitivityNext;
    FHUDRect Back;
};

inline FMenuLayout make_menu_layout(double ViewWidth, double ViewHeight)
{
    const double Width = std::max(1.0, ViewWidth);
    const double Height = std::max(1.0, ViewHeight);
    const double S = std::clamp(
        std::min(Width / 1280.0, Height / 720.0), 0.01, 1.25);

    FMenuLayout Layout;
    Layout.Scale = S;
    Layout.PausePanel = {(Width - 420.0*S)/2.0,
                         (Height - 360.0*S)/2.0,
                         420.0*S, 360.0*S};
    const double PauseButtonX = Layout.PausePanel.Left + 35.0*S;
    Layout.Resume = {PauseButtonX, Layout.PausePanel.Top + 94.0*S,
                     350.0*S, 56.0*S};
    Layout.OpenSettings = {PauseButtonX,
                           Layout.PausePanel.Top + 168.0*S,
                           350.0*S, 56.0*S};
    Layout.Quit = {PauseButtonX, Layout.PausePanel.Top + 242.0*S,
                   350.0*S, 56.0*S};

    Layout.SettingsPanel = {(Width - 600.0*S)/2.0,
                            (Height - 444.0*S)/2.0,
                            600.0*S, 444.0*S};
    const double RowX = Layout.SettingsPanel.Left + 28.0*S;
    const auto Row = [&](double Offset) -> FHUDRect {
        return {RowX, Layout.SettingsPanel.Top + Offset*S,
                544.0*S, 64.0*S};
    };
    const auto Previous = [&](const FHUDRect& R) -> FHUDRect {
        return {R.Left + 344.0*S, R.Top + 10.0*S, 40.0*S, 44.0*S};
    };
    const auto Value = [&](const FHUDRect& R) -> FHUDRect {
        return {R.Left + 389.0*S, R.Top + 10.0*S, 102.0*S, 44.0*S};
    };
    const auto Next = [&](const FHUDRect& R) -> FHUDRect {
        return {R.Left + 496.0*S, R.Top + 10.0*S, 40.0*S, 44.0*S};
    };

    Layout.GraphicsRow = Row(91.0);
    Layout.GraphicsPrevious = Previous(Layout.GraphicsRow);
    Layout.GraphicsValue = Value(Layout.GraphicsRow);
    Layout.GraphicsNext = Next(Layout.GraphicsRow);
    Layout.DisplayRow = Row(166.0);
    Layout.DisplayPrevious = Previous(Layout.DisplayRow);
    Layout.DisplayValue = Value(Layout.DisplayRow);
    Layout.DisplayNext = Next(Layout.DisplayRow);
    Layout.SensitivityRow = Row(241.0);
    Layout.SensitivityPrevious = Previous(Layout.SensitivityRow);
    Layout.SensitivityValue = Value(Layout.SensitivityRow);
    Layout.SensitivityNext = Next(Layout.SensitivityRow);
    Layout.Back = {RowX, Layout.SettingsPanel.Top + 355.0*S,
                   544.0*S, 54.0*S};
    return Layout;
}

inline EMenuHit hit_test_menu(const FMenuLayout& Layout, EMenuPage Page,
                              double X, double Y)
{
    if (Page == EMenuPage::Pause)
    {
        if (Layout.Resume.Contains(X, Y)) return EMenuHit::Resume;
        if (Layout.OpenSettings.Contains(X, Y)) return EMenuHit::OpenSettings;
        if (Layout.Quit.Contains(X, Y)) return EMenuHit::Quit;
    }
    else
    {
        if (Layout.GraphicsPrevious.Contains(X, Y))
            return EMenuHit::GraphicsPrevious;
        if (Layout.GraphicsNext.Contains(X, Y))
            return EMenuHit::GraphicsNext;
        if (Layout.DisplayPrevious.Contains(X, Y))
            return EMenuHit::DisplayPrevious;
        if (Layout.DisplayNext.Contains(X, Y))
            return EMenuHit::DisplayNext;
        if (Layout.SensitivityPrevious.Contains(X, Y))
            return EMenuHit::SensitivityPrevious;
        if (Layout.SensitivityNext.Contains(X, Y))
            return EMenuHit::SensitivityNext;
        if (Layout.Back.Contains(X, Y)) return EMenuHit::Back;
    }
    // The full-screen menu owns all pointer presses, including its backdrop.
    return EMenuHit::Overlay;
}

} // namespace gis_unreal
