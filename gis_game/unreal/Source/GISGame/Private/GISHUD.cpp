#include "GISHUD.h"

#include "GISBoatPawn.h"
#include "GISCompassTape.h"
#include "GISLandmarkScene.h"
#include "GISMapProjection.h"
#include "GISMenuLayout.h"
#include "GISUserSettings.h"
#include "GISWindDisplay.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Texture2D.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

namespace
{
const FLinearColor Ink(0.025f, 0.055f, 0.062f, 0.92f);
const FLinearColor Brass(0.73f, 0.54f, 0.27f, 1.0f);
const FLinearColor PaleBrass(0.97f, 0.82f, 0.51f, 1.0f);
const FLinearColor DarkBrass(0.27f, 0.21f, 0.12f, 1.0f);
const FLinearColor Cream(0.95f, 0.94f, 0.85f, 1.0f);
const FLinearColor Muted(0.65f, 0.79f, 0.77f, 1.0f);

float F(double Value)
{
    return static_cast<float>(Value);
}

FString CompassLabel(double Bearing)
{
    const int32 Degrees = FMath::RoundToInt(Bearing) % 360;
    switch (Degrees)
    {
    case 0: return TEXT("N");
    case 90: return TEXT("E");
    case 180: return TEXT("S");
    case 270: return TEXT("W");
    default: return FString::Printf(TEXT("%03d"), Degrees);
    }
}
} // namespace

void AGISHUD::BeginPlay()
{
    Super::BeginPlay();
    GreenwoodMapTexture = LoadObject<UTexture2D>(nullptr,
        TEXT("/Game/Environment/T_GreenwoodNAIP.T_GreenwoodNAIP"));
    if (GreenwoodMapTexture)
    {
        // Canvas drawing does not inform the world texture streamer how much
        // detail the cropped minimap needs, so keep the aerial's top mips in.
        GreenwoodMapTexture->SetForceMipLevelsToBeResident(3600.0f);
        GreenwoodMapTexture->WaitForStreaming();
    }
#if !UE_BUILD_SHIPPING
    bMapExpanded = FParse::Param(FCommandLine::Get(), TEXT("GISPreviewFullMap"));
    bDataCollapsed = FParse::Param(FCommandLine::Get(), TEXT("GISPreviewCollapsed"));
#endif
}

bool AGISHUD::HandlePointerPress(float ScreenX, float ScreenY)
{
    int32 ViewWidth = 1280;
    int32 ViewHeight = 720;
    if (Canvas)
    {
        ViewWidth = FMath::RoundToInt(Canvas->ClipX);
        ViewHeight = FMath::RoundToInt(Canvas->ClipY);
    }
    else if (APlayerController* Controller = GetOwningPlayerController())
    {
        Controller->GetViewportSize(ViewWidth, ViewHeight);
    }
    if (bMenuOpen)
    {
        const auto Menu = gis_unreal::make_menu_layout(ViewWidth, ViewHeight);
        const auto Page = bSettingsOpen
            ? gis_unreal::EMenuPage::Settings : gis_unreal::EMenuPage::Pause;
        const auto Hit = gis_unreal::hit_test_menu(Menu, Page, ScreenX, ScreenY);
        switch (Hit)
        {
        case gis_unreal::EMenuHit::Resume:
            ResumeGame();
            break;
        case gis_unreal::EMenuHit::OpenSettings:
            bSettingsOpen = true;
            break;
        case gis_unreal::EMenuHit::Quit:
            UKismetSystemLibrary::QuitGame(this, GetOwningPlayerController(),
                EQuitPreference::Quit, false);
            break;
        case gis_unreal::EMenuHit::GraphicsPrevious:
        case gis_unreal::EMenuHit::GraphicsNext:
        {
            const int32 Current = FGISUserSettings::GetGraphicsQuality();
            const int32 Base = Current < 0 ? 3 : Current;
            const int32 Change = Hit == gis_unreal::EMenuHit::GraphicsNext ? 1 : -1;
            FGISUserSettings::SetGraphicsQuality(FMath::Clamp(Base + Change, 0, 4));
            break;
        }
        case gis_unreal::EMenuHit::DisplayPrevious:
        case gis_unreal::EMenuHit::DisplayNext:
            FGISUserSettings::SetFullscreen(!FGISUserSettings::IsFullscreen());
            break;
        case gis_unreal::EMenuHit::SensitivityPrevious:
            FGISUserSettings::SetHelmSensitivity(
                FGISUserSettings::GetHelmSensitivity() - 0.25f);
            break;
        case gis_unreal::EMenuHit::SensitivityNext:
            FGISUserSettings::SetHelmSensitivity(
                FGISUserSettings::GetHelmSensitivity() + 0.25f);
            break;
        case gis_unreal::EMenuHit::Back:
            bSettingsOpen = false;
            break;
        default:
            break;
        }
        return true;
    }
    const gis_unreal::FHUDLayout Layout = gis_unreal::make_hud_layout(
        ViewWidth, ViewHeight);
    switch (gis_unreal::hit_test_hud(Layout, bMapExpanded, ScreenX, ScreenY))
    {
    case gis_unreal::EHUDHit::MiniMap:
    case gis_unreal::EHUDHit::MapClose:
        ToggleMap();
        return true;
    case gis_unreal::EHUDHit::DataToggle:
        ToggleDataPanel();
        return true;
    case gis_unreal::EHUDHit::MenuButton:
        TogglePauseMenu();
        return true;
    case gis_unreal::EHUDHit::MapOverlay:
        return true;
    default:
        return false;
    }
}

void AGISHUD::ToggleMap()
{
    bMapExpanded = !bMapExpanded;
}

void AGISHUD::ToggleDataPanel()
{
    bDataCollapsed = !bDataCollapsed;
}

void AGISHUD::TogglePauseMenu()
{
    if (!bMenuOpen)
    {
        bMenuOpen = true;
        bSettingsOpen = false;
        UGameplayStatics::SetGamePaused(this, true);
    }
    else if (bSettingsOpen)
    {
        bSettingsOpen = false;
    }
    else
    {
        ResumeGame();
    }
}

void AGISHUD::ResumeGame()
{
    bMenuOpen = false;
    bSettingsOpen = false;
    UGameplayStatics::SetGamePaused(this, false);
}

void AGISHUD::DrawDataPanel(const AGISBoatPawn& Boat,
                           const gis_unreal::FHUDLayout& Layout, UFont* Font)
{
    const double S = Layout.Scale;
    const auto& Rect = Layout.DataPanel;
    const float Height = F(bDataCollapsed ? 43.0 * S : Rect.Height);
    DrawRect(Brass, F(Rect.Left), F(Rect.Top), F(Rect.Width), Height);
    DrawRect(Ink, F(Rect.Left + 2*S), F(Rect.Top + 2*S),
             F(Rect.Width - 4*S), Height - F(4*S));
    DrawText(TEXT("GIS  /  SAILING DATA"), PaleBrass,
             F(Rect.Left + 10*S), F(Rect.Top + 8*S), Font, F(0.96*S));
    DrawRect(Brass, F(Layout.DataToggle.Left), F(Layout.DataToggle.Top),
             F(Layout.DataToggle.Width), F(Layout.DataToggle.Height));
    DrawRect(Ink, F(Layout.DataToggle.Left + S), F(Layout.DataToggle.Top + S),
             F(Layout.DataToggle.Width - 2*S), F(Layout.DataToggle.Height - 2*S));
    DrawText(bDataCollapsed ? TEXT("+") : TEXT("-"), PaleBrass,
             F(Layout.DataToggle.Left + 9*S), F(Layout.DataToggle.Top + 2*S),
             Font, F(1.25*S));

    const gis::State& State = Boat.GetBoatState();
    const double SpeedKnots = FMath::Sqrt(State.u*State.u + State.v*State.v) * 1.943844;
    if (bDataCollapsed)
    {
        DrawText(FString::Printf(TEXT("%.1f kn"), SpeedKnots), Cream,
                 F(Rect.Left + 185*S), F(Rect.Top + 10*S), Font, F(0.96*S));
        return;
    }

    const gis::Input& Input = Boat.GetSailingInput();
    const gis::StepResult& Step = Boat.GetLastStep();
    const double Heading = gis_unreal::normalize_compass_degrees(
        450.0 - FMath::RadiansToDegrees(State.heading));
    DrawLine(F(Rect.Left + 10*S), F(Rect.Top + 35*S),
             F(Rect.Right() - 10*S), F(Rect.Top + 35*S), Brass, F(S));
    DrawText(TEXT("SPEED"), Muted, F(Rect.Left + 12*S), F(Rect.Top + 40*S),
             Font, F(0.78*S));
    DrawText(FString::Printf(TEXT("%.1f kn"), SpeedKnots), Cream,
             F(Rect.Left + 12*S), F(Rect.Top + 56*S), Font, F(1.38*S));
    DrawText(TEXT("HEADING"), Muted, F(Rect.Left + 155*S), F(Rect.Top + 40*S),
             Font, F(0.78*S));
    DrawText(FString::Printf(TEXT("%03.0f deg"), Heading), Cream,
             F(Rect.Left + 155*S), F(Rect.Top + 58*S), Font, F(1.04*S));
    DrawLine(F(Rect.Left + 10*S), F(Rect.Top + 88*S),
             F(Rect.Right() - 10*S), F(Rect.Top + 88*S), Brass, F(0.7*S));
    DrawText(FString::Printf(TEXT("HEEL  %+0.0f deg"),
             FMath::RadiansToDegrees(State.heel)), Cream,
             F(Rect.Left + 12*S), F(Rect.Top + 99*S), Font, F(0.88*S));
    DrawText(FString::Printf(TEXT("WIND  %.1f m/s"),
             Step.apparent_wind_speed), Cream,
             F(Rect.Left + 151*S), F(Rect.Top + 99*S), Font, F(0.88*S));
    DrawText(FString::Printf(TEXT("SHEET  %02.0f%%"), Input.sheet_ease*100.0),
             Cream, F(Rect.Left + 12*S), F(Rect.Top + 123*S), Font, F(0.88*S));
    DrawText(FString::Printf(TEXT("BOARD  %02.0f%%"), Input.centerboard*100.0),
             Cream, F(Rect.Left + 151*S), F(Rect.Top + 123*S), Font, F(0.88*S));
}

void AGISHUD::DrawWindInstrument(const AGISBoatPawn& Boat,
                                const gis_unreal::FHUDLayout& Layout, UFont* Font)
{
    const double S = Layout.Scale;
    const auto& Rect = Layout.WindPanel;
    DrawRect(Brass, F(Rect.Left), F(Rect.Top), F(Rect.Width), F(Rect.Height));
    DrawRect(Ink, F(Rect.Left + 3*S), F(Rect.Top + 3*S),
             F(Rect.Width - 6*S), F(Rect.Height - 6*S));
    DrawText(TEXT("WIND  /  COMPASS"), PaleBrass,
             F(Rect.Left + 12*S), F(Rect.Top + 9*S), Font, F(1.04*S));

    const gis::State& State = Boat.GetBoatState();
    const gis::Input& Input = Boat.GetSailingInput();
    const gis::StepResult& Step = Boat.GetLastStep();
    const double Heading = gis_unreal::normalize_compass_degrees(
        450.0 - FMath::RadiansToDegrees(State.heading));
    const double TapeLeft = Rect.Left + 15*S;
    const double TapeTop = Rect.Top + 38*S;
    const double TapeWidth = Rect.Width - 30*S;
    const double TapeCenterX = TapeLeft + TapeWidth/2.0;
    DrawRect(DarkBrass, F(TapeLeft-3*S), F(TapeTop-3*S),
             F(TapeWidth+6*S), F(71*S));
    DrawRect(PaleBrass, F(TapeLeft-1*S), F(TapeTop-1*S),
             F(TapeWidth+2*S), F(67*S));
    DrawRect(FLinearColor(0.12f, 0.15f, 0.13f, 1.0f),
             F(TapeLeft), F(TapeTop), F(TapeWidth), F(65*S));
    DrawLine(F(TapeLeft), F(TapeTop + 64*S),
             F(TapeLeft + TapeWidth), F(TapeTop + 64*S), Brass, F(S));
    const auto Tape = gis_unreal::make_compass_tape(Heading, 1.95*S,
                                                   TapeWidth/2.0 - 9*S);
    for (const auto& Tick : Tape.Ticks)
    {
        const double X = TapeCenterX + Tick.OffsetPixels;
        DrawLine(F(X), F(TapeTop + (Tick.bMajor ? 38 : 46)*S),
                 F(X), F(TapeTop + 61*S),
                 Tick.bMajor ? PaleBrass : Brass, F((Tick.bMajor ? 1.4 : 0.8)*S));
        if (Tick.bMajor)
        {
            const FString Label = CompassLabel(Tick.BearingDegrees);
            DrawText(Label, Cream, F(X - (Label.Len() == 1 ? 4 : 10)*S),
                     F(TapeTop + 8*S), Font, F((Label.Len() == 1 ? 1.1 : 0.78)*S));
        }
    }
    DrawLine(F(TapeCenterX), F(TapeTop + 2*S), F(TapeCenterX),
             F(TapeTop + 63*S), FLinearColor(1.0f, 0.36f, 0.21f), F(2.2*S));
    DrawText(FString::Printf(TEXT("%03.0f DEG"), Tape.LubberBearingDegrees),
             PaleBrass, F(Rect.Left + 100*S), F(Rect.Top + 111*S), Font, F(0.97*S));

    // The wind pointer remains boat-relative as the boat turns. The compass
    // tape above shows absolute heading; it never changes the wind bearing.
    gis::Vec2 AirVelocityBoat = Step.apparent_wind_boat;
    if (State.time <= 0.0)
    {
        const double C = FMath::Cos(State.heading);
        const double Sn = FMath::Sin(State.heading);
        AirVelocityBoat = {
            C*Input.true_wind.x + Sn*Input.true_wind.y - State.u,
            -Sn*Input.true_wind.x + C*Input.true_wind.y - State.v,
        };
    }
    const gis_unreal::FBoatRelativeWindDisplay Wind =
        gis_unreal::make_apparent_wind_display(AirVelocityBoat);
    const double CenterX = Rect.Left + 78*S;
    const double CenterY = Rect.Top + 186*S;
    const double Radius = 43*S;
    for (int32 Index = 0; Index < 32; ++Index)
    {
        const double A = 2.0*PI*Index/32.0;
        const double B = 2.0*PI*(Index+1)/32.0;
        DrawLine(F(CenterX + 49*S*FMath::Cos(A)),
                 F(CenterY + 49*S*FMath::Sin(A)),
                 F(CenterX + 49*S*FMath::Cos(B)),
                 F(CenterY + 49*S*FMath::Sin(B)), DarkBrass, F(3*S));
        DrawLine(F(CenterX + 46*S*FMath::Cos(A)),
                 F(CenterY + 46*S*FMath::Sin(A)),
                 F(CenterX + 46*S*FMath::Cos(B)),
                 F(CenterY + 46*S*FMath::Sin(B)), PaleBrass, F(2*S));
        DrawLine(F(CenterX + Radius*FMath::Cos(A)),
                 F(CenterY + Radius*FMath::Sin(A)),
                 F(CenterX + Radius*FMath::Cos(B)),
                 F(CenterY + Radius*FMath::Sin(B)), Brass, F(1.4*S));
    }
    for (int32 Index = 0; Index < 12; ++Index)
    {
        const double A = 2.0*PI*Index/12.0;
        DrawLine(F(CenterX + 37*S*FMath::Cos(A)),
                 F(CenterY + 37*S*FMath::Sin(A)),
                 F(CenterX + 42*S*FMath::Cos(A)),
                 F(CenterY + 42*S*FMath::Sin(A)), PaleBrass, F(S));
    }
    DrawLine(F(CenterX), F(CenterY-Radius+4*S),
             F(CenterX), F(CenterY+Radius-4*S), Muted, F(0.7*S));
    DrawLine(F(CenterX-Radius+4*S), F(CenterY),
             F(CenterX+Radius-4*S), F(CenterY), Muted, F(0.7*S));
    DrawText(TEXT("BOW"), PaleBrass, F(CenterX-14*S),
             F(CenterY-Radius-20*S), Font, F(0.78*S));
    DrawText(TEXT("P"), Cream, F(CenterX-Radius-14*S),
             F(CenterY-7*S), Font, F(0.84*S));
    DrawText(TEXT("S"), Cream, F(CenterX+Radius+5*S),
             F(CenterY-7*S), Font, F(0.84*S));
    if (Wind.bValid)
    {
        const double X = Wind.ScreenX;
        const double Y = Wind.ScreenY;
        const double TipX = CenterX + Radius*0.88*X;
        const double TipY = CenterY + Radius*0.88*Y;
        DrawLine(F(CenterX), F(CenterY), F(TipX), F(TipY),
                 FLinearColor(1.0f, 0.34f, 0.20f), F(3.0*S));
        DrawLine(F(TipX), F(TipY), F(TipX-10*S*X-5*S*Y),
                 F(TipY-10*S*Y+5*S*X), PaleBrass, F(2*S));
        DrawLine(F(TipX), F(TipY), F(TipX-10*S*X+5*S*Y),
                 F(TipY-10*S*Y-5*S*X), PaleBrass, F(2*S));
    }
    DrawText(TEXT("APPARENT WIND FROM"), Muted,
             F(Rect.Left + 148*S), F(Rect.Top + 151*S), Font, F(0.87*S));
    DrawText(FString::Printf(TEXT("%.1f m/s"), Wind.SpeedMetresPerSecond),
             Cream, F(Rect.Left + 148*S), F(Rect.Top + 176*S), Font, F(1.22*S));
    const double Bearing = Wind.BearingDegreesStarboard;
    const TCHAR* Side = FMath::Abs(Bearing) < 0.5 ? TEXT("AHEAD")
        : FMath::Abs(FMath::Abs(Bearing)-180.0) < 0.5 ? TEXT("ASTERN")
        : Bearing > 0.0 ? TEXT("STBD") : TEXT("PORT");
    DrawText(Wind.bValid
                 ? FString::Printf(TEXT("%03.0f DEG %s"), FMath::Abs(Bearing), Side)
                 : TEXT("CALM"),
             PaleBrass, F(Rect.Left + 148*S), F(Rect.Top + 202*S),
             Font, F(0.94*S));
}

void AGISHUD::DrawMapPanel(const AGISBoatPawn& Boat,
                          const gis_unreal::FHUDRect& Rect,
                          bool bExpanded, UFont* Font)
{
    const double S = gis_unreal::make_hud_layout(Canvas->ClipX, Canvas->ClipY).Scale;
    const double Inset = bExpanded ? 5*S : 3*S;
    const gis_unreal::FHUDRect Image = {
        Rect.Left + Inset, Rect.Top + Inset,
        Rect.Width - 2*Inset, Rect.Height - 2*Inset,
    };
    DrawRect(Brass, F(Rect.Left-2*S), F(Rect.Top-2*S),
             F(Rect.Width+4*S), F(Rect.Height+4*S));
    DrawRect(Ink, F(Rect.Left), F(Rect.Top), F(Rect.Width), F(Rect.Height));
    const FGISMapData& Map = Boat.GetMapData();
    const bool bGreenwoodImage = GreenwoodMapTexture
        && Map.Name.Contains(TEXT("Lake Greenwood"));
    const gis::State& State = Boat.GetBoatState();
    const auto MiniCrop = gis_unreal::make_greenwood_minimap_view(
        State.x, State.y);
    gis_unreal::FMapProjection Projection;
    if (bGreenwoodImage)
    {
        const double U = bExpanded ? 0.0 : MiniCrop.MinU;
        const double V = bExpanded ? 0.0 : MiniCrop.MinV;
        const double UVSpan = bExpanded ? 1.0 : MiniCrop.MaxU - MiniCrop.MinU;
        DrawTexture(GreenwoodMapTexture, F(Image.Left), F(Image.Top),
                    F(Image.Width), F(Image.Height), F(U), F(V),
                    F(UVSpan), F(UVSpan),
                    FLinearColor(0.85f, 0.89f, 0.82f, 1.0f));
    }
    else
    {
        DrawRect(FLinearColor(0.09f, 0.19f, 0.19f, 1.0f),
                 F(Image.Left), F(Image.Top), F(Image.Width), F(Image.Height));
        Projection = gis_unreal::make_north_up_map_projection(
            {Map.BoundsMin.X, Map.BoundsMin.Y, Map.BoundsMax.X, Map.BoundsMax.Y},
            {Image.Left, Image.Top, Image.Width, Image.Height}, 12*S);
        if (Projection.bValid)
        {
            const int32 Count = Map.WaterPolygon.Num();
            const int32 Stride = FMath::Max(1, Count/440);
            if (Count >= 3)
            {
                auto Previous = Projection.Project(Map.WaterPolygon[0].X,
                                                   Map.WaterPolygon[0].Y);
                for (int32 Index = Stride; Index < Count; Index += Stride)
                {
                    const auto Next = Projection.Project(Map.WaterPolygon[Index].X,
                                                         Map.WaterPolygon[Index].Y);
                    DrawLine(F(Previous.X), F(Previous.Y), F(Next.X), F(Next.Y),
                             Muted, F(S));
                    Previous = Next;
                }
                const auto First = Projection.Project(Map.WaterPolygon[0].X,
                                                      Map.WaterPolygon[0].Y);
                DrawLine(F(Previous.X), F(Previous.Y), F(First.X), F(First.Y),
                         Muted, F(S));
            }
        }
    }
    const auto ToScreen = [&](double East, double North)
    {
        if (bGreenwoodImage)
        {
            const auto UV = bExpanded
                ? gis_unreal::greenwood_image_uv(East, North)
                : MiniCrop.WorldToLocal(East, North);
            return gis_unreal::FMapPoint{
                Image.Left + UV.X*Image.Width,
                Image.Top + UV.Y*Image.Height,
            };
        }
        return Projection.Project(East, North);
    };

    if (bGreenwoodImage && bExpanded && Map.WaterPolygon.Num() >= 3)
    {
        const int32 Count = Map.WaterPolygon.Num();
        const int32 Stride = FMath::Max(1, Count/1000);
        auto Previous = ToScreen(Map.WaterPolygon[0].X,
                                 Map.WaterPolygon[0].Y);
        for (int32 Index = Stride; Index < Count; Index += Stride)
        {
            const auto Next = ToScreen(Map.WaterPolygon[Index].X,
                                       Map.WaterPolygon[Index].Y);
            DrawLine(F(Previous.X), F(Previous.Y), F(Next.X), F(Next.Y),
                     PaleBrass, F(1.15*S));
            Previous = Next;
        }
        const auto First = ToScreen(Map.WaterPolygon[0].X,
                                    Map.WaterPolygon[0].Y);
        DrawLine(F(Previous.X), F(Previous.Y), F(First.X), F(First.Y),
                 PaleBrass, F(1.15*S));
    }

    if (bExpanded)
    {
        TArray<gis_unreal::FHUDRect> UsedLabels;
        const auto BoatPoint = ToScreen(State.x, State.y);
        UsedLabels.Add({BoatPoint.X-5*S, BoatPoint.Y-18*S, 114*S, 34*S});
        for (TActorIterator<AGISLandmarkScene> It(GetWorld()); It; ++It)
        {
            for (const FGISLandmarkMapMarker& Marker : It->MapMarkers)
            {
                const auto Point = ToScreen(Marker.EastNorthMetres.X,
                                            Marker.EastNorthMetres.Y);
                if (Point.X < Image.Left || Point.X > Image.Right()
                    || Point.Y < Image.Top || Point.Y > Image.Bottom())
                {
                    continue;
                }
                const bool bDam = Marker.Type.Contains(TEXT("dam"));
                const FLinearColor Pin = bDam
                    ? FLinearColor(1.0f, 0.46f, 0.30f)
                    : PaleBrass;
                DrawRect(Ink, F(Point.X-4*S), F(Point.Y-4*S), F(8*S), F(8*S));
                DrawRect(Pin, F(Point.X-2*S), F(Point.Y-2*S), F(4*S), F(4*S));
                if (Marker.Type.Contains(TEXT("major"))
                    || Marker.Type.Contains(TEXT("rail"))
                    || Marker.Name.Contains(TEXT("Spillway")))
                {
                    const FString Label = Marker.Name.Left(24);
                    const double LabelWidth = (8.0 + Label.Len()*5.5)*S;
                    const gis_unreal::FHUDRect LabelRect = {
                        FMath::Clamp(Point.X+6*S, Image.Left+3*S,
                                     Image.Right()-LabelWidth-3*S),
                        FMath::Clamp(Point.Y-8*S, Image.Top+43*S,
                                     Image.Bottom()-38*S),
                        LabelWidth, 15*S,
                    };
                    bool bOverlaps = false;
                    for (const auto& Used : UsedLabels)
                    {
                        if (LabelRect.Left < Used.Right()
                            && LabelRect.Right() > Used.Left
                            && LabelRect.Top < Used.Bottom()
                            && LabelRect.Bottom() > Used.Top)
                        {
                            bOverlaps = true;
                            break;
                        }
                    }
                    if (!bOverlaps)
                    {
                        DrawRect(Ink, F(LabelRect.Left), F(LabelRect.Top),
                                 F(LabelRect.Width), F(LabelRect.Height));
                        DrawText(Label, Cream, F(LabelRect.Left+3*S),
                                 F(LabelRect.Top+1*S), Font, F(0.74*S));
                        UsedLabels.Add(LabelRect);
                    }
                }
            }
            break;
        }
    }

    if (bGreenwoodImage || Projection.bValid)
    {
        const auto Point = ToScreen(State.x, State.y);
        if (Point.X >= Image.Left && Point.X <= Image.Right()
            && Point.Y >= Image.Top && Point.Y <= Image.Bottom())
        {
            const double Radius = (bExpanded ? 11.0 : 7.0)*S;
            for (int32 Index = 0; Index < 16; ++Index)
            {
                const double A = 2.0*PI*Index/16.0;
                const double B = 2.0*PI*(Index+1)/16.0;
                DrawLine(F(Point.X+Radius*FMath::Cos(A)),
                         F(Point.Y+Radius*FMath::Sin(A)),
                         F(Point.X+Radius*FMath::Cos(B)),
                         F(Point.Y+Radius*FMath::Sin(B)), Ink, F(2*S));
            }
            const auto Tip = gis_unreal::heading_tip(Point, State.heading, Radius);
            const auto LeftWing = gis_unreal::heading_tip(
                Point, State.heading + 2.45, Radius*0.68);
            const auto RightWing = gis_unreal::heading_tip(
                Point, State.heading - 2.45, Radius*0.68);
            DrawLine(F(Tip.X), F(Tip.Y), F(LeftWing.X), F(LeftWing.Y),
                     PaleBrass, F(2.5*S));
            DrawLine(F(Tip.X), F(Tip.Y), F(RightWing.X), F(RightWing.Y),
                     PaleBrass, F(2.5*S));
            DrawLine(F(LeftWing.X), F(LeftWing.Y), F(RightWing.X),
                     F(RightWing.Y), PaleBrass, F(2*S));
            if (bExpanded)
            {
                DrawRect(Ink, F(Point.X+13*S), F(Point.Y-14*S),
                         F(88*S), F(22*S));
                DrawText(TEXT("YOU ARE HERE"), Cream,
                         F(Point.X+17*S), F(Point.Y-10*S), Font, F(0.74*S));
            }
        }
    }

    const double HeaderHeight = bExpanded ? 39*S : 27*S;
    DrawRect(Ink, F(Image.Left), F(Image.Top), F(Image.Width), F(HeaderHeight));
    FString ShortMapName = Map.Name;
    int32 Comma = INDEX_NONE;
    if (ShortMapName.FindChar(TEXT(','), Comma))
    {
        ShortMapName = ShortMapName.Left(Comma);
    }
    const FString MapTitle = bExpanded
        ? ShortMapName.Left(22).ToUpper() + TEXT("  /  NORTH-UP CHART")
        : TEXT("LAKE MAP  -  CLICK / M");
    DrawText(MapTitle,
             PaleBrass, F(Image.Left+8*S), F(Image.Top+6*S),
             Font, F((bExpanded ? 1.02 : 0.84)*S));
    if (bExpanded)
    {
        const auto Layout = gis_unreal::make_hud_layout(Canvas->ClipX, Canvas->ClipY);
        DrawRect(Brass, F(Layout.ExpandedMapClose.Left),
                 F(Layout.ExpandedMapClose.Top),
                 F(Layout.ExpandedMapClose.Width),
                 F(Layout.ExpandedMapClose.Height));
        DrawRect(Ink, F(Layout.ExpandedMapClose.Left+S),
                 F(Layout.ExpandedMapClose.Top+S),
                 F(Layout.ExpandedMapClose.Width-2*S),
                 F(Layout.ExpandedMapClose.Height-2*S));
        DrawText(TEXT("X"), Cream, F(Layout.ExpandedMapClose.Left+12*S),
                 F(Layout.ExpandedMapClose.Top+5*S), Font, F(1.0*S));
        DrawRect(Ink, F(Image.Left+8*S), F(Image.Bottom()-28*S),
                 F(190*S), F(22*S));
        DrawText(TEXT("USGS / USDA AERIAL  -  N ↑"), Cream,
                 F(Image.Left+13*S), F(Image.Bottom()-25*S), Font, F(0.79*S));
        DrawRect(Ink, F(Image.Right()-165*S), F(Image.Bottom()-28*S),
                 F(157*S), F(22*S));
        DrawText(TEXT("NOT FOR NAVIGATION"), PaleBrass,
                 F(Image.Right()-159*S), F(Image.Bottom()-25*S),
                 Font, F(0.75*S));
    }
}

void AGISHUD::DrawPauseMenu(UFont* Font)
{
    const auto Layout = gis_unreal::make_menu_layout(Canvas->ClipX, Canvas->ClipY);
    const double S = Layout.Scale;
    DrawRect(FLinearColor(0.006f, 0.020f, 0.025f, 0.82f),
             0.0f, 0.0f, Canvas->ClipX, Canvas->ClipY);

    const auto DrawPanel = [&](const gis_unreal::FHUDRect& Rect)
    {
        DrawRect(Brass, F(Rect.Left), F(Rect.Top), F(Rect.Width), F(Rect.Height));
        DrawRect(FLinearColor(0.035f, 0.075f, 0.078f, 0.98f),
                 F(Rect.Left + 3*S), F(Rect.Top + 3*S),
                 F(Rect.Width - 6*S), F(Rect.Height - 6*S));
    };
    const auto DrawButton = [&](const gis_unreal::FHUDRect& Rect,
                                const FString& Label, bool bAccent)
    {
        DrawRect(bAccent ? PaleBrass : Brass, F(Rect.Left), F(Rect.Top),
                 F(Rect.Width), F(Rect.Height));
        DrawRect(bAccent
                     ? FLinearColor(0.14f, 0.25f, 0.23f, 1.0f)
                     : FLinearColor(0.075f, 0.13f, 0.14f, 1.0f),
                 F(Rect.Left + 2*S), F(Rect.Top + 2*S),
                 F(Rect.Width - 4*S), F(Rect.Height - 4*S));
        DrawText(Label, bAccent ? Cream : PaleBrass,
                 F(Rect.Left + 16*S), F(Rect.Top + 13*S), Font, F(1.20*S));
    };
    if (!bSettingsOpen)
    {
        DrawPanel(Layout.PausePanel);
        DrawText(TEXT("PAUSED"), Cream,
                 F(Layout.PausePanel.Left + 35*S),
                 F(Layout.PausePanel.Top + 22*S), Font, F(1.72*S));
        DrawText(TEXT("GOAT ISLAND SKIFF  /  LAKE GREENWOOD"), Muted,
                 F(Layout.PausePanel.Left + 35*S),
                 F(Layout.PausePanel.Top + 60*S), Font, F(0.82*S));
        DrawButton(Layout.Resume, TEXT("RESUME SAILING"), true);
        DrawButton(Layout.OpenSettings, TEXT("SETTINGS"), false);
        DrawButton(Layout.Quit, TEXT("QUIT TO DESKTOP"), false);
        DrawText(TEXT("ESC  RESUME"), Muted,
                 F(Layout.PausePanel.Left + 35*S),
                 F(Layout.PausePanel.Bottom() - 42*S), Font, F(0.82*S));
        return;
    }

    DrawPanel(Layout.SettingsPanel);
    DrawText(TEXT("SETTINGS"), Cream,
             F(Layout.SettingsPanel.Left + 28*S),
             F(Layout.SettingsPanel.Top + 21*S), Font, F(1.58*S));
    DrawText(TEXT("CHANGES SAVE AUTOMATICALLY"), Muted,
             F(Layout.SettingsPanel.Left + 29*S),
             F(Layout.SettingsPanel.Top + 61*S), Font, F(0.82*S));

    const auto DrawSetting = [&](const gis_unreal::FHUDRect& Row,
                                 const gis_unreal::FHUDRect& Previous,
                                 const gis_unreal::FHUDRect& Value,
                                 const gis_unreal::FHUDRect& Next,
                                 const FString& Label,
                                 const FString& CurrentValue)
    {
        DrawRect(FLinearColor(0.09f, 0.17f, 0.17f, 1.0f),
                 F(Row.Left), F(Row.Top), F(Row.Width), F(Row.Height));
        DrawText(Label, Cream, F(Row.Left + 14*S), F(Row.Top + 19*S),
                 Font, F(1.04*S));
        DrawRect(Brass, F(Previous.Left), F(Previous.Top),
                 F(Previous.Width), F(Previous.Height));
        DrawRect(Ink, F(Previous.Left + 2*S), F(Previous.Top + 2*S),
                 F(Previous.Width - 4*S), F(Previous.Height - 4*S));
        DrawText(TEXT("<"), PaleBrass, F(Previous.Left + 13*S),
                 F(Previous.Top + 9*S), Font, F(1.16*S));
        DrawRect(DarkBrass, F(Value.Left), F(Value.Top),
                 F(Value.Width), F(Value.Height));
        DrawRect(Ink, F(Value.Left + S), F(Value.Top + S),
                 F(Value.Width - 2*S), F(Value.Height - 2*S));
        DrawText(CurrentValue, Cream, F(Value.Left + 6*S),
                 F(Value.Top + 13*S), Font, F(0.91*S));
        DrawRect(Brass, F(Next.Left), F(Next.Top),
                 F(Next.Width), F(Next.Height));
        DrawRect(Ink, F(Next.Left + 2*S), F(Next.Top + 2*S),
                 F(Next.Width - 4*S), F(Next.Height - 4*S));
        DrawText(TEXT(">"), PaleBrass, F(Next.Left + 13*S),
                 F(Next.Top + 9*S), Font, F(1.16*S));
    };
    const TCHAR* QualityNames[] = {
        TEXT("LOW"), TEXT("MEDIUM"), TEXT("HIGH"),
        TEXT("EPIC"), TEXT("CINEMA")};
    const int32 Quality = FGISUserSettings::GetGraphicsQuality();
    const FString QualityName = Quality >= 0 && Quality <= 4
        ? QualityNames[Quality] : TEXT("CUSTOM");
    DrawSetting(Layout.GraphicsRow, Layout.GraphicsPrevious,
                Layout.GraphicsValue, Layout.GraphicsNext,
                TEXT("GRAPHICS QUALITY"), QualityName);
    DrawSetting(Layout.DisplayRow, Layout.DisplayPrevious,
                Layout.DisplayValue, Layout.DisplayNext,
                TEXT("DISPLAY MODE"),
                FGISUserSettings::IsFullscreen() ? TEXT("FULL") : TEXT("WINDOW"));
    DrawSetting(Layout.SensitivityRow, Layout.SensitivityPrevious,
                Layout.SensitivityValue, Layout.SensitivityNext,
                TEXT("HELM SENSITIVITY"),
                FString::Printf(TEXT("%.2fx"),
                    FGISUserSettings::GetHelmSensitivity()));
    DrawButton(Layout.Back, TEXT("BACK TO MENU"), false);
    DrawText(TEXT("ESC  BACK"), Muted,
             F(Layout.SettingsPanel.Left + 28*S),
             F(Layout.SettingsPanel.Bottom() - 27*S), Font, F(0.80*S));
}

void AGISHUD::DrawHUD()
{
    Super::DrawHUD();
    const APlayerController* Controller = GetOwningPlayerController();
    const AGISBoatPawn* Boat = Controller
        ? Cast<AGISBoatPawn>(Controller->GetPawn()) : nullptr;
    if (!Boat || !Canvas || !GEngine)
    {
        return;
    }
    UFont* Font = GEngine->GetSmallFont();
    const auto Layout = gis_unreal::make_hud_layout(Canvas->ClipX, Canvas->ClipY);
    DrawDataPanel(*Boat, Layout, Font);
    DrawWindInstrument(*Boat, Layout, Font);
    DrawMapPanel(*Boat, Layout.MiniMap, false, Font);

    const double S = Layout.Scale;
    DrawRect(Brass, F(Layout.MenuButton.Left), F(Layout.MenuButton.Top),
             F(Layout.MenuButton.Width), F(Layout.MenuButton.Height));
    DrawRect(Ink, F(Layout.MenuButton.Left + 2*S), F(Layout.MenuButton.Top + 2*S),
             F(Layout.MenuButton.Width - 4*S), F(Layout.MenuButton.Height - 4*S));
    DrawText(TEXT("MENU  /  ESC"), PaleBrass,
             F(Layout.MenuButton.Left + 10*S), F(Layout.MenuButton.Top + 7*S),
             Font, F(0.94*S));
    DrawRect(Ink, F(12*S), F(Canvas->ClipY-32*S), F(525*S), F(23*S));
    DrawText(TEXT("LMB drag tiller   Wheel trim   M map   Tab data   V view   ESC menu"),
             Muted, F(20*S), F(Canvas->ClipY-29*S), Font, F(0.83*S));
    if (Boat->GetBoatState().capsized)
    {
        DrawRect(FLinearColor(0.36f, 0.08f, 0.06f, 0.93f),
                 F(Canvas->ClipX/2-145*S), F(12*S), F(290*S), F(34*S));
        DrawText(TEXT("CAPSIZED  -  BACKSPACE TO RECOVER"), Cream,
                 F(Canvas->ClipX/2-138*S), F(18*S), Font, F(0.95*S));
    }
    if (bMapExpanded)
    {
        DrawRect(FLinearColor(0.008f, 0.023f, 0.025f, 0.79f),
                 0.0f, 0.0f, Canvas->ClipX, Canvas->ClipY);
        DrawMapPanel(*Boat, Layout.ExpandedMap, true, Font);
    }
    if (bMenuOpen)
    {
        DrawPauseMenu(Font);
    }
}
