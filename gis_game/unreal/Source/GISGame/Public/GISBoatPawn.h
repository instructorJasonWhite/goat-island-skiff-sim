#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "GISMapData.h"
#include "SailingSim.h"
#include "GISBoatPawn.generated.h"

class UCameraComponent;
class UAnimInstance;
class USpringArmComponent;
class USkeletalMesh;
class USkeletalMeshComponent;
class UStaticMeshComponent;
struct FMinimalViewInfo;

UCLASS()
class GISGAME_API AGISBoatPawn : public APawn
{
    GENERATED_BODY()

public:
    AGISBoatPawn();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void CalcCamera(float DeltaTime, FMinimalViewInfo& OutResult) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

    void InitializeFromMap(const FGISMapData& InMap);
    const gis::State& GetBoatState() const { return BoatState; }
    const gis::Input& GetSailingInput() const { return SailingInput; }
    const gis::StepResult& GetLastStep() const { return LastStep; }
    const FGISMapData& GetMapData() const { return MapData; }
    double GetWindSpeedMetresPerSecond() const;
    bool IsFirstPersonView() const { return bFirstPersonView; }

    // Read these values in an Animation Blueprint using Try Get Pawn Owner.
    // Solver/body +Y is port; delivered FBX and Unreal +Y are starboard.
    // The coordinate adapter maps their rotations into visual bone angles.
    UPROPERTY(BlueprintReadOnly, Category="GIS|Rig")
    float TillerAngleDegrees = 0.0f;

    UPROPERTY(BlueprintReadOnly, Category="GIS|Rig")
    float SailSwingDegrees = 0.0f;

    UPROPERTY(BlueprintReadOnly, Category="GIS|Rig")
    float SailHoist = 1.0f;

    UPROPERTY(BlueprintReadOnly, Category="GIS|Rig")
    float RudderLift = 0.0f;

    UPROPERTY(BlueprintReadOnly, Category="GIS|Rig")
    float CenterboardLift = 0.0f;

protected:
    // Import SK_Goat_Island_Skiff.fbx into /Game/Boat/ with this name, or
    // override this soft path on a Pawn Blueprint subclass.
    UPROPERTY(EditDefaultsOnly, Category="GIS|Art")
    TSoftObjectPtr<USkeletalMesh> BoatMeshAsset;

    UPROPERTY(EditDefaultsOnly, Category="GIS|Art")
    TSubclassOf<UAnimInstance> BoatAnimationClass;

private:
    UPROPERTY(VisibleAnywhere, Category="GIS|Art")
    TObjectPtr<USceneComponent> SceneRoot;
    UPROPERTY(VisibleAnywhere, Category="GIS|Art")
    TObjectPtr<USkeletalMeshComponent> BoatArt;
    UPROPERTY(VisibleAnywhere, Category="GIS|Placeholder")
    TObjectPtr<UStaticMeshComponent> HullPlaceholder;
    UPROPERTY(VisibleAnywhere, Category="GIS|Placeholder")
    TObjectPtr<UStaticMeshComponent> DeckPlaceholder;
    UPROPERTY(VisibleAnywhere, Category="GIS|Placeholder")
    TObjectPtr<UStaticMeshComponent> MastPlaceholder;
    UPROPERTY(VisibleAnywhere, Category="GIS|Placeholder")
    TObjectPtr<UStaticMeshComponent> SailPlaceholder;
    UPROPERTY(VisibleAnywhere, Category="GIS|Placeholder")
    TObjectPtr<UStaticMeshComponent> RudderPlaceholder;
    UPROPERTY(VisibleAnywhere, Category="GIS|Placeholder")
    TObjectPtr<UStaticMeshComponent> BoardPlaceholder;
    // Live spans join the imported rig's moving helper bones.
    UPROPERTY(VisibleAnywhere, Category="GIS|Rig")
    TArray<TObjectPtr<UStaticMeshComponent>> RiggingLines;
    UPROPERTY(VisibleAnywhere, Category="GIS|Camera")
    TObjectPtr<USpringArmComponent> CameraBoom;
    UPROPERTY(VisibleAnywhere, Category="GIS|Camera")
    TObjectPtr<UCameraComponent> FollowCamera;
    UPROPERTY(VisibleAnywhere, Category="GIS|Camera")
    TObjectPtr<UCameraComponent> FirstPersonCamera;

    gis::State BoatState;
    gis::Input SailingInput;
    gis::Params SailingParams;
    gis::StepResult LastStep;
    FGISMapData MapData;
    bool bHaveMap = false;
    double StepAccumulator = 0.0;

    float HelmAxis = 0.0f;
    float SheetAxis = 0.0f;
    float CrewAxis = 0.0f;
    float CenterboardAxis = 0.0f;
    float RudderBladeAxis = 0.0f;
    float HoistAxis = 0.0f;
    float CameraYawAxis = 0.0f;
    float CameraPitchAxis = 0.0f;
    float CameraZoomAxis = 0.0f;
    bool bMouseHelmHeld = false;
    bool bFirstPersonView = false;
    float MouseHelm = 0.0f;

    void SetHelmAxis(float Value) { HelmAxis = Value; }
    void SetSheetAxis(float Value) { SheetAxis = Value; }
    void SetCrewAxis(float Value) { CrewAxis = Value; }
    void SetCenterboardAxis(float Value) { CenterboardAxis = Value; }
    void SetRudderBladeAxis(float Value) { RudderBladeAxis = Value; }
    void SetHoistAxis(float Value) { HoistAxis = Value; }
    void SetCameraYawAxis(float Value) { CameraYawAxis = Value; }
    void SetCameraPitchAxis(float Value) { CameraPitchAxis = Value; }
    void SetCameraZoomAxis(float Value) { CameraZoomAxis = Value; }
    void OnMouseHelmAxis(float Value);
    void OnSheetWheel(float Value);
    void OnMouseHelmPressed();
    void OnMouseHelmReleased();
    void OnToggleCamera();
    void OnToggleMap();
    void OnToggleDataPanel();
    void OnRecover();
    void OnTogglePause();
    void UpdateVisuals();
    void UpdateRiggingLines();
};
