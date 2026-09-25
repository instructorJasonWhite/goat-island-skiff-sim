#include "GISLandmarkScene.h"

#include "GISCoordinates.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
// Scenic heights and widths, NOT measured bridge clearances or dam sections.
constexpr double RoadDeckHeightM = 5.5;
constexpr double RailDeckHeightM = 5.0;
constexpr double DamCrestHeightM = 3.0;

struct FParsedLandmark
{
    FString Id;
    FString Name;
    FString Type;
    FString Component;
    FVector2D Point = FVector2D::ZeroVector;
    FVector2D SpanStart = FVector2D::ZeroVector;
    FVector2D SpanEnd = FVector2D::ZeroVector;
    double SpanLength = 0.0;
    double SpanBearing = 0.0;
    bool bHasSpan = false;
    bool bCourtesyDock = false;
};

bool ReadFinite(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, double& Out)
{
    return Object.IsValid() && Object->TryGetNumberField(Key, Out) && FMath::IsFinite(Out);
}

bool ReadPair(const TSharedPtr<FJsonValue>& Value, FVector2D& Out)
{
    if (!Value.IsValid() || Value->Type != EJson::Array)
    {
        return false;
    }
    const TArray<TSharedPtr<FJsonValue>>& Pair = Value->AsArray();
    double East = 0.0, North = 0.0;
    if (Pair.Num() != 2 || !Pair[0].IsValid() || !Pair[1].IsValid()
        || !Pair[0]->TryGetNumber(East) || !Pair[1]->TryGetNumber(North)
        || !FMath::IsFinite(East) || !FMath::IsFinite(North))
    {
        return false;
    }
    Out = FVector2D(East, North);
    return true;
}

FVector ToWorld(const FVector2D& EastNorth, double HeightMetres)
{
    return FVector(gis_unreal::east_metres_to_ue_x_cm(EastNorth.X),
                   gis_unreal::north_metres_to_ue_y_cm(EastNorth.Y),
                   HeightMetres * gis_unreal::CentimetresPerMetre);
}

UMaterialInstanceDynamic* Tinted(AActor* Owner, const FLinearColor& Color)
{
    UMaterialInterface* Base = LoadObject<UMaterialInterface>(
        nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    if (!Base)
    {
        return nullptr;
    }
    UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(Base, Owner);
    if (Material)
    {
        Material->SetVectorParameterValue(TEXT("Color"), Color);
    }
    return Material;
}

UHierarchicalInstancedStaticMeshComponent* NewLayer(
    AGISLandmarkScene* Owner, USceneComponent* Root, const TCHAR* Name,
    UStaticMesh* Mesh, UMaterialInterface* Material)
{
    UHierarchicalInstancedStaticMeshComponent* Layer =
        NewObject<UHierarchicalInstancedStaticMeshComponent>(Owner, FName(Name));
    Owner->AddInstanceComponent(Layer);
    Layer->SetupAttachment(Root);
    // These layers are created when play starts, so they have no baked lightmaps.
    Layer->SetMobility(EComponentMobility::Movable);
    Layer->SetStaticMesh(Mesh);
    Layer->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Layer->SetCanEverAffectNavigation(false);
    if (Material)
    {
        Layer->SetMaterial(0, Material);
    }
    Layer->RegisterComponent();
    return Layer;
}

void AddBox(UHierarchicalInstancedStaticMeshComponent* Layer,
            const FVector2D& Center, double HeightM, double BearingDeg,
            double LengthM, double WidthM, double ThicknessM)
{
    if (!Layer || LengthM <= 0.0 || WidthM <= 0.0 || ThicknessM <= 0.0)
    {
        return;
    }
    const float Yaw = static_cast<float>(
        gis_unreal::compass_heading_deg_to_ue_yaw_deg(BearingDeg));
    Layer->AddInstance(FTransform(FRotator(0.0f, Yaw, 0.0f),
                                  ToWorld(Center, HeightM),
                                  FVector(LengthM, WidthM, ThicknessM)));
}

void AddPost(UHierarchicalInstancedStaticMeshComponent* Layer,
             const FVector2D& Center, double HeightM, double DiameterM)
{
    if (!Layer)
    {
        return;
    }
    Layer->AddInstance(FTransform(FRotator::ZeroRotator,
                                  ToWorld(Center, HeightM * 0.5),
                                  FVector(DiameterM, DiameterM, HeightM)));
}

FVector2D Along(double BearingDeg)
{
    const double Radians = FMath::DegreesToRadians(BearingDeg);
    return FVector2D(FMath::Sin(Radians), FMath::Cos(Radians));
}

FVector2D Side(double BearingDeg)
{
    const FVector2D Axis = Along(BearingDeg);
    return FVector2D(Axis.Y, -Axis.X);
}

void AddRoadBridge(const FParsedLandmark& Feature,
                   UHierarchicalInstancedStaticMeshComponent* Deck,
                   UHierarchicalInstancedStaticMeshComponent* Rails,
                   UHierarchicalInstancedStaticMeshComponent* Piers)
{
    if (!Feature.bHasSpan)
    {
        return;
    }
    const FVector2D Center = (Feature.SpanStart + Feature.SpanEnd) * 0.5;
    const double Length = Feature.SpanLength + 10.0; // scenic bank overlap
    const double Width = Feature.Type == TEXT("major-road-bridge") ? 12.0 : 8.0;
    const FVector2D Lateral = Side(Feature.SpanBearing);
    const FVector2D Axis = Along(Feature.SpanBearing);
    AddBox(Deck, Center, RoadDeckHeightM, Feature.SpanBearing,
           Length, Width, 0.55);
    for (const double Sign : {-1.0, 1.0})
    {
        AddBox(Rails, Center + Lateral * (Sign * (Width * 0.5 - 0.25)),
               RoadDeckHeightM + 0.7, Feature.SpanBearing,
               Length, 0.25, 0.9);
    }
    const int32 PierCount = FMath::Max(0, FMath::FloorToInt(Feature.SpanLength / 35.0) - 1);
    for (int32 Index = 1; Index <= PierCount; ++Index)
    {
        const double Offset = -Feature.SpanLength * 0.5
            + Feature.SpanLength * Index / (PierCount + 1);
        AddPost(Piers, Center + Axis * Offset, RoadDeckHeightM - 0.35, 1.8);
    }
}

void AddRailBridge(const FParsedLandmark& Feature,
                   UHierarchicalInstancedStaticMeshComponent* Deck,
                   UHierarchicalInstancedStaticMeshComponent* Rails,
                   UHierarchicalInstancedStaticMeshComponent* Ties,
                   UHierarchicalInstancedStaticMeshComponent* Piers)
{
    if (!Feature.bHasSpan)
    {
        return;
    }
    const FVector2D Center = (Feature.SpanStart + Feature.SpanEnd) * 0.5;
    const double Length = Feature.SpanLength + 8.0;
    const FVector2D Axis = Along(Feature.SpanBearing);
    const FVector2D Lateral = Side(Feature.SpanBearing);
    AddBox(Deck, Center, RailDeckHeightM, Feature.SpanBearing,
           Length, 4.5, 0.55);
    for (const double Sign : {-1.0, 1.0})
    {
        AddBox(Rails, Center + Lateral * (Sign * 0.72),
               RailDeckHeightM + 0.45, Feature.SpanBearing,
               Length, 0.16, 0.18);
    }
    const int32 TieCount = FMath::Clamp(FMath::FloorToInt(Length / 1.8), 4, 350);
    for (int32 Index = 0; Index <= TieCount; ++Index)
    {
        const double Offset = -Length * 0.5 + Length * Index / TieCount;
        AddBox(Ties, Center + Axis * Offset, RailDeckHeightM + 0.35,
               Feature.SpanBearing + 90.0, 2.7, 0.22, 0.16);
    }
    const int32 PierCount = FMath::Max(0, FMath::FloorToInt(Feature.SpanLength / 28.0) - 1);
    for (int32 Index = 1; Index <= PierCount; ++Index)
    {
        const double Offset = -Feature.SpanLength * 0.5
            + Feature.SpanLength * Index / (PierCount + 1);
        AddPost(Piers, Center + Axis * Offset, RailDeckHeightM - 0.35, 1.3);
    }
}

} // namespace

AGISLandmarkScene::AGISLandmarkScene()
{
    PrimaryActorTick.bCanEverTick = false;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("LandmarkRoot"));
    SceneRoot->SetMobility(EComponentMobility::Movable);
    SetRootComponent(SceneRoot);
}

bool AGISLandmarkScene::LoadLandmarksFromFile(const FString& FilePath)
{
    if (!VisualLayers.IsEmpty())
    {
        UE_LOG(LogTemp, Warning, TEXT("GIS landmarks already loaded; ignoring duplicate call."));
        return false;
    }

    FString JsonText;
    if (!FFileHelper::LoadFileToString(JsonText, *FilePath))
    {
        UE_LOG(LogTemp, Warning, TEXT("GIS landmarks file missing: %s"), *FilePath);
        return false;
    }
    TSharedPtr<FJsonObject> Root;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root)
        || !Root.IsValid())
    {
        UE_LOG(LogTemp, Warning, TEXT("GIS landmarks JSON is invalid: %s"), *FilePath);
        return false;
    }
    FString MapId;
    bool bNavigationalUse = true;
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!Root->TryGetStringField(TEXT("map_id"), MapId)
        || MapId != TEXT("lake_greenwood_south_carolina")
        || !Root->TryGetBoolField(TEXT("navigational_use"), bNavigationalUse)
        || bNavigationalUse
        || !Root->TryGetArrayField(TEXT("features"), Values))
    {
        UE_LOG(LogTemp, Warning, TEXT("GIS landmark catalog has wrong map ID or schema."));
        return false;
    }

    TArray<FParsedLandmark> Parsed;
    for (const TSharedPtr<FJsonValue>& Value : *Values)
    {
        const TSharedPtr<FJsonObject> Item = Value.IsValid() ? Value->AsObject() : nullptr;
        FParsedLandmark Feature;
        if (!Item.IsValid()
            || !Item->TryGetStringField(TEXT("id"), Feature.Id)
            || !Item->TryGetStringField(TEXT("name"), Feature.Name)
            || !Item->TryGetStringField(TEXT("type"), Feature.Type)
            || Feature.Id.IsEmpty() || Feature.Name.IsEmpty())
        {
            UE_LOG(LogTemp, Warning, TEXT("GIS landmark catalog has an unnamed feature."));
            return false;
        }
        double East = 0.0, North = 0.0;
        if (!ReadFinite(Item, TEXT("east_m"), East)
            || !ReadFinite(Item, TEXT("north_m"), North)
            || FMath::Abs(East) > 20000.0 || FMath::Abs(North) > 20000.0)
        {
            UE_LOG(LogTemp, Warning, TEXT("GIS landmark %s has invalid coordinates."), *Feature.Id);
            return false;
        }
        Feature.Point = FVector2D(East, North);
        Item->TryGetStringField(TEXT("component"), Feature.Component);
        const TArray<TSharedPtr<FJsonValue>>* AmenityValues = nullptr;
        if (Item->TryGetArrayField(TEXT("amenities"), AmenityValues))
        {
            for (const TSharedPtr<FJsonValue>& Amenity : *AmenityValues)
            {
                if (Amenity.IsValid() && Amenity->AsString() == TEXT("courtesy_dock"))
                {
                    Feature.bCourtesyDock = true;
                }
            }
        }
        const TArray<TSharedPtr<FJsonValue>>* SpanPoints = nullptr;
        if (Item->TryGetArrayField(TEXT("span_endpoints_m"), SpanPoints)
            && SpanPoints->Num() == 2
            && ReadPair((*SpanPoints)[0], Feature.SpanStart)
            && ReadPair((*SpanPoints)[1], Feature.SpanEnd)
            && ReadFinite(Item, TEXT("span_length_m"), Feature.SpanLength)
            && ReadFinite(Item, TEXT("span_bearing_deg"), Feature.SpanBearing)
            && Feature.SpanLength >= 10.0 && Feature.SpanLength <= 1500.0)
        {
            Feature.bHasSpan = true;
        }
        if ((Feature.Type == TEXT("major-road-bridge")
             || Feature.Type == TEXT("road-bridge")
             || Feature.Type == TEXT("rail-crossing")) && !Feature.bHasSpan)
        {
            UE_LOG(LogTemp, Warning, TEXT("GIS landmark %s lacks a mapped span."), *Feature.Id);
            return false;
        }
        Parsed.Add(MoveTemp(Feature));
    }
    if (Parsed.IsEmpty())
    {
        return false;
    }

    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    UStaticMesh* Cylinder = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    if (!Cube || !Cylinder)
    {
        UE_LOG(LogTemp, Warning, TEXT("GIS landmarks could not load engine primitive meshes."));
        return false;
    }
    auto Layer = [this](const TCHAR* Name, UStaticMesh* Mesh, const FLinearColor& Color)
    {
        UHierarchicalInstancedStaticMeshComponent* Result =
            NewLayer(this, SceneRoot, Name, Mesh, Tinted(this, Color));
        VisualLayers.Add(Result);
        return Result;
    };
    auto* RoadDeck = Layer(TEXT("RoadBridgeDecks"), Cube, FLinearColor(0.28f, 0.30f, 0.31f));
    auto* RoadRails = Layer(TEXT("RoadBridgeGuardrails"), Cube, FLinearColor(0.67f, 0.68f, 0.66f));
    auto* RoadPiers = Layer(TEXT("RoadBridgePiers"), Cylinder, FLinearColor(0.52f, 0.53f, 0.50f));
    auto* RailDeck = Layer(TEXT("RailBridgeDecks"), Cube, FLinearColor(0.28f, 0.24f, 0.20f));
    auto* RailRails = Layer(TEXT("RailBridgeRails"), Cube, FLinearColor(0.23f, 0.26f, 0.27f));
    auto* RailTies = Layer(TEXT("RailBridgeTies"), Cube, FLinearColor(0.36f, 0.23f, 0.13f));
    auto* RailPiers = Layer(TEXT("RailBridgePiers"), Cylinder, FLinearColor(0.29f, 0.30f, 0.28f));
    auto* Dam = Layer(TEXT("DamCrestAndComponents"), Cube, FLinearColor(0.48f, 0.48f, 0.44f));
    auto* Ramp = Layer(TEXT("PublicLaunchRamps"), Cube, FLinearColor(0.57f, 0.54f, 0.46f));
    auto* Dock = Layer(TEXT("CourtesyDock"), Cube, FLinearColor(0.44f, 0.28f, 0.15f));
    auto* DockPosts = Layer(TEXT("CourtesyDockPosts"), Cylinder, FLinearColor(0.35f, 0.22f, 0.12f));

    TMap<FString, FVector2D> DamComponents;
    for (const FParsedLandmark& Feature : Parsed)
    {
        FGISLandmarkMapMarker Marker;
        Marker.Id = Feature.Id;
        Marker.Name = Feature.Name;
        Marker.Type = Feature.Type;
        Marker.EastNorthMetres = Feature.Point;
        Marker.WorldCentimetres = ToWorld(Feature.Point, 0.0);
        Marker.bApproximateStructureGeometry = true;
        MapMarkers.Add(MoveTemp(Marker));

        if (Feature.Type == TEXT("major-road-bridge") || Feature.Type == TEXT("road-bridge"))
        {
            AddRoadBridge(Feature, RoadDeck, RoadRails, RoadPiers);
        }
        else if (Feature.Type == TEXT("rail-crossing"))
        {
            AddRailBridge(Feature, RailDeck, RailRails, RailTies, RailPiers);
        }
        else if (Feature.Type == TEXT("dam-component"))
        {
            DamComponents.Add(Feature.Component, Feature.Point);
            AddBox(Dam, Feature.Point, DamCrestHeightM * 0.5,
                   90.0, Feature.Component == TEXT("spillway") ? 75.0 : 35.0,
                   18.0, DamCrestHeightM);
        }
        else if (Feature.Type == TEXT("public-ramp"))
        {
            // The source locates a facility, not its ramp/dock footprint.
            AddBox(Ramp, Feature.Point, 0.08, 90.0, 12.0, 5.0, 0.16);
            if (Feature.bCourtesyDock)
            {
                AddBox(Dock, Feature.Point + FVector2D(8.0, 0.0),
                       0.45, 90.0, 15.0, 3.0, 0.35);
                AddPost(DockPosts, Feature.Point + FVector2D(3.0, -1.2), 1.0, 0.25);
                AddPost(DockPosts, Feature.Point + FVector2D(13.0, 1.2), 1.0, 0.25);
            }
        }

        if (bShowWorldLabels)
        {
            UTextRenderComponent* Label = NewObject<UTextRenderComponent>(this);
            AddInstanceComponent(Label);
            Label->SetupAttachment(SceneRoot);
            Label->SetMobility(EComponentMobility::Movable);
            Label->SetText(FText::FromString(Feature.Name));
            Label->SetHorizontalAlignment(EHTA_Center);
            Label->SetWorldSize(75.0f);
            Label->SetTextRenderColor(FColor(252, 228, 172));
            Label->SetCollisionEnabled(ECollisionEnabled::NoCollision);
            Label->SetRelativeLocation(ToWorld(Feature.Point, 9.0));
            Label->RegisterComponent();
        }
    }
    // NID gives component centres, not a surveyed crest. These connecting
    // blocks are intentionally scenic and have no collision or boat hazard.
    auto ConnectDam = [Dam, &DamComponents](const TCHAR* Start, const TCHAR* End)
    {
        const FVector2D* A = DamComponents.Find(FString(Start));
        const FVector2D* B = DamComponents.Find(FString(End));
        if (!A || !B)
        {
            return;
        }
        const FVector2D Delta = *B - *A;
        const double Bearing = FMath::RadiansToDegrees(FMath::Atan2(Delta.X, Delta.Y));
        AddBox(Dam, (*A + *B) * 0.5, DamCrestHeightM * 0.5,
               Bearing, Delta.Size(), 12.0, DamCrestHeightM);
    };
    ConnectDam(TEXT("fuse-plug"), TEXT("embankment"));
    ConnectDam(TEXT("embankment"), TEXT("spillway"));

    UE_LOG(LogTemp, Log, TEXT("GIS landmarks: %d sourced markers, approximate visual structures; no collision/clearance data."),
           MapMarkers.Num());
    return true;
}
