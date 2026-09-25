#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "GISLandmarkScene.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;

// Map/UI code can read these sourced locations without inspecting visual
// meshes. Bridge and trestle spans are deliberately marked approximate.
USTRUCT(BlueprintType)
struct FGISLandmarkMapMarker
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category="GIS|Landmarks")
    FString Id;

    UPROPERTY(BlueprintReadOnly, Category="GIS|Landmarks")
    FString Name;

    UPROPERTY(BlueprintReadOnly, Category="GIS|Landmarks")
    FString Type;

    UPROPERTY(BlueprintReadOnly, Category="GIS|Landmarks")
    FVector2D EastNorthMetres = FVector2D::ZeroVector;

    UPROPERTY(BlueprintReadOnly, Category="GIS|Landmarks")
    FVector WorldCentimetres = FVector::ZeroVector;

    UPROPERTY(BlueprintReadOnly, Category="GIS|Landmarks")
    bool bApproximateStructureGeometry = true;
};

// Visual-only infrastructure from Content/Data/greenwood_landmarks.json.
// Coordinates are sourced; deck widths, pier spacing, and heights are scenic
// approximations. They have no collision or navigational clearance meaning.
UCLASS()
class GISGAME_API AGISLandmarkScene : public AActor
{
    GENERATED_BODY()

public:
    AGISLandmarkScene();

    UFUNCTION(BlueprintCallable, Category="GIS|Landmarks")
    bool LoadLandmarksFromFile(const FString& FilePath);

    UPROPERTY(BlueprintReadOnly, Category="GIS|Landmarks")
    TArray<FGISLandmarkMapMarker> MapMarkers;

    // Toggle in a Blueprint subclass if authored meshes and signs replace
    // these source-point labels.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="GIS|Landmarks")
    bool bShowWorldLabels = true;

private:
    UPROPERTY(VisibleAnywhere, Category="GIS|Landmarks")
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(Transient)
    TArray<TObjectPtr<UHierarchicalInstancedStaticMeshComponent>> VisualLayers;
};
