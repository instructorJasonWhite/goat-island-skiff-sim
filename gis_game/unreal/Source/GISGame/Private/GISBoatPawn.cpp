#include "GISBoatPawn.h"
#include "GISBoatAnimInstance.h"
#include "GISCoordinates.h"
#include "GISHUD.h"
#include "GISUserSettings.h"

#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Math/RotationMatrix.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
constexpr double FixedStepSeconds = 1.0 / 120.0;
const FName RiggingLineNames[4] = {
    TEXT("LiveHalyard"), TEXT("LiveMainsheet"),
    TEXT("LiveDownhaul"), TEXT("LiveRudderShockCord")};
const FName RiggingLineEndpoints[4][2] = {
    {TEXT("HalyardMast"), TEXT("HalyardYard")},
    {TEXT("SheetTraveller"), TEXT("SheetBoom")},
    {TEXT("DownhaulDeck"), TEXT("DownhaulBoom")},
    {TEXT("ShockCordStock"), TEXT("ShockCordBlade")}};

void SetPlaceholderTint(UStaticMeshComponent* Mesh, const FLinearColor& Tint)
{
    if (!Mesh || !Mesh->GetMaterial(0))
    {
        return;
    }
    UMaterialInstanceDynamic* Material = Mesh->CreateDynamicMaterialInstance(0);
    if (Material)
    {
        Material->SetVectorParameterValue(TEXT("Color"), Tint);
    }
}
} // namespace

AGISBoatPawn::AGISBoatPawn()
{
    PrimaryActorTick.bCanEverTick = true;
    AutoPossessPlayer = EAutoReceiveInput::Player0;

    SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("BoatRoot"));
    RootComponent = SceneRoot;

    BoatArt = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("ImportedBoatArt"));
    BoatArt->SetupAttachment(SceneRoot);
    BoatArt->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    BoatArt->SetVisibility(false);

    HullPlaceholder = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlaceholderHull"));
    HullPlaceholder->SetupAttachment(SceneRoot);
    HullPlaceholder->SetRelativeScale3D(FVector(4.6f, 1.45f, 0.3f));
    HullPlaceholder->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    DeckPlaceholder = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlaceholderDeck"));
    DeckPlaceholder->SetupAttachment(SceneRoot);
    DeckPlaceholder->SetRelativeLocation(FVector(0.0f, 0.0f, 16.0f));
    DeckPlaceholder->SetRelativeScale3D(FVector(4.1f, 1.2f, 0.025f));
    DeckPlaceholder->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    MastPlaceholder = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlaceholderMast"));
    MastPlaceholder->SetupAttachment(SceneRoot);
    MastPlaceholder->SetRelativeLocation(FVector(60.0f, 0.0f, 240.0f));
    MastPlaceholder->SetRelativeScale3D(FVector(0.05f, 0.05f, 4.73f));
    MastPlaceholder->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    SailPlaceholder = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlaceholderSail"));
    SailPlaceholder->SetupAttachment(SceneRoot);
    SailPlaceholder->SetRelativeLocation(FVector(-35.0f, 0.0f, 235.0f));
    SailPlaceholder->SetRelativeScale3D(FVector(2.9f, 0.015f, 3.35f));
    SailPlaceholder->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    RudderPlaceholder = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlaceholderSlidingRudder"));
    RudderPlaceholder->SetupAttachment(SceneRoot);
    RudderPlaceholder->SetRelativeScale3D(FVector(0.36f, 0.045f, 0.95f));
    RudderPlaceholder->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    BoardPlaceholder = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("PlaceholderDaggerboard"));
    BoardPlaceholder->SetupAttachment(SceneRoot);
    BoardPlaceholder->SetRelativeScale3D(FVector(0.33f, 0.04f, 1.1f));
    BoardPlaceholder->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    for (const FName LineName : RiggingLineNames)
    {
        UStaticMeshComponent* Line = CreateDefaultSubobject<UStaticMeshComponent>(LineName);
        Line->SetupAttachment(SceneRoot);
        Line->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Line->SetCastShadow(false);
        Line->SetVisibility(false);
        RiggingLines.Add(Line);
    }

    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    if (Cube.Succeeded())
    {
        HullPlaceholder->SetStaticMesh(Cube.Object);
        DeckPlaceholder->SetStaticMesh(Cube.Object);
        SailPlaceholder->SetStaticMesh(Cube.Object);
        RudderPlaceholder->SetStaticMesh(Cube.Object);
        BoardPlaceholder->SetStaticMesh(Cube.Object);
    }
    if (Cylinder.Succeeded())
    {
        MastPlaceholder->SetStaticMesh(Cylinder.Object);
        for (UStaticMeshComponent* Line : RiggingLines)
        {
            Line->SetStaticMesh(Cylinder.Object);
        }
    }

    CameraBoom = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom"));
    CameraBoom->SetupAttachment(SceneRoot);
    // Follow from just aft of the cockpit, offset to starboard like a sailor's shoulder.
    CameraBoom->SetRelativeLocation(FVector(-65.0f, 55.0f, 110.0f));
    CameraBoom->TargetArmLength = 275.0f;
    CameraBoom->SetRelativeRotation(FRotator(-13.0f, 0.0f, 0.0f));
    CameraBoom->bDoCollisionTest = false;
    CameraBoom->bEnableCameraLag = true;
    CameraBoom->CameraLagSpeed = 9.0f;
    CameraBoom->bInheritRoll = false;
    FollowCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FollowCamera"));
    FollowCamera->SetupAttachment(CameraBoom, USpringArmComponent::SocketName);
    FollowCamera->FieldOfView = 82.0f;

    // The eye point is near the tiller. It rolls with the boat as the sailor would.
    FirstPersonCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
    FirstPersonCamera->SetupAttachment(SceneRoot);
    FirstPersonCamera->SetRelativeLocation(FVector(-135.0f, 38.0f, 105.0f));
    FirstPersonCamera->FieldOfView = 88.0f;
    FirstPersonCamera->SetAutoActivate(false);

    BoatMeshAsset = TSoftObjectPtr<USkeletalMesh>(
        FSoftObjectPath(TEXT("/Game/Boat/SK_Goat_Island_Skiff.SK_Goat_Island_Skiff")));
}

void AGISBoatPawn::BeginPlay()
{
    Super::BeginPlay();

    FollowCamera->SetActive(true);
    FirstPersonCamera->SetActive(false);

    if (USkeletalMesh* ImportedMesh = BoatMeshAsset.LoadSynchronous())
    {
        BoatArt->SetSkeletalMeshAsset(ImportedMesh);
        UClass* RigClass = BoatAnimationClass
            ? BoatAnimationClass.Get() : UGISBoatAnimInstance::StaticClass();
        BoatArt->SetAnimInstanceClass(RigClass);
        BoatArt->SetVisibility(true);
        if (UMaterialInterface* Rope = LoadObject<UMaterialInterface>(nullptr,
            TEXT("/Game/Boat/Natural_running_rigging.Natural_running_rigging")))
        {
            for (UStaticMeshComponent* Line : RiggingLines)
            {
                Line->SetMaterial(0, Rope);
            }
        }
        HullPlaceholder->SetVisibility(false);
        DeckPlaceholder->SetVisibility(false);
        MastPlaceholder->SetVisibility(false);
        SailPlaceholder->SetVisibility(false);
        RudderPlaceholder->SetVisibility(false);
        BoardPlaceholder->SetVisibility(false);
    }
    else
    {
        // Approximate visual cues until the supplied FBX is imported.
        SetPlaceholderTint(HullPlaceholder, FLinearColor(0.015f, 0.078f, 0.16f));
        SetPlaceholderTint(DeckPlaceholder, FLinearColor(0.82f, 0.82f, 0.79f));
        SetPlaceholderTint(SailPlaceholder, FLinearColor(0.90f, 0.91f, 0.88f));
        const FLinearColor Fir(0.48f, 0.23f, 0.09f);
        SetPlaceholderTint(MastPlaceholder, Fir);
        SetPlaceholderTint(RudderPlaceholder, Fir);
        SetPlaceholderTint(BoardPlaceholder, Fir);
    }
    UpdateVisuals();
    UpdateRiggingLines();
}

void AGISBoatPawn::CalcCamera(float DeltaTime, FMinimalViewInfo& OutResult)
{
    // Select explicitly: two camera components should never leave view choice
    // dependent on component registration order or an inherited Blueprint.
    UCameraComponent* View = bFirstPersonView ? FirstPersonCamera : FollowCamera;
    if (View)
    {
        View->GetCameraView(DeltaTime, OutResult);
    }
    else
    {
        Super::CalcCamera(DeltaTime, OutResult);
    }
}

void AGISBoatPawn::InitializeFromMap(const FGISMapData& InMap)
{
    MapData = InMap;
    bHaveMap = true;
    BoatState = gis::State{};
    BoatState.x = InMap.SpawnMetres.X;
    BoatState.y = InMap.SpawnMetres.Y;
    BoatState.heading = FMath::DegreesToRadians(90.0 - InMap.SpawnHeadingDegreesFromNorth);

    const double FromRadians = FMath::DegreesToRadians(InMap.WindFromDegrees);
    SailingInput = gis::Input{};
    SailingInput.true_wind = {
        -InMap.WindSpeedMetresPerSecond * FMath::Sin(FromRadians),
        -InMap.WindSpeedMetresPerSecond * FMath::Cos(FromRadians)};
    SailingInput.sheet_ease = 0.25;
    SailingParams.gust_speed_std = InMap.GustMetresPerSecond;
    StepAccumulator = 0.0;
    UpdateVisuals();
    UpdateRiggingLines();
}

void AGISBoatPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);
    PlayerInputComponent->BindAxis(TEXT("Helm"), this, &AGISBoatPawn::SetHelmAxis);
    PlayerInputComponent->BindAxis(TEXT("Sheet"), this, &AGISBoatPawn::SetSheetAxis);
    PlayerInputComponent->BindAxis(TEXT("Crew"), this, &AGISBoatPawn::SetCrewAxis);
    PlayerInputComponent->BindAxis(TEXT("Centerboard"), this, &AGISBoatPawn::SetCenterboardAxis);
    PlayerInputComponent->BindAxis(TEXT("RudderBlade"), this, &AGISBoatPawn::SetRudderBladeAxis);
    PlayerInputComponent->BindAxis(TEXT("SailHoist"), this, &AGISBoatPawn::SetHoistAxis);
    PlayerInputComponent->BindAxis(TEXT("CameraYaw"), this, &AGISBoatPawn::SetCameraYawAxis);
    PlayerInputComponent->BindAxis(TEXT("CameraPitch"), this, &AGISBoatPawn::SetCameraPitchAxis);
    PlayerInputComponent->BindAxis(TEXT("CameraZoom"), this, &AGISBoatPawn::SetCameraZoomAxis);
    PlayerInputComponent->BindAxis(TEXT("MouseHelm"), this, &AGISBoatPawn::OnMouseHelmAxis);
    PlayerInputComponent->BindAxis(TEXT("SheetWheel"), this, &AGISBoatPawn::OnSheetWheel);
    FInputActionBinding& MousePressBinding = PlayerInputComponent->BindAction(TEXT("MouseHelmHold"), IE_Pressed,
        this, &AGISBoatPawn::OnMouseHelmPressed);
    MousePressBinding.bExecuteWhenPaused = true;
    PlayerInputComponent->BindAction(TEXT("MouseHelmHold"), IE_Released,
        this, &AGISBoatPawn::OnMouseHelmReleased);
    PlayerInputComponent->BindAction(TEXT("ToggleCamera"), IE_Pressed,
        this, &AGISBoatPawn::OnToggleCamera);
    PlayerInputComponent->BindAction(TEXT("ToggleMap"), IE_Pressed,
        this, &AGISBoatPawn::OnToggleMap);
    PlayerInputComponent->BindAction(TEXT("ToggleDataPanel"), IE_Pressed,
        this, &AGISBoatPawn::OnToggleDataPanel);
    PlayerInputComponent->BindAction(TEXT("Recover"), IE_Pressed, this, &AGISBoatPawn::OnRecover);
    FInputActionBinding& PauseBinding = PlayerInputComponent->BindAction(
        TEXT("TogglePause"), IE_Pressed, this, &AGISBoatPawn::OnTogglePause);
    PauseBinding.bExecuteWhenPaused = true;
}

void AGISBoatPawn::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    const float FrameSeconds = FMath::Clamp(DeltaSeconds, 0.0f, 0.25f);

    if (bFirstPersonView)
    {
        const FRotator ViewRotation = FirstPersonCamera->GetRelativeRotation();
        FirstPersonCamera->SetRelativeRotation(FRotator(
            FMath::Clamp(ViewRotation.Pitch + CameraPitchAxis * FrameSeconds * 60.0f,
                -65.0f, 45.0f),
            FMath::Clamp(FRotator::NormalizeAxis(
                ViewRotation.Yaw + CameraYawAxis * FrameSeconds * 70.0f),
                -110.0f, 110.0f),
            0.0f));
    }
    else
    {
        const FRotator ViewRotation = CameraBoom->GetRelativeRotation();
        CameraBoom->SetRelativeRotation(FRotator(
            FMath::Clamp(ViewRotation.Pitch + CameraPitchAxis * FrameSeconds * 60.0f,
                -65.0f, 15.0f),
            FRotator::NormalizeAxis(ViewRotation.Yaw + CameraYawAxis * FrameSeconds * 70.0f),
            0.0f));
        CameraBoom->TargetArmLength = FMath::Clamp(
            CameraBoom->TargetArmLength - CameraZoomAxis * FrameSeconds * 400.0f,
            180.0f, 600.0f);
    }

    if (!bHaveMap)
    {
        return;
    }

    SailingInput.helm = FMath::Clamp(
        static_cast<double>(bMouseHelmHeld ? MouseHelm : HelmAxis), -1.0, 1.0);
    SailingInput.sheet_ease = FMath::Clamp(
        SailingInput.sheet_ease + SheetAxis * FrameSeconds * 0.45, 0.0, 1.0);
    SailingInput.crew_shift = FMath::Clamp(
        SailingInput.crew_shift + CrewAxis * FrameSeconds * 0.35, -0.60, 0.60);
    SailingInput.centerboard = FMath::Clamp(
        SailingInput.centerboard + CenterboardAxis * FrameSeconds * 0.45, 0.0, 1.0);
    SailingInput.rudder_immersion = FMath::Clamp(
        SailingInput.rudder_immersion + RudderBladeAxis * FrameSeconds * 0.45, 0.0, 1.0);
    SailingInput.sail_hoist = FMath::Clamp(
        SailingInput.sail_hoist + HoistAxis * FrameSeconds * 0.30, 0.0, 1.0);

    // Fixed physics substeps prevent frame-rate-dependent steering and gusts.
    StepAccumulator += FrameSeconds;
    int32 Substeps = 0;
    while (StepAccumulator >= FixedStepSeconds && Substeps < 30)
    {
        const double OldX = BoatState.x;
        const double OldY = BoatState.y;
        LastStep = gis::step(BoatState, SailingInput, SailingParams, FixedStepSeconds);
        StepAccumulator -= FixedStepSeconds;
        ++Substeps;
        if (!MapData.IsSailable(BoatState.x, BoatState.y))
        {
            BoatState.x = OldX;
            BoatState.y = OldY;
            BoatState.u *= -0.15;
            BoatState.v *= -0.15;
            BoatState.yaw_rate *= 0.5;
        }
    }
    // A long hitch drops excess wall time instead of feeding an unsafe step.
    if (Substeps == 30)
    {
        StepAccumulator = 0.0;
    }
    UpdateVisuals();
    UpdateRiggingLines();
}

void AGISBoatPawn::UpdateVisuals()
{
    const float HeadingDegrees = static_cast<float>(
        gis_unreal::core_heading_rad_to_ue_yaw_deg(BoatState.heading));
    const float VisualHeelDegrees = static_cast<float>(
        gis_unreal::core_heel_rad_to_ue_roll_deg(BoatState.heel));
    SetActorLocationAndRotation(
        FVector(gis_unreal::east_metres_to_ue_x_cm(BoatState.x),
                gis_unreal::north_metres_to_ue_y_cm(BoatState.y), 28.0),
        FRotator(0.0f, HeadingDegrees, VisualHeelDegrees), false, nullptr,
        ETeleportType::TeleportPhysics);

    TillerAngleDegrees = static_cast<float>(
        gis_unreal::core_port_angle_rad_to_ue_bone_yaw_deg(BoatState.rudder_angle));
    SailSwingDegrees = static_cast<float>(
        gis_unreal::core_port_angle_rad_to_ue_bone_yaw_deg(BoatState.boom_angle));
    SailHoist = static_cast<float>(SailingInput.sail_hoist);
    RudderLift = static_cast<float>(1.0 - SailingInput.rudder_immersion);
    CenterboardLift = static_cast<float>(1.0 - SailingInput.centerboard);

    RudderPlaceholder->SetRelativeLocation(FVector(-240.0f, 0.0f, -36.0f + 75.0f * RudderLift));
    RudderPlaceholder->SetRelativeRotation(FRotator(0.0f, TillerAngleDegrees, 0.0f));
    BoardPlaceholder->SetRelativeLocation(FVector(-45.0f, 0.0f, -40.0f + 90.0f * CenterboardLift));
    SailPlaceholder->SetRelativeRotation(FRotator(0.0f, SailSwingDegrees, 0.0f));
    SailPlaceholder->SetRelativeScale3D(FVector(2.9f, 0.015f, FMath::Max(0.1f, 3.35f * SailHoist)));
    if (BoatArt->GetSkeletalMeshAsset())
    {
        BoatArt->SetMorphTarget(FName(TEXT("Furled")), 1.0f - SailHoist);
    }
}

void AGISBoatPawn::UpdateRiggingLines()
{
    if (!BoatArt->GetSkeletalMeshAsset())
    {
        return;
    }
    for (int32 Index = 0; Index < RiggingLines.Num() && Index < 4; ++Index)
    {
        UStaticMeshComponent* Line = RiggingLines[Index];
        const FName StartBone = RiggingLineEndpoints[Index][0];
        const FName EndBone = RiggingLineEndpoints[Index][1];
        if (BoatArt->GetBoneIndex(StartBone) == INDEX_NONE ||
            BoatArt->GetBoneIndex(EndBone) == INDEX_NONE)
        {
            Line->SetVisibility(false);
            continue;
        }
        const FVector Start = BoatArt->GetBoneLocation(StartBone);
        const FVector End = BoatArt->GetBoneLocation(EndBone);
        const FVector Span = End - Start;
        const double Length = Span.Size();
        if (Length < 1.0)
        {
            Line->SetVisibility(false);
            continue;
        }
        Line->SetWorldLocation((Start + End) * 0.5);
        Line->SetWorldRotation(FRotationMatrix::MakeFromZ(Span).Rotator());
        // Engine BasicShapes/Cylinder is 100 cm high and 100 cm in diameter.
        Line->SetWorldScale3D(FVector(0.009f, 0.009f,
            static_cast<float>(Length / 100.0)));
        Line->SetVisibility(true);
    }
}

double AGISBoatPawn::GetWindSpeedMetresPerSecond() const
{
    const gis::Vec2 Wind = BoatState.time > 0.0
        ? LastStep.true_wind_world : SailingInput.true_wind;
    return FMath::Sqrt(FMath::Square(Wind.x) + FMath::Square(Wind.y));
}

void AGISBoatPawn::OnMouseHelmAxis(float Value)
{
    if (bMouseHelmHeld && !FMath::IsNearlyZero(Value))
    {
        // A right drag pushes the forward tiller handle starboard. The aft
        // rudder blade swings port, so the bow turns port while moving ahead.
        MouseHelm = FMath::Clamp(MouseHelm + Value * 0.008f
            * FGISUserSettings::GetHelmSensitivity(), -1.0f, 1.0f);
    }
}

void AGISBoatPawn::OnSheetWheel(float Value)
{
    if (!FMath::IsNearlyZero(Value))
    {
        // Positive wheel motion pulls the sheet in (less ease).
        SailingInput.sheet_ease = FMath::Clamp(
            SailingInput.sheet_ease - Value * 0.06, 0.0, 1.0);
    }
}

void AGISBoatPawn::OnMouseHelmPressed()
{
    if (APlayerController* PlayerController = Cast<APlayerController>(GetController()))
    {
        AGISHUD* BoatHUD = Cast<AGISHUD>(PlayerController->GetHUD());
        float ScreenX = 0.0f;
        float ScreenY = 0.0f;
        if (PlayerController->GetMousePosition(ScreenX, ScreenY))
        {
            if (BoatHUD && BoatHUD->HandlePointerPress(ScreenX, ScreenY))
            {
                return;
            }
        }
        if (BoatHUD && BoatHUD->IsMenuOpen())
        {
            return;
        }
    }
    bMouseHelmHeld = true;
    MouseHelm = 0.0f;
}

void AGISBoatPawn::OnMouseHelmReleased()
{
    bMouseHelmHeld = false;
    MouseHelm = 0.0f;
    SailingInput.helm = 0.0;
}

void AGISBoatPawn::OnToggleCamera()
{
    bFirstPersonView = !bFirstPersonView;
    FollowCamera->SetActive(!bFirstPersonView);
    FirstPersonCamera->SetActive(bFirstPersonView);
}

void AGISBoatPawn::OnToggleMap()
{
    if (const APlayerController* PlayerController = Cast<APlayerController>(GetController()))
    {
        if (AGISHUD* BoatHUD = Cast<AGISHUD>(PlayerController->GetHUD()))
        {
            BoatHUD->ToggleMap();
        }
    }
}

void AGISBoatPawn::OnToggleDataPanel()
{
    if (const APlayerController* PlayerController = Cast<APlayerController>(GetController()))
    {
        if (AGISHUD* BoatHUD = Cast<AGISHUD>(PlayerController->GetHUD()))
        {
            BoatHUD->ToggleDataPanel();
        }
    }
}

void AGISBoatPawn::OnRecover()
{
    if (BoatState.capsized)
    {
        BoatState.capsized = false;
        BoatState.u = 0.0;
        BoatState.v = 0.0;
        BoatState.yaw_rate = 0.0;
        BoatState.heel = 0.0;
        BoatState.roll_rate = 0.0;
        SailingInput.sheet_ease = 1.0;
        UpdateVisuals();
    }
}

void AGISBoatPawn::OnTogglePause()
{
    bMouseHelmHeld = false;
    MouseHelm = 0.0f;
    SailingInput.helm = 0.0;
    if (APlayerController* PlayerController = Cast<APlayerController>(GetController()))
    {
        if (AGISHUD* BoatHUD = Cast<AGISHUD>(PlayerController->GetHUD()))
        {
            BoatHUD->TogglePauseMenu();
        }
    }
}
