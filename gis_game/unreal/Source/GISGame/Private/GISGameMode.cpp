#include "GISGameMode.h"

#include "GISBoatPawn.h"
#include "GISCoordinates.h"
#include "GISHUD.h"
#include "GISLandmarkScene.h"
#include "GISPlayerController.h"
#include "GISTerrainActor.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/Controller.h"
#include "GameFramework/PlayerStart.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/Paths.h"

namespace
{
constexpr double ShorelineVisualToleranceMetres = 8.0;
constexpr double WaterTileMetres = 30.0;
constexpr int32 BoundarySubdivisions = 3;
constexpr double BoundaryTileMetres = WaterTileMetres / BoundarySubdivisions;

UMaterialInstanceDynamic* TintedMaterial(UObject* Owner, const FLinearColor& Color)
{
    UMaterialInterface* Base = LoadObject<UMaterialInterface>(
        nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    if (!Base)
    {
        return nullptr;
    }
    UMaterialInstanceDynamic* Dynamic = UMaterialInstanceDynamic::Create(Base, Owner);
    Dynamic->SetVectorParameterValue(TEXT("Color"), Color);
    return Dynamic;
}

UInstancedStaticMeshComponent* MakeLayer(AActor* Owner, USceneComponent* Root,
                                         const TCHAR* Name, UStaticMesh* Mesh,
                                         UMaterialInterface* Material)
{
    UInstancedStaticMeshComponent* Layer =
        NewObject<UHierarchicalInstancedStaticMeshComponent>(Owner, FName(Name));
    Owner->AddInstanceComponent(Layer);
    Layer->SetupAttachment(Root);
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

double DistanceToSegmentSquared(const FVector2D& Point, const FVector2D& A,
                                const FVector2D& B)
{
    const FVector2D Edge = B - A;
    const double LengthSquared = Edge.SizeSquared();
    const double T = LengthSquared > 0.0
        ? FMath::Clamp(FVector2D::DotProduct(Point - A, Edge) / LengthSquared, 0.0, 1.0)
        : 0.0;
    return FVector2D::DistSquared(Point, A + Edge * T);
}

// Ramer-Douglas-Peucker on both arcs of a closed ring. This only changes
// drawn shore markers; FGISMapData retains every vertex for sailing limits.
TArray<FVector2D> SimplifyVisualRing(const TArray<FVector2D>& Source)
{
    int32 Count = Source.Num();
    if (Count > 1 && Source[0].Equals(Source[Count - 1], 0.01))
    {
        --Count;
    }
    if (Count < 4)
    {
        return Source;
    }

    int32 Opposite = 1;
    double Farthest = 0.0;
    for (int32 Index = 1; Index < Count; ++Index)
    {
        const double Distance = FVector2D::DistSquared(Source[0], Source[Index]);
        if (Distance > Farthest)
        {
            Farthest = Distance;
            Opposite = Index;
        }
    }

    TArray<uint8> Keep;
    Keep.Init(0, Count);
    Keep[0] = 1;
    Keep[Opposite] = 1;
    TArray<FIntPoint> Ranges;
    Ranges.Add(FIntPoint(0, Opposite));
    Ranges.Add(FIntPoint(Opposite, Count));
    const double ToleranceSquared = FMath::Square(ShorelineVisualToleranceMetres);
    while (!Ranges.IsEmpty())
    {
        const FIntPoint Range = Ranges.Pop();
        const FVector2D& A = Source[Range.X];
        const FVector2D& B = Source[Range.Y == Count ? 0 : Range.Y];
        int32 FarthestIndex = INDEX_NONE;
        double MaximumDistance = ToleranceSquared;
        for (int32 Index = Range.X + 1; Index < Range.Y; ++Index)
        {
            const double Distance = DistanceToSegmentSquared(Source[Index], A, B);
            if (Distance > MaximumDistance)
            {
                MaximumDistance = Distance;
                FarthestIndex = Index;
            }
        }
        if (FarthestIndex != INDEX_NONE)
        {
            Keep[FarthestIndex] = 1;
            Ranges.Add(FIntPoint(Range.X, FarthestIndex));
            Ranges.Add(FIntPoint(FarthestIndex, Range.Y));
        }
    }

    TArray<FVector2D> Simplified;
    for (int32 Index = 0; Index < Count; ++Index)
    {
        if (Keep[Index])
        {
            Simplified.Add(Source[Index]);
        }
    }
    return Simplified.Num() >= 3 ? Simplified : Source;
}

void AppendShoreline(const TArray<FVector2D>& Polygon, TArray<FTransform>& Out)
{
    const TArray<FVector2D> VisualRing = SimplifyVisualRing(Polygon);
    for (int32 Index = 0; Index < VisualRing.Num(); ++Index)
    {
        const FVector2D& A = VisualRing[Index];
        const FVector2D& B = VisualRing[(Index + 1) % VisualRing.Num()];
        const FVector2D Difference = B - A;
        const double SegmentMetres = Difference.Size();
        if (SegmentMetres < 1.0)
        {
            continue;
        }
        const FVector2D Midpoint = (A + B) * 0.5;
        const float Yaw = static_cast<float>(
            gis_unreal::east_north_segment_to_ue_yaw_deg(Difference.X, Difference.Y));
        Out.Add(FTransform(FRotator(0.0f, Yaw, 0.0f),
            FVector(gis_unreal::east_metres_to_ue_x_cm(Midpoint.X),
                    gis_unreal::north_metres_to_ue_y_cm(Midpoint.Y), 22.0),
            FVector(SegmentMetres, 4.0, 0.45)));
    }
}

void AppendScanlineCrossings(const TArray<FVector2D>& Polygon, double Y,
                             TArray<double>& Out)
{
    for (int32 Index = 0; Index < Polygon.Num(); ++Index)
    {
        const FVector2D& A = Polygon[Index];
        const FVector2D& B = Polygon[(Index + 1) % Polygon.Num()];
        // Half-open endpoints count a vertex once, including at horizontal edges.
        if ((A.Y <= Y && B.Y > Y) || (B.Y <= Y && A.Y > Y))
        {
            Out.Add(A.X + (Y - A.Y) * (B.X - A.X) / (B.Y - A.Y));
        }
    }
}

bool InsideCrossings(const TArray<double>& Sorted, double X)
{
    int32 Low = 0;
    int32 High = Sorted.Num();
    while (Low < High)
    {
        const int32 Middle = Low + (High - Low) / 2;
        if (Sorted[Middle] <= X)
        {
            Low = Middle + 1;
        }
        else
        {
            High = Middle;
        }
    }
    return (Low & 1) != 0;
}

bool SegmentTouchesCell(const FVector2D& A, const FVector2D& B,
                        int32 Column, int32 Row, double CellMetres)
{
    // Liang-Barsky clipping catches shorelines that cross a tile even when
    // the tile centre lies on land (or inside a small island).
    const double MinX = static_cast<double>(Column) * CellMetres;
    const double MaxX = MinX + CellMetres;
    const double MinY = static_cast<double>(Row) * CellMetres;
    const double MaxY = MinY + CellMetres;
    const double Dx = B.X - A.X;
    const double Dy = B.Y - A.Y;
    double Enter = 0.0;
    double Leave = 1.0;
    auto Clip = [&Enter, &Leave](double P, double Q)
    {
        if (FMath::Abs(P) < 1.0e-12)
        {
            return Q >= 0.0;
        }
        const double T = Q / P;
        if (P < 0.0)
        {
            if (T > Leave) return false;
            Enter = FMath::Max(Enter, T);
        }
        else
        {
            if (T < Enter) return false;
            Leave = FMath::Min(Leave, T);
        }
        return true;
    };
    return Clip(-Dx, A.X - MinX) && Clip(Dx, MaxX - A.X)
        && Clip(-Dy, A.Y - MinY) && Clip(Dy, MaxY - A.Y);
}

void AppendEdgeCells(const TArray<FVector2D>& Polygon, double CellMetres,
                     TSet<FIntPoint>& Out)
{
    constexpr double EdgeEpsilonMetres = 1.0e-6;
    for (int32 Index = 0; Index < Polygon.Num(); ++Index)
    {
        const FVector2D& A = Polygon[Index];
        const FVector2D& B = Polygon[(Index + 1) % Polygon.Num()];
        const int32 MinColumn = FMath::FloorToInt(
            (FMath::Min(A.X, B.X) - EdgeEpsilonMetres) / CellMetres);
        const int32 MaxColumn = FMath::FloorToInt(
            (FMath::Max(A.X, B.X) + EdgeEpsilonMetres) / CellMetres);
        const int32 MinRow = FMath::FloorToInt(
            (FMath::Min(A.Y, B.Y) - EdgeEpsilonMetres) / CellMetres);
        const int32 MaxRow = FMath::FloorToInt(
            (FMath::Max(A.Y, B.Y) + EdgeEpsilonMetres) / CellMetres);
        for (int32 Row = MinRow; Row <= MaxRow; ++Row)
        {
            for (int32 Column = MinColumn; Column <= MaxColumn; ++Column)
            {
                if (SegmentTouchesCell(A, B, Column, Row, CellMetres))
                {
                    Out.Add(FIntPoint(Column, Row));
                }
            }
        }
    }
}

bool ScanlineIsWater(const TArray<double>& Shore, const TArray<double>& Islands,
                     double X)
{
    return InsideCrossings(Shore, X) && !InsideCrossings(Islands, X);
}

void AddWaterTile(double X, double Y, double SizeMetres, TArray<FTransform>& Out)
{
    Out.Add(FTransform(FRotator::ZeroRotator,
        FVector(gis_unreal::east_metres_to_ue_x_cm(X),
                gis_unreal::north_metres_to_ue_y_cm(Y), -5.0),
        FVector(SizeMetres, SizeMetres, 1.0)));
}

void AppendWaterTiles(const FGISMapData& Map, TArray<FTransform>& Out)
{
    // Full-size interior tiles are cheap. Every 30 m cell touched by shore or
    // island edges is refined into 10 m cells. An edge-touching fine cell is
    // drawn even if its centre is land, closing narrow-cove visual gaps.
    // Sailing collision remains on the exact source polygons.
    TSet<FIntPoint> BoundaryCells;
    TSet<FIntPoint> FineEdgeCells;
    AppendEdgeCells(Map.WaterPolygon, WaterTileMetres, BoundaryCells);
    AppendEdgeCells(Map.WaterPolygon, BoundaryTileMetres, FineEdgeCells);
    for (const TArray<FVector2D>& Island : Map.Islands)
    {
        AppendEdgeCells(Island, WaterTileMetres, BoundaryCells);
        AppendEdgeCells(Island, BoundaryTileMetres, FineEdgeCells);
    }

    const int32 MinColumn = FMath::FloorToInt(Map.BoundsMin.X / WaterTileMetres);
    const int32 MaxColumn = FMath::CeilToInt(Map.BoundsMax.X / WaterTileMetres);
    const int32 MinRow = FMath::FloorToInt(Map.BoundsMin.Y / WaterTileMetres);
    const int32 MaxRow = FMath::CeilToInt(Map.BoundsMax.Y / WaterTileMetres);
    for (int32 Row = MinRow; Row < MaxRow; ++Row)
    {
        const double Y = (static_cast<double>(Row) + 0.5) * WaterTileMetres;
        TArray<double> ShoreCrossings;
        AppendScanlineCrossings(Map.WaterPolygon, Y, ShoreCrossings);
        ShoreCrossings.Sort();
        TArray<double> IslandCrossings;
        for (const TArray<FVector2D>& Island : Map.Islands)
        {
            AppendScanlineCrossings(Island, Y, IslandCrossings);
        }
        IslandCrossings.Sort();

        TArray<double> FineShore[BoundarySubdivisions];
        TArray<double> FineIslands[BoundarySubdivisions];
        for (int32 SubRow = 0; SubRow < BoundarySubdivisions; ++SubRow)
        {
            const double FineY = (static_cast<double>(Row * BoundarySubdivisions + SubRow)
                + 0.5) * BoundaryTileMetres;
            AppendScanlineCrossings(Map.WaterPolygon, FineY, FineShore[SubRow]);
            FineShore[SubRow].Sort();
            for (const TArray<FVector2D>& Island : Map.Islands)
            {
                AppendScanlineCrossings(Island, FineY, FineIslands[SubRow]);
            }
            FineIslands[SubRow].Sort();
        }

        for (int32 Column = MinColumn; Column < MaxColumn; ++Column)
        {
            const double X = (static_cast<double>(Column) + 0.5) * WaterTileMetres;
            if (!BoundaryCells.Contains(FIntPoint(Column, Row)))
            {
                if (ScanlineIsWater(ShoreCrossings, IslandCrossings, X))
                {
                    AddWaterTile(X, Y, WaterTileMetres, Out);
                }
                continue;
            }
            for (int32 SubRow = 0; SubRow < BoundarySubdivisions; ++SubRow)
            {
                const int32 FineRow = Row * BoundarySubdivisions + SubRow;
                const double FineY = (static_cast<double>(FineRow) + 0.5) * BoundaryTileMetres;
                for (int32 SubColumn = 0; SubColumn < BoundarySubdivisions; ++SubColumn)
                {
                    const int32 FineColumn = Column * BoundarySubdivisions + SubColumn;
                    const double FineX = (static_cast<double>(FineColumn) + 0.5) * BoundaryTileMetres;
                    if (ScanlineIsWater(FineShore[SubRow], FineIslands[SubRow], FineX)
                        || FineEdgeCells.Contains(FIntPoint(FineColumn, FineRow)))
                    {
                        AddWaterTile(FineX, FineY, BoundaryTileMetres, Out);
                    }
                }
            }
        }
    }
    UE_LOG(LogTemp, Log, TEXT("GIS water refinement: %d coarse shore cells, %d fine edge cells."),
           BoundaryCells.Num(), FineEdgeCells.Num());
}
} // namespace

AGISGameMode::AGISGameMode()
{
    DefaultPawnClass = AGISBoatPawn::StaticClass();
    PlayerControllerClass = AGISPlayerController::StaticClass();
    HUDClass = AGISHUD::StaticClass();
}

void AGISGameMode::InitGame(const FString& MapName, const FString& Options,
                            FString& ErrorMessage)
{
    Super::InitGame(MapName, Options, ErrorMessage);

    FString RequestedMap = UGameplayStatics::ParseOption(Options, TEXT("GISMap"));
    if (RequestedMap.IsEmpty())
    {
        RequestedMap = MapFileName;
    }
    bool bSafeFileName = !RequestedMap.IsEmpty()
        && RequestedMap == FPaths::GetCleanFilename(RequestedMap)
        && RequestedMap.EndsWith(TEXT(".json"), ESearchCase::IgnoreCase);
    for (int32 Index = 0; Index < RequestedMap.Len(); ++Index)
    {
        const TCHAR Character = RequestedMap[Index];
        if (!FChar::IsAlnum(Character) && Character != TEXT('_')
            && Character != TEXT('-') && Character != TEXT('.'))
        {
            bSafeFileName = false;
            break;
        }
    }
    if (RequestedMap.Contains(TEXT("..")))
    {
        bSafeFileName = false;
    }
    if (!bSafeFileName)
    {
        UE_LOG(LogTemp, Warning, TEXT("Invalid GISMap filename; using greenwood_usgs.json."));
        RequestedMap = TEXT("greenwood_usgs.json");
    }

    FString MapError;
    const FString StagedPath = FPaths::Combine(
        FPaths::ProjectContentDir(), TEXT("Data"), RequestedMap);
    const bool bMapLoaded = LakeMap.LoadFromFile(StagedPath, MapError);
    bUseGreenwoodTerrain = bMapLoaded
        && RequestedMap.Equals(TEXT("greenwood_usgs.json"), ESearchCase::IgnoreCase);
    if (!bMapLoaded)
    {
        UE_LOG(LogTemp, Warning, TEXT("%s; using small fallback water rectangle."), *MapError);
        LakeMap.Name = TEXT("Fallback training water");
        LakeMap.Description = TEXT("The shared Greenwood JSON could not be loaded.");
        LakeMap.BoundsMin = FVector2D(-500.0, -500.0);
        LakeMap.BoundsMax = FVector2D(500.0, 500.0);
        LakeMap.WaterPolygon = {
            FVector2D(-500.0, -500.0), FVector2D(500.0, -500.0),
            FVector2D(500.0, 500.0), FVector2D(-500.0, 500.0)};
        LakeMap.Islands.Reset();
        LakeMap.SpawnMetres = FVector2D::ZeroVector;
    }

    // Entry is intentionally blank; create the start before player login.
    if (GetWorld())
    {
        const float Heading = static_cast<float>(
            gis_unreal::compass_heading_deg_to_ue_yaw_deg(LakeMap.SpawnHeadingDegreesFromNorth));
        GetWorld()->SpawnActor<APlayerStart>(
            FVector(gis_unreal::east_metres_to_ue_x_cm(LakeMap.SpawnMetres.X),
                    gis_unreal::north_metres_to_ue_y_cm(LakeMap.SpawnMetres.Y), 28.0),
            FRotator(0.0f, Heading, 0.0f));
    }
}

void AGISGameMode::RestartPlayer(AController* NewPlayer)
{
    Super::RestartPlayer(NewPlayer);
    if (NewPlayer)
    {
        if (AGISBoatPawn* Boat = Cast<AGISBoatPawn>(NewPlayer->GetPawn()))
        {
            Boat->InitializeFromMap(LakeMap);
        }
    }
}

void AGISGameMode::BeginPlay()
{
    Super::BeginPlay();
    BuildLakeVisuals();
}

void AGISGameMode::BuildLakeVisuals()
{
    UStaticMesh* Plane = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Plane.Plane"));
    UStaticMesh* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!GetWorld() || !Plane || !Cube)
    {
        UE_LOG(LogTemp, Warning, TEXT("Could not create GIS lake visuals: engine meshes missing."));
        return;
    }

    bool bTerrainReady = false;
    if (bUseGreenwoodTerrain)
    {
        if (AGISTerrainActor* Terrain = GetWorld()->SpawnActor<AGISTerrainActor>())
        {
            bTerrainReady = Terrain->Initialize(LakeMap);
            if (!bTerrainReady)
            {
                Terrain->Destroy();
            }
        }
    }
    if (!bTerrainReady)
    {
        UMaterialInstanceDynamic* Water = TintedMaterial(this, FLinearColor(0.018f, 0.13f, 0.18f));
        UMaterialInstanceDynamic* Shore = TintedMaterial(this, FLinearColor(0.13f, 0.23f, 0.10f));
        UMaterialInstanceDynamic* Island = TintedMaterial(this, FLinearColor(0.17f, 0.28f, 0.12f));

        AActor* LakeVisuals = GetWorld()->SpawnActor<AActor>(FVector::ZeroVector, FRotator::ZeroRotator);
        if (!LakeVisuals)
        {
            return;
        }
        USceneComponent* VisualRoot = NewObject<USceneComponent>(LakeVisuals, TEXT("GISLakeVisualRoot"));
        LakeVisuals->AddInstanceComponent(VisualRoot);
        LakeVisuals->SetRootComponent(VisualRoot);
        VisualRoot->RegisterComponent();
        UInstancedStaticMeshComponent* WaterLayer = MakeLayer(
            LakeVisuals, VisualRoot, TEXT("GISWaterTiles"), Plane, Water);
        UInstancedStaticMeshComponent* ShoreLayer = MakeLayer(
            LakeVisuals, VisualRoot, TEXT("GISShoreMarkers"), Cube, Shore);
        UInstancedStaticMeshComponent* IslandLayer = MakeLayer(
            LakeVisuals, VisualRoot, TEXT("GISIslandMarkers"), Cube, Island);

        TArray<FTransform> WaterTiles;
        AppendWaterTiles(LakeMap, WaterTiles);
        WaterLayer->AddInstances(WaterTiles, false, false, false);

        TArray<FTransform> ShoreSegments;
        AppendShoreline(LakeMap.WaterPolygon, ShoreSegments);
        ShoreLayer->AddInstances(ShoreSegments, false, false, false);

        TArray<FTransform> IslandSegments;
        for (const TArray<FVector2D>& Polygon : LakeMap.Islands)
        {
            AppendShoreline(Polygon, IslandSegments);
        }
        IslandLayer->AddInstances(IslandSegments, false, false, false);
        UE_LOG(LogTemp, Log, TEXT("GIS fallback lake visuals: %d water tiles, %d shore segments, %d island segments."),
               WaterTiles.Num(), ShoreSegments.Num(), IslandSegments.Num());
    }

    if (bUseGreenwoodTerrain)
    {
        if (AGISLandmarkScene* Landmarks = GetWorld()->SpawnActor<AGISLandmarkScene>())
        {
            const FString LandmarksPath = FPaths::Combine(FPaths::ProjectContentDir(),
                TEXT("Data"), TEXT("greenwood_landmarks.json"));
            if (!Landmarks->LoadLandmarksFromFile(LandmarksPath))
            {
                Landmarks->Destroy();
            }
        }
    }

    if (ADirectionalLight* Sun = GetWorld()->SpawnActor<ADirectionalLight>(
            FVector::ZeroVector, FRotator(-48.0f, 25.0f, 0.0f)))
    {
        if (UDirectionalLightComponent* SunLight =
                Cast<UDirectionalLightComponent>(Sun->GetLightComponent()))
        {
            SunLight->SetMobility(EComponentMobility::Movable);
            SunLight->SetIntensity(8.0f);
            SunLight->SetAtmosphereSunLight(true);
        }
    }
    if (ASkyLight* Ambient = GetWorld()->SpawnActor<ASkyLight>())
    {
        Ambient->GetLightComponent()->SetMobility(EComponentMobility::Movable);
        Ambient->GetLightComponent()->SetIntensity(1.0f);
        Ambient->GetLightComponent()->RecaptureSky();
    }
}
