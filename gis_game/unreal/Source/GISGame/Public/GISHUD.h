#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "GISUILayout.h"
#include "GISHUD.generated.h"

class AGISBoatPawn;
class UFont;
class UTexture2D;

UCLASS()
class GISGAME_API AGISHUD : public AHUD
{
    GENERATED_BODY()

public:
    virtual void BeginPlay() override;
    virtual void DrawHUD() override;

    // Called by the helm input before a mouse drag starts. A consumed click
    // operates the chart/data controls without moving the tiller.
    bool HandlePointerPress(float ScreenX, float ScreenY);
    void ToggleMap();
    void ToggleDataPanel();
    void TogglePauseMenu();
    bool IsMenuOpen() const { return bMenuOpen; }

private:
    UPROPERTY(Transient)
    TObjectPtr<UTexture2D> GreenwoodMapTexture;

    bool bMapExpanded = false;
    bool bDataCollapsed = false;
    bool bMenuOpen = false;
    bool bSettingsOpen = false;

    void DrawDataPanel(const AGISBoatPawn& Boat,
                       const gis_unreal::FHUDLayout& Layout, UFont* Font);
    void DrawWindInstrument(const AGISBoatPawn& Boat,
                            const gis_unreal::FHUDLayout& Layout, UFont* Font);
    void DrawMapPanel(const AGISBoatPawn& Boat,
                      const gis_unreal::FHUDRect& Rect,
                      bool bExpanded, UFont* Font);
    void DrawPauseMenu(UFont* Font);
    void ResumeGame();
};
