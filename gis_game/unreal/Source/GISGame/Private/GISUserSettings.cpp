#include "GISUserSettings.h"

#include "GISSettingsPolicy.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "GameFramework/GameUserSettings.h"
#include "Misc/ConfigCacheIni.h"

namespace
{
constexpr TCHAR ControlsSection[] = TEXT("GISGame.Controls");
constexpr TCHAR HelmSensitivityKey[] = TEXT("HelmSensitivity");

UGameUserSettings* GameSettings()
{
    return GEngine ? GEngine->GetGameUserSettings() : nullptr;
}
}

int32 FGISUserSettings::GetGraphicsQuality()
{
    const UGameUserSettings* Settings = GameSettings();
    return Settings ? Settings->GetOverallScalabilityLevel() : 2;
}

void FGISUserSettings::SetGraphicsQuality(int32 Quality)
{
    if (UGameUserSettings* Settings = GameSettings())
    {
        Settings->SetOverallScalabilityLevel(gis_unreal::clamp_graphics_quality(Quality));
        // ApplySettings also saves GameUserSettings.ini.
        Settings->ApplySettings(false);
    }
}

bool FGISUserSettings::IsFullscreen()
{
    const UGameUserSettings* Settings = GameSettings();
    return Settings && Settings->GetFullscreenMode() != EWindowMode::Windowed;
}

void FGISUserSettings::SetFullscreen(bool bFullscreen)
{
    if (UGameUserSettings* Settings = GameSettings())
    {
        Settings->SetFullscreenMode(bFullscreen ? EWindowMode::WindowedFullscreen
                                                : EWindowMode::Windowed);
        Settings->ConfirmVideoMode();
        Settings->ApplySettings(false);
    }
}

float FGISUserSettings::GetHelmSensitivity()
{
    float Sensitivity = 1.0f;
    if (GConfig && !GGameUserSettingsIni.IsEmpty())
    {
        GConfig->GetFloat(ControlsSection, HelmSensitivityKey,
                          Sensitivity, GGameUserSettingsIni);
    }
    return gis_unreal::sanitize_helm_sensitivity(Sensitivity);
}

void FGISUserSettings::SetHelmSensitivity(float Sensitivity)
{
    if (GConfig && !GGameUserSettingsIni.IsEmpty())
    {
        GConfig->SetFloat(ControlsSection, HelmSensitivityKey,
                          gis_unreal::sanitize_helm_sensitivity(Sensitivity),
                          GGameUserSettingsIni);
        GConfig->Flush(false, GGameUserSettingsIni);
    }
}
