#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimInstanceProxy.h"
#include "GISBoatAnimInstance.generated.h"

class UAnimSequence;
struct FPoseContext;

// The Blender clips supply exact pivots and travel for each independently
// controlled part. The proxy samples them into one pose each animation frame.
struct FGISBoatAnimInstanceProxy final : public FAnimInstanceProxy
{
    FGISBoatAnimInstanceProxy();
    explicit FGISBoatAnimInstanceProxy(UAnimInstance* Instance);

    virtual bool Evaluate(FPoseContext& Output) override;

    void SetControls(float InTillerDegrees, float InSailDegrees,
        float InHoist, float InRudderLift, float InCenterboardLift);
    void SetClips(UAnimSequence* InTiller, UAnimSequence* InSail,
        UAnimSequence* InHoist, UAnimSequence* InRudderLift,
        UAnimSequence* InCenterboardLift);

private:
    float TillerDegrees = 0.0f;
    float SailDegrees = 0.0f;
    float Hoist = 1.0f;
    float RudderLift = 0.0f;
    float CenterboardLift = 0.0f;
    UAnimSequence* TillerClip = nullptr;
    UAnimSequence* SailClip = nullptr;
    UAnimSequence* HoistClip = nullptr;
    UAnimSequence* RudderLiftClip = nullptr;
    UAnimSequence* CenterboardLiftClip = nullptr;
};

UCLASS(Transient, Blueprintable)
class GISGAME_API UGISBoatAnimInstance : public UAnimInstance
{
    GENERATED_BODY()

public:
    UGISBoatAnimInstance();
    virtual void NativeInitializeAnimation() override;
    virtual void NativeUpdateAnimation(float DeltaSeconds) override;

protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;

private:
    UPROPERTY(EditDefaultsOnly, Category="GIS|Rig")
    TSoftObjectPtr<UAnimSequence> TillerAsset;
    UPROPERTY(EditDefaultsOnly, Category="GIS|Rig")
    TSoftObjectPtr<UAnimSequence> SailAsset;
    UPROPERTY(EditDefaultsOnly, Category="GIS|Rig")
    TSoftObjectPtr<UAnimSequence> HoistAsset;
    UPROPERTY(EditDefaultsOnly, Category="GIS|Rig")
    TSoftObjectPtr<UAnimSequence> RudderLiftAsset;
    UPROPERTY(EditDefaultsOnly, Category="GIS|Rig")
    TSoftObjectPtr<UAnimSequence> CenterboardLiftAsset;

    UPROPERTY(Transient)
    TObjectPtr<UAnimSequence> LoadedTiller;
    UPROPERTY(Transient)
    TObjectPtr<UAnimSequence> LoadedSail;
    UPROPERTY(Transient)
    TObjectPtr<UAnimSequence> LoadedHoist;
    UPROPERTY(Transient)
    TObjectPtr<UAnimSequence> LoadedRudderLift;
    UPROPERTY(Transient)
    TObjectPtr<UAnimSequence> LoadedCenterboardLift;

};
