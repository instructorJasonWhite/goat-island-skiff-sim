#include "GISTerrainActor.h"

#include "GISMapData.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "ProceduralMeshComponent.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
constexpr TCHAR ManifestName[] = TEXT("greenwood_2017_s16m_manifest.json");
constexpr double WaterBedCentimetres = -200.0;

void AppendCrossings(const TArray<FVector2D>& Polygon, double NorthMetres,
                     TArray<double>& Crossings)
{
    for (int32 Index = 0; Index < Polygon.Num(); ++Index)
    {
        const FVector2D& A = Polygon[Index];
        const FVector2D& B = Polygon[(Index + 1) % Polygon.Num()];
        if ((A.Y <= NorthMetres && B.Y > NorthMetres)
            || (B.Y <= NorthMetres && A.Y > NorthMetres))
        {
            Crossings.Add(A.X + (NorthMetres - A.Y) * (B.X - A.X) / (B.Y - A.Y));
        }
    }
}

bool IsInsideCrossings(const TArray<double>& SortedCrossings, double EastMetres)
{
    int32 Low = 0;
    int32 High = SortedCrossings.Num();
    while (Low < High)
    {
        const int32 Middle = Low + (High - Low) / 2;
        if (SortedCrossings[Middle] <= EastMetres)
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
}

AGISTerrainActor::AGISTerrainActor()
{
    PrimaryActorTick.bCanEverTick = true;
    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("TerrainRoot"));
    SetRootComponent(SceneRoot);
}

bool AGISTerrainActor::LoadData(FString& OutError)
{
    const FString DataDir = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data"));
    FString JsonText;
    if (!FFileHelper::LoadFileToString(JsonText, *FPaths::Combine(DataDir, ManifestName)))
    {
        OutError = TEXT("Greenwood terrain manifest is missing from Content/Data.");
        return false;
    }

    TSharedPtr<FJsonObject> Manifest;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
    if (!FJsonSerializer::Deserialize(Reader, Manifest) || !Manifest.IsValid())
    {
        OutError = TEXT("Greenwood terrain manifest is invalid JSON.");
        return false;
    }

    double Width = 0.0;
    double Height = 0.0;
    double Zero = 0.0;
    double XMax = 0.0;
    double YMin = 0.0;
    double XMin = 0.0;
    double YMax = 0.0;
    double Spacing = 0.0;
    double CodeScale = 0.0;
    bool bNorthFirst = false;
    FString R16Name;
    if (!Manifest->TryGetNumberField(TEXT("width"), Width)
        || !Manifest->TryGetNumberField(TEXT("height"), Height)
        || !Manifest->TryGetNumberField(TEXT("x_min_m"), XMin)
        || !Manifest->TryGetNumberField(TEXT("x_max_m"), XMax)
        || !Manifest->TryGetNumberField(TEXT("y_min_m"), YMin)
        || !Manifest->TryGetNumberField(TEXT("y_max_m"), YMax)
        || !Manifest->TryGetNumberField(TEXT("sample_spacing_m"), Spacing)
        || !Manifest->TryGetNumberField(TEXT("r16_zero_code"), Zero)
        || !Manifest->TryGetNumberField(TEXT("r16_world_cm_per_code"), CodeScale)
        || !Manifest->TryGetBoolField(TEXT("row_0_is_north"), bNorthFirst)
        || !Manifest->TryGetStringField(TEXT("r16_file"), R16Name))
    {
        OutError = TEXT("Greenwood terrain manifest lacks required grid metadata.");
        return false;
    }

    if (Width != FMath::FloorToDouble(Width) || Height != FMath::FloorToDouble(Height)
        || Width < TileCells + 1 || Height < TileCells + 1
        || Width > 8193 || Height > 8193 || Spacing <= 0.0 || CodeScale <= 0.0
        || !bNorthFirst || R16Name != FPaths::GetCleanFilename(R16Name)
        || !R16Name.EndsWith(TEXT(".r16"), ESearchCase::IgnoreCase)
        || !FMath::IsNearlyEqual(XMax - XMin, (Width - 1.0) * Spacing, 0.01)
        || !FMath::IsNearlyEqual(YMax - YMin, (Height - 1.0) * Spacing, 0.01))
    {
        OutError = TEXT("Greenwood terrain grid dimensions, bounds, or orientation are inconsistent.");
        return false;
    }

    GridWidth = static_cast<int32>(Width);
    GridHeight = static_cast<int32>(Height);
    XMinMetres = XMin;
    YMaxMetres = YMax;
    SampleSpacingMetres = Spacing;
    ZeroCode = static_cast<int32>(Zero);
    CentimetresPerCode = CodeScale;

    TArray<uint8> Bytes;
    if (!FFileHelper::LoadFileToArray(Bytes, *FPaths::Combine(DataDir, R16Name))
        || static_cast<int64>(Bytes.Num()) != static_cast<int64>(GridWidth) * GridHeight * 2)
    {
        OutError = TEXT("Greenwood R16 file is missing or does not match its grid dimensions.");
        return false;
    }
    Heights.SetNumUninitialized(GridWidth * GridHeight);
    FMemory::Memcpy(Heights.GetData(), Bytes.GetData(), Bytes.Num());
    return true;
}

void AGISTerrainActor::BuildWaterMask(const FGISMapData& Map)
{
    WaterMask.Init(0, GridWidth * GridHeight);
    for (int32 Row = 0; Row < GridHeight; ++Row)
    {
        const double North = YMaxMetres - static_cast<double>(Row) * SampleSpacingMetres;
        TArray<double> ShoreCrossings;
        TArray<double> IslandCrossings;
        AppendCrossings(Map.WaterPolygon, North, ShoreCrossings);
        ShoreCrossings.Sort();
        for (const TArray<FVector2D>& Island : Map.Islands)
        {
            AppendCrossings(Island, North, IslandCrossings);
        }
        IslandCrossings.Sort();
        if (ShoreCrossings.IsEmpty())
        {
            continue;
        }
        for (int32 Column = 0; Column < GridWidth; ++Column)
        {
            const double East = XMinMetres + static_cast<double>(Column) * SampleSpacingMetres;
            WaterMask[Row * GridWidth + Column] =
                IsInsideCrossings(ShoreCrossings, East)
                && !IsInsideCrossings(IslandCrossings, East) ? 1 : 0;
        }
    }
}

double AGISTerrainActor::HeightCentimetres(int32 Row, int32 Column) const
{
    Row = FMath::Clamp(Row, 0, GridHeight - 1);
    Column = FMath::Clamp(Column, 0, GridWidth - 1);
    const int32 Index = Row * GridWidth + Column;
    const double Measured = (static_cast<int32>(Heights[Index]) - ZeroCode)
        * CentimetresPerCode;
    // 3DEP is hydroflattened at the water surface. A shallow visual bed makes
    // the existing accurate water polygon visible without implying bathymetry.
    return WaterMask[Index] ? FMath::Min(Measured, WaterBedCentimetres)
                            : FMath::Max(Measured, 20.0);
}

bool AGISTerrainActor::Initialize(const FGISMapData& Map)
{
    FString Error;
    if (!LoadData(Error))
    {
        UE_LOG(LogTemp, Warning, TEXT("GIS terrain: %s"), *Error);
        return false;
    }
    if (Map.BoundsMin.X < XMinMetres || Map.BoundsMax.X > XMinMetres + (GridWidth - 1) * SampleSpacingMetres
        || Map.BoundsMin.Y < YMaxMetres - (GridHeight - 1) * SampleSpacingMetres
        || Map.BoundsMax.Y > YMaxMetres)
    {
        UE_LOG(LogTemp, Warning, TEXT("GIS terrain does not cover this lake map."));
        return false;
    }

    BuildWaterMask(Map);
    UMaterialInterface* Base = LoadObject<UMaterialInterface>(
        nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    UMaterialInterface* AuthoredLand = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/Environment/M_GreenwoodNAIP.M_GreenwoodNAIP"));
    if (AuthoredLand)
    {
        LandMaterial = AuthoredLand;
    }
    else if (Base)
    {
        UMaterialInstanceDynamic* TintedLand = UMaterialInstanceDynamic::Create(Base, this);
        TintedLand->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.13f, 0.23f, 0.095f));
        LandMaterial = TintedLand;
    }
    UStaticMesh* PlaneAsset = LoadObject<UStaticMesh>(nullptr,
        TEXT("/Engine/BasicShapes/Plane.Plane"));
    if (!PlaneAsset)
    {
        UE_LOG(LogTemp, Warning, TEXT("GIS terrain water plane asset is unavailable."));
        return false;
    }
    WaterPlane = NewObject<UStaticMeshComponent>(this, TEXT("GISStreamedWater"));
    AddInstanceComponent(WaterPlane);
    WaterPlane->SetupAttachment(SceneRoot);
    WaterPlane->SetMobility(EComponentMobility::Movable);
    WaterPlane->SetStaticMesh(PlaneAsset);
    WaterPlane->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    WaterPlane->SetCanEverAffectNavigation(false);
    UMaterialInterface* AuthoredWater = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Game/Environment/M_GreenwoodWater.M_GreenwoodWater"));
    if (AuthoredWater)
    {
        WaterPlane->SetMaterial(0, AuthoredWater);
    }
    else if (Base)
    {
        UMaterialInstanceDynamic* WaterMaterial = UMaterialInstanceDynamic::Create(Base, WaterPlane);
        WaterMaterial->SetVectorParameterValue(TEXT("Color"), FLinearColor(0.018f, 0.13f, 0.18f));
        WaterPlane->SetMaterial(0, WaterMaterial);
    }
    WaterPlane->RegisterComponent();
    bReady = true;
    UpdateVisibleTiles(FVector(Map.SpawnMetres.X * 100.0,
                               -Map.SpawnMetres.Y * 100.0, 0.0));
    UE_LOG(LogTemp, Log, TEXT("GIS terrain: %dx%d measured vertices, %d visible tiles."),
           GridWidth, GridHeight, VisibleTiles.Num());
    return true;
}

UProceduralMeshComponent* AGISTerrainActor::CreateTile(int32 TileColumn,
                                                        int32 TileRow, int32 Step)
{
    const int32 StartColumn = TileColumn * TileCells;
    const int32 StartRow = TileRow * TileCells;
    const int32 CellsX = FMath::Min(TileCells, GridWidth - 1 - StartColumn);
    const int32 CellsY = FMath::Min(TileCells, GridHeight - 1 - StartRow);
    if (CellsX <= 0 || CellsY <= 0 || CellsX % Step != 0 || CellsY % Step != 0)
    {
        return nullptr;
    }

    const int32 QuadsX = CellsX / Step;
    const int32 QuadsY = CellsY / Step;
    const int32 VerticesPerRow = QuadsX + 1;
    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FColor> Colors;
    TArray<FProcMeshTangent> Tangents;
    Vertices.Reserve((QuadsX + 1) * (QuadsY + 1));
    Normals.Reserve(Vertices.GetSlack());
    UVs.Reserve(Vertices.GetSlack());
    Tangents.Reserve(Vertices.GetSlack());
    Triangles.Reserve(QuadsX * QuadsY * 6);

    const double VertexCm = SampleSpacingMetres * 100.0;
    for (int32 LocalRow = 0; LocalRow <= QuadsY; ++LocalRow)
    {
        for (int32 LocalColumn = 0; LocalColumn <= QuadsX; ++LocalColumn)
        {
            const int32 Row = StartRow + LocalRow * Step;
            const int32 Column = StartColumn + LocalColumn * Step;
            const double Z = HeightCentimetres(Row, Column);
            Vertices.Add(FVector(LocalColumn * Step * VertexCm,
                                 LocalRow * Step * VertexCm, Z));
            const double Dx = (HeightCentimetres(Row, Column + 1)
                               - HeightCentimetres(Row, Column - 1)) / (2.0 * VertexCm);
            const double Dy = (HeightCentimetres(Row + 1, Column)
                               - HeightCentimetres(Row - 1, Column)) / (2.0 * VertexCm);
            Normals.Add(FVector(-Dx, -Dy, 1.0).GetSafeNormal());
            // One north-up UV frame over the complete 3DEP square also aligns
            // tiled NAIP aerial imagery; streaming never resets the texture.
            UVs.Add(FVector2D(static_cast<double>(Column) / (GridWidth - 1),
                              static_cast<double>(Row) / (GridHeight - 1)));
            Tangents.Add(FProcMeshTangent(1.0f, 0.0f, 0.0f));
        }
    }
    for (int32 Row = 0; Row < QuadsY; ++Row)
    {
        for (int32 Column = 0; Column < QuadsX; ++Column)
        {
            const int32 NW = Row * VerticesPerRow + Column;
            const int32 NE = NW + 1;
            const int32 SW = NW + VerticesPerRow;
            const int32 SE = SW + 1;
            Triangles.Append({NW, NE, SE, NW, SE, SW});
        }
    }

    // A tile may leave and re-enter the visible ring before garbage collection.
    // Let Unreal assign a fresh object name rather than reusing the old one.
    UProceduralMeshComponent* Mesh = NewObject<UProceduralMeshComponent>(this);
    AddInstanceComponent(Mesh);
    Mesh->SetupAttachment(SceneRoot);
    Mesh->SetMobility(EComponentMobility::Movable);
    Mesh->SetRelativeLocation(FVector((XMinMetres + StartColumn * SampleSpacingMetres) * 100.0,
                                      (-YMaxMetres + StartRow * SampleSpacingMetres) * 100.0, 0.0));
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Mesh->SetCanEverAffectNavigation(false);
    Mesh->RegisterComponent();
    Mesh->CreateMeshSection(0, Vertices, Triangles, Normals, UVs, Colors, Tangents, false);
    if (LandMaterial)
    {
        Mesh->SetMaterial(0, LandMaterial);
    }
    return Mesh;
}

void AGISTerrainActor::UpdateVisibleTiles(const FVector& BoatWorldLocation)
{
    if (!bReady)
    {
        return;
    }
    const double East = BoatWorldLocation.X / 100.0;
    const double South = BoatWorldLocation.Y / 100.0;
    const double TileMetres = TileCells * SampleSpacingMetres;
    const int32 MaxTileColumn = FMath::DivideAndRoundUp(GridWidth - 1, TileCells) - 1;
    const int32 MaxTileRow = FMath::DivideAndRoundUp(GridHeight - 1, TileCells) - 1;
    const FIntPoint BoatTile(
        FMath::Clamp(FMath::FloorToInt((East - XMinMetres) / TileMetres), 0, MaxTileColumn),
        FMath::Clamp(FMath::FloorToInt((South + YMaxMetres) / TileMetres), 0, MaxTileRow));
    if (BoatTile == CurrentBoatTile)
    {
        return;
    }
    CurrentBoatTile = BoatTile;

    TMap<FIntPoint, int32> Desired;
    for (int32 Row = BoatTile.Y - FarTileRadius; Row <= BoatTile.Y + FarTileRadius; ++Row)
    {
        for (int32 Column = BoatTile.X - FarTileRadius; Column <= BoatTile.X + FarTileRadius; ++Column)
        {
            if (Row < 0 || Row > MaxTileRow || Column < 0 || Column > MaxTileColumn)
            {
                continue;
            }
            const int32 Step = FMath::Abs(Row - BoatTile.Y) <= NearTileRadius
                && FMath::Abs(Column - BoatTile.X) <= NearTileRadius ? 1 : 4;
            Desired.Add(FIntPoint(Column, Row), Step);
        }
    }

    for (auto It = VisibleTiles.CreateIterator(); It; ++It)
    {
        const int32* DesiredStep = Desired.Find(It.Key());
        if (!DesiredStep || *DesiredStep != It.Value().SampleStep)
        {
            if (It.Value().Mesh)
            {
                It.Value().Mesh->DestroyComponent();
            }
            It.RemoveCurrent();
        }
    }
    for (const TPair<FIntPoint, int32>& Tile : Desired)
    {
        if (!VisibleTiles.Contains(Tile.Key))
        {
            if (UProceduralMeshComponent* Mesh = CreateTile(Tile.Key.X, Tile.Key.Y, Tile.Value))
            {
                VisibleTiles.Add(Tile.Key, FVisibleTile{Mesh, Tile.Value});
            }
        }
    }
    if (WaterPlane && !Desired.IsEmpty())
    {
        int32 MinColumn = MAX_int32;
        int32 MaxColumn = MIN_int32;
        int32 MinRow = MAX_int32;
        int32 MaxRow = MIN_int32;
        for (const TPair<FIntPoint, int32>& Tile : Desired)
        {
            MinColumn = FMath::Min(MinColumn, Tile.Key.X);
            MaxColumn = FMath::Max(MaxColumn, Tile.Key.X);
            MinRow = FMath::Min(MinRow, Tile.Key.Y);
            MaxRow = FMath::Max(MaxRow, Tile.Key.Y);
        }
        const double West = XMinMetres + MinColumn * TileMetres;
        const double EastEdge = XMinMetres + FMath::Min((MaxColumn + 1) * TileCells,
                                                        GridWidth - 1) * SampleSpacingMetres;
        const double North = -YMaxMetres + MinRow * TileMetres;
        const double SouthEdge = -YMaxMetres + FMath::Min((MaxRow + 1) * TileCells,
                                                          GridHeight - 1) * SampleSpacingMetres;
        WaterPlane->SetRelativeLocation(FVector((West + EastEdge) * 50.0,
                                                 (North + SouthEdge) * 50.0, -5.0));
        WaterPlane->SetRelativeScale3D(FVector(EastEdge - West, SouthEdge - North, 1.0));
    }
}

void AGISTerrainActor::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!bReady)
    {
        return;
    }
    RefreshSeconds += DeltaSeconds;
    if (RefreshSeconds < 0.5f)
    {
        return;
    }
    RefreshSeconds = 0.0f;
    if (const APlayerController* Controller = GetWorld()->GetFirstPlayerController())
    {
        if (const APawn* Boat = Controller->GetPawn())
        {
            UpdateVisibleTiles(Boat->GetActorLocation());
        }
    }
}
