#include "GISBoatAnimInstance.h"
#include "GISBoatPawn.h"
#include "GISRigSampling.h"

#include "Animation/AnimNodeBase.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimationPoseData.h"
#include "Animation/AnimationAsset.h"
#include "Animation/Skeleton.h"

namespace
{
FCompactPoseBoneIndex FindControlledBone(FPoseContext& Output, const FName BoneName)
{
    const USkeleton* Skeleton = Output.AnimInstanceProxy->GetSkeleton();
    const int32 SkeletonIndex = Skeleton
        ? Skeleton->GetReferenceSkeleton().FindBoneIndex(BoneName) : INDEX_NONE;
    return SkeletonIndex == INDEX_NONE ? FCompactPoseBoneIndex(INDEX_NONE)
        : Output.Pose.GetBoneContainer().GetCompactPoseIndexFromSkeletonIndex(SkeletonIndex);
}

void ApplyClipBone(FPoseContext& Output, UAnimSequence* Clip, const FName BoneName,
    const double Fraction, const bool bCopyCurves = false)
{
    if (!Clip)
    {
        return;
    }
    const FCompactPoseBoneIndex Bone = FindControlledBone(Output, BoneName);
    if (!Bone.IsValid())
    {
        return;
    }
    FPoseContext Sample(Output);
    FAnimationPoseData PoseData(Sample);
    Clip->GetAnimationPose(PoseData,
        FAnimExtractContext(FMath::Clamp(Fraction, 0.0, 1.0) * Clip->GetPlayLength()));
    Output.Pose[Bone] = Sample.Pose[Bone];
    if (bCopyCurves)
    {
        Output.Curve = Sample.Curve;
    }
}

void ApplyWideSailSwing(FPoseContext& Output, UAnimSequence* Clip, const float Degrees)
{
    if (!Clip)
    {
        return;
    }
    const FCompactPoseBoneIndex Bone = FindControlledBone(Output, TEXT("SailSwing"));
    if (!Bone.IsValid())
    {
        return;
    }
    const double AbsoluteDegrees = FMath::Abs(Degrees);
    if (AbsoluteDegrees <= 50.0)
    {
        ApplyClipBone(Output, Clip, TEXT("SailSwing"),
            gis_unreal::sail_clip_fraction(Degrees));
        return;
    }

    // The Blender demonstration clip ends at +/-50 degrees, while the
    // physics allows 85. Extrapolate the authored local pivot rotation so
    // the rig follows the real sheet range without losing its correct pivot.
    FPoseContext Neutral(Output);
    FPoseContext End(Output);
    FAnimationPoseData NeutralData(Neutral);
    FAnimationPoseData EndData(End);
    Clip->GetAnimationPose(NeutralData,
        FAnimExtractContext(0.5 * Clip->GetPlayLength()));
    Clip->GetAnimationPose(EndData,
        FAnimExtractContext(gis_unreal::sail_clip_fraction(Degrees) * Clip->GetPlayLength()));
    const FTransform& A = Neutral.Pose[Bone];
    const FTransform& B = End.Pose[Bone];
    const float Alpha = static_cast<float>(
        gis_unreal::sail_swing_extrapolation(Degrees));
    FTransform Swing = B;
    Swing.SetRotation(FQuat::Slerp(A.GetRotation(), B.GetRotation(), Alpha));
    Swing.SetTranslation(FMath::Lerp(A.GetTranslation(), B.GetTranslation(), Alpha));
    Output.Pose[Bone] = Swing;
}
} // namespace

FGISBoatAnimInstanceProxy::FGISBoatAnimInstanceProxy()
    : FAnimInstanceProxy()
{
}

FGISBoatAnimInstanceProxy::FGISBoatAnimInstanceProxy(UAnimInstance* Instance)
    : FAnimInstanceProxy(Instance)
{
}

void FGISBoatAnimInstanceProxy::SetControls(const float InTillerDegrees,
    const float InSailDegrees, const float InHoist, const float InRudderLift,
    const float InCenterboardLift)
{
    TillerDegrees = InTillerDegrees;
    SailDegrees = InSailDegrees;
    Hoist = InHoist;
    RudderLift = InRudderLift;
    CenterboardLift = InCenterboardLift;
}

void FGISBoatAnimInstanceProxy::SetClips(UAnimSequence* InTiller,
    UAnimSequence* InSail, UAnimSequence* InHoist,
    UAnimSequence* InRudderLift, UAnimSequence* InCenterboardLift)
{
    TillerClip = InTiller;
    SailClip = InSail;
    HoistClip = InHoist;
    RudderLiftClip = InRudderLift;
    CenterboardLiftClip = InCenterboardLift;
}

bool FGISBoatAnimInstanceProxy::Evaluate(FPoseContext& Output)
{
    Output.ResetToRefPose();
    ApplyClipBone(Output, TillerClip, TEXT("RudderYaw"),
        gis_unreal::tiller_clip_fraction(TillerDegrees));
    ApplyClipBone(Output, RudderLiftClip, TEXT("RudderBladeSlide"),
        gis_unreal::lift_clip_fraction(RudderLift));
    ApplyClipBone(Output, CenterboardLiftClip, TEXT("CenterboardSlide"),
        gis_unreal::lift_clip_fraction(CenterboardLift));
    ApplyWideSailSwing(Output, SailClip, SailDegrees);
    ApplyClipBone(Output, HoistClip, TEXT("SailHoist"),
        gis_unreal::hoist_clip_fraction(Hoist), true);
    return true;
}

UGISBoatAnimInstance::UGISBoatAnimInstance()
{
    const FString Prefix = TEXT("/Game/Boat/A_Goat_Island_Skiff_");
    TillerAsset = TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(
        Prefix + TEXT("TillerPortStarboard.A_Goat_Island_Skiff_TillerPortStarboard")));
    SailAsset = TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(
        Prefix + TEXT("TackPortToStarboard.A_Goat_Island_Skiff_TackPortToStarboard")));
    HoistAsset = TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(
        Prefix + TEXT("SailRaiseLower.A_Goat_Island_Skiff_SailRaiseLower")));
    RudderLiftAsset = TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(
        Prefix + TEXT("RudderBladeLift.A_Goat_Island_Skiff_RudderBladeLift")));
    CenterboardLiftAsset = TSoftObjectPtr<UAnimSequence>(FSoftObjectPath(
        Prefix + TEXT("CenterboardLift.A_Goat_Island_Skiff_CenterboardLift")));
}

void UGISBoatAnimInstance::NativeInitializeAnimation()
{
    Super::NativeInitializeAnimation();
    LoadedTiller = TillerAsset.LoadSynchronous();
    LoadedSail = SailAsset.LoadSynchronous();
    LoadedHoist = HoistAsset.LoadSynchronous();
    LoadedRudderLift = RudderLiftAsset.LoadSynchronous();
    LoadedCenterboardLift = CenterboardLiftAsset.LoadSynchronous();
    GetProxyOnGameThread<FGISBoatAnimInstanceProxy>().SetClips(
        LoadedTiller.Get(), LoadedSail.Get(), LoadedHoist.Get(),
        LoadedRudderLift.Get(), LoadedCenterboardLift.Get());
    UE_CLOG(!LoadedTiller || !LoadedSail || !LoadedHoist || !LoadedRudderLift ||
        !LoadedCenterboardLift, LogTemp, Warning,
        TEXT("Goat Island Skiff rig is missing one or more imported animation clips"));
}

void UGISBoatAnimInstance::NativeUpdateAnimation(float DeltaSeconds)
{
    Super::NativeUpdateAnimation(DeltaSeconds);
    if (const AGISBoatPawn* Boat = Cast<AGISBoatPawn>(GetOwningActor()))
    {
        GetProxyOnGameThread<FGISBoatAnimInstanceProxy>().SetControls(
            Boat->TillerAngleDegrees, Boat->SailSwingDegrees, Boat->SailHoist,
            Boat->RudderLift, Boat->CenterboardLift);
    }
}

FAnimInstanceProxy* UGISBoatAnimInstance::CreateAnimInstanceProxy()
{
    return new FGISBoatAnimInstanceProxy(this);
}
