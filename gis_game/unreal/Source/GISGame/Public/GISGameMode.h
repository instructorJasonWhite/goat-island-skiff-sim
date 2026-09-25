#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GISMapData.h"
#include "GISGameMode.generated.h"

UCLASS(Config=Game)
class GISGAME_API AGISGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    AGISGameMode();
    virtual void InitGame(const FString& MapName, const FString& Options,
                          FString& ErrorMessage) override;
    virtual void BeginPlay() override;
    virtual void RestartPlayer(AController* NewPlayer) override;

    // Only a filename in Content/Data is accepted. Override in a Blueprint,
    // DefaultGame.ini, or with ?GISMap=another_lake.json in the launch URL.
    UPROPERTY(Config, EditDefaultsOnly, Category="GIS|Map")
    FString MapFileName = TEXT("greenwood_usgs.json");

private:
    FGISMapData LakeMap;
    bool bUseGreenwoodTerrain = false;
    void BuildLakeVisuals();
};
