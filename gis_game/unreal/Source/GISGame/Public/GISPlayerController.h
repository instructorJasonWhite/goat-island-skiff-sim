#pragma once

#include "CoreMinimal.h"
#include "GameFramework/PlayerController.h"
#include "GISPlayerController.generated.h"

UCLASS()
class GISGAME_API AGISPlayerController : public APlayerController
{
    GENERATED_BODY()

public:
    virtual void BeginPlay() override;
};
