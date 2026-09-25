#pragma once

#include "CoreMinimal.h"

// The JSON contract lives in ../maps. All map distances and positions are
// local metres: X east, Y north. Map provenance and suitability vary by file.
struct FGISMapData
{
    FString Name = TEXT("Schematic training reach");
    FString Description;
    bool bApproximate = true;
    FVector2D BoundsMin = FVector2D(-500.0, -500.0);
    FVector2D BoundsMax = FVector2D(500.0, 500.0);
    TArray<FVector2D> WaterPolygon;
    TArray<TArray<FVector2D>> Islands;
    FVector2D SpawnMetres = FVector2D::ZeroVector;
    double SpawnHeadingDegreesFromNorth = 90.0;
    double WindFromDegrees = 315.0;
    double WindSpeedMetresPerSecond = 5.8;
    double GustMetresPerSecond = 2.0;

    bool LoadFromFile(const FString& FilePath, FString& OutError);
    bool IsSailable(double XMetres, double YMetres) const;

private:
    static bool IsInsidePolygon(const TArray<FVector2D>& Polygon, const FVector2D& Point);
};
