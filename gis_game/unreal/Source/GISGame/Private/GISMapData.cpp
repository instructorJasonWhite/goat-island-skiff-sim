#include "GISMapData.h"

#include "Dom/JsonObject.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
bool ReadNumber(const TSharedPtr<FJsonObject>& Object, const TCHAR* Name, double& Out)
{
    return Object.IsValid() && Object->TryGetNumberField(Name, Out) && FMath::IsFinite(Out);
}

bool ReadPoint(const TSharedPtr<FJsonValue>& Value, FVector2D& Out)
{
    if (!Value.IsValid() || Value->Type != EJson::Array)
    {
        return false;
    }
    const TArray<TSharedPtr<FJsonValue>>& Coordinates = Value->AsArray();
    double X = 0.0;
    double Y = 0.0;
    if (Coordinates.Num() != 2 || !Coordinates[0].IsValid() || !Coordinates[1].IsValid()
        || !Coordinates[0]->TryGetNumber(X) || !Coordinates[1]->TryGetNumber(Y)
        || !FMath::IsFinite(X) || !FMath::IsFinite(Y))
    {
        return false;
    }
    Out = FVector2D(X, Y);
    return true;
}

bool ReadPolygon(const TArray<TSharedPtr<FJsonValue>>& Values, TArray<FVector2D>& Out)
{
    if (Values.Num() < 3)
    {
        return false;
    }
    Out.Reset(Values.Num());
    for (const TSharedPtr<FJsonValue>& Value : Values)
    {
        FVector2D Point;
        if (!ReadPoint(Value, Point))
        {
            return false;
        }
        Out.Add(Point);
    }
    return true;
}
} // namespace

bool FGISMapData::LoadFromFile(const FString& FilePath, FString& OutError)
{
    FString Text;
    if (!FFileHelper::LoadFileToString(Text, *FilePath))
    {
        OutError = FString::Printf(TEXT("Could not read map: %s"), *FilePath);
        return false;
    }

    TSharedPtr<FJsonObject> Root;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Text);
    if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
    {
        OutError = TEXT("Map file is not valid JSON.");
        return false;
    }

    const TSharedPtr<FJsonObject>* Bounds = nullptr;
    const TSharedPtr<FJsonObject>* Spawn = nullptr;
    const TSharedPtr<FJsonObject>* Wind = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Water = nullptr;
    if (!Root->TryGetObjectField(TEXT("bounds_m"), Bounds)
        || !Root->TryGetObjectField(TEXT("spawn"), Spawn)
        || !Root->TryGetObjectField(TEXT("wind"), Wind)
        || !Root->TryGetArrayField(TEXT("water_polygon"), Water))
    {
        OutError = TEXT("Map is missing bounds, spawn, wind, or water_polygon.");
        return false;
    }

    double MinX = 0.0, MinY = 0.0, MaxX = 0.0, MaxY = 0.0;
    double SpawnX = 0.0, SpawnY = 0.0;
    if (!ReadNumber(*Bounds, TEXT("min_x"), MinX) || !ReadNumber(*Bounds, TEXT("min_y"), MinY)
        || !ReadNumber(*Bounds, TEXT("max_x"), MaxX) || !ReadNumber(*Bounds, TEXT("max_y"), MaxY)
        || !ReadNumber(*Spawn, TEXT("x_m"), SpawnX) || !ReadNumber(*Spawn, TEXT("y_m"), SpawnY)
        || !ReadNumber(*Spawn, TEXT("heading_deg"), SpawnHeadingDegreesFromNorth)
        || !ReadNumber(*Wind, TEXT("from_deg"), WindFromDegrees)
        || !ReadNumber(*Wind, TEXT("speed_mps"), WindSpeedMetresPerSecond)
        || !ReadNumber(*Wind, TEXT("gust_mps"), GustMetresPerSecond)
        || MaxX <= MinX || MaxY <= MinY || WindSpeedMetresPerSecond < 0.0)
    {
        OutError = TEXT("Map bounds, spawn, or wind values are invalid.");
        return false;
    }

    TArray<FVector2D> ParsedWater;
    if (!ReadPolygon(*Water, ParsedWater))
    {
        OutError = TEXT("Map water_polygon requires at least three finite points.");
        return false;
    }

    TArray<TArray<FVector2D>> ParsedIslands;
    const TArray<TSharedPtr<FJsonValue>>* IslandValues = nullptr;
    if (Root->TryGetArrayField(TEXT("islands"), IslandValues))
    {
        for (const TSharedPtr<FJsonValue>& Island : *IslandValues)
        {
            if (!Island.IsValid() || Island->Type != EJson::Array)
            {
                OutError = TEXT("Map island polygon is invalid.");
                return false;
            }
            TArray<FVector2D> Polygon;
            if (!ReadPolygon(Island->AsArray(), Polygon))
            {
                OutError = TEXT("Map island polygon requires at least three finite points.");
                return false;
            }
            ParsedIslands.Add(MoveTemp(Polygon));
        }
    }

    BoundsMin = FVector2D(MinX, MinY);
    BoundsMax = FVector2D(MaxX, MaxY);
    SpawnMetres = FVector2D(SpawnX, SpawnY);
    WaterPolygon = MoveTemp(ParsedWater);
    Islands = MoveTemp(ParsedIslands);
    Root->TryGetStringField(TEXT("name"), Name);
    Root->TryGetStringField(TEXT("description"), Description);
    Root->TryGetBoolField(TEXT("approximate"), bApproximate);
    if (!IsSailable(SpawnMetres.X, SpawnMetres.Y))
    {
        OutError = TEXT("Map spawn is outside sailable water.");
        return false;
    }
    OutError.Empty();
    return true;
}

bool FGISMapData::IsInsidePolygon(const TArray<FVector2D>& Polygon, const FVector2D& Point)
{
    bool bInside = false;
    for (int32 I = 0, J = Polygon.Num() - 1; I < Polygon.Num(); J = I++)
    {
        const FVector2D& A = Polygon[J];
        const FVector2D& B = Polygon[I];
        if ((A.Y > Point.Y) != (B.Y > Point.Y))
        {
            const double CrossX = A.X + (Point.Y - A.Y) * (B.X - A.X) / (B.Y - A.Y);
            if (Point.X < CrossX)
            {
                bInside = !bInside;
            }
        }
    }
    return bInside;
}

bool FGISMapData::IsSailable(double XMetres, double YMetres) const
{
    const FVector2D Point(XMetres, YMetres);
    if (!IsInsidePolygon(WaterPolygon, Point))
    {
        return false;
    }
    for (const TArray<FVector2D>& Island : Islands)
    {
        if (IsInsidePolygon(Island, Point))
        {
            return false;
        }
    }
    return true;
}
