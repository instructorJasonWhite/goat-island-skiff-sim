#pragma once

#include "CoreMinimal.h"

// Thin interface for settings used by both the HUD and boat input. Unreal's
// GameUserSettings persists graphics and display choices; the custom control
// value is stored alongside them in GameUserSettings.ini.
struct FGISUserSettings
{
    // 0 Low, 1 Medium, 2 High, 3 Epic, 4 Cinematic; -1 means custom.
    static int32 GetGraphicsQuality();
    static void SetGraphicsQuality(int32 Quality);

    // Fullscreen uses borderless desktop resolution for reliable switching.
    static bool IsFullscreen();
    static void SetFullscreen(bool bFullscreen);

    // Mouse helm multiplier, default 1.0, restricted to 0.5..2.0.
    static float GetHelmSensitivity();
    static void SetHelmSensitivity(float Sensitivity);
};
