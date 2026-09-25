#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GISTerrainActor.generated.h"

struct FGISMapData;
class UMaterialInterface;
class UProceduralMeshComponent;
class USceneComponent;
class UStaticMeshComponent;

// Streams the measured Greenwood elevation grid around the boat. The R16 is
// kept in memory (about 8 MB); only nearby portions become render meshes.
UCLASS()
class GISGAME_API AGISTerrainActor : public AActor
{
    GENERATED_BODY()

public:
    AGISTerrainActor();
    virtual void Tick(float DeltaSeconds) override;

    // The map polygon is used once to put the hydroflattened lake bed below
    // the water visual while keeping islands and land at measured elevations.
    bool Initialize(const FGISMapData& Map);

private:
    static constexpr int32 TileCells = 64;
    static constexpr int32 NearTileRadius = 1;
    static constexpr int32 FarTileRadius = 4;

    struct FVisibleTile
    {
        UProceduralMeshComponent* Mesh = nullptr;
        int32 SampleStep = 1;
    };

    UPROPERTY()
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY()
    TObjectPtr<UMaterialInterface> LandMaterial;

    UPROPERTY()
    TObjectPtr<UStaticMeshComponent> WaterPlane;

    TArray<uint16> Heights;
    TArray<uint8> WaterMask;
    TMap<FIntPoint, FVisibleTile> VisibleTiles;
    int32 GridWidth = 0;
    int32 GridHeight = 0;
    double XMinMetres = 0.0;
    double YMaxMetres = 0.0;
    double SampleSpacingMetres = 0.0;
    double CentimetresPerCode = 0.0;
    int32 ZeroCode = 32768;
    FIntPoint CurrentBoatTile = FIntPoint(INDEX_NONE, INDEX_NONE);
    float RefreshSeconds = 0.0f;
    bool bReady = false;

    bool LoadData(FString& OutError);
    void BuildWaterMask(const FGISMapData& Map);
    double HeightCentimetres(int32 Row, int32 Column) const;
    void UpdateVisibleTiles(const FVector& BoatWorldLocation);
    UProceduralMeshComponent* CreateTile(int32 TileColumn, int32 TileRow, int32 Step);
};
