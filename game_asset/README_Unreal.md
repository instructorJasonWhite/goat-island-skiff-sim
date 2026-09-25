# Goat Island Skiff: Unreal Engine handoff

This folder contains seven skinned mesh parts and six animation clips. Keep `Goat_Island_Skiff_Game.blend` as the editable source. Import `SK_Goat_Island_Skiff.fbx` as the boat's Skeletal Mesh, then import each `A_Goat_Island_Skiff_*.fbx` as an Animation Sequence using the Skeleton created by the first import. `Preview_Goat_Island_Skiff.glb` is an inspection copy. See `asset_manifest.json` for the full parts list. [Epic's skeletal mesh import guide](https://dev.epicgames.com/documentation/unreal-engine/importing-skeletal-meshes-using-fbx-in-unreal-engine) and [animation import options](https://dev.epicgames.com/documentation/unreal-engine/fbx-import-options-reference-in-unreal-engine) describe these import steps.

## Import order

1. Import `SK_Goat_Island_Skiff.fbx` with **Skeletal Mesh** and **Import Morph Targets** enabled. Let Unreal create a new Skeleton. Check the combined boat geometry, bone hierarchy, `Furled` morph target, material slots, and scale in the Skeletal Mesh Editor before importing clips.
2. Import each `A_Goat_Island_Skiff_*.fbx` with **Import Mesh** disabled, **Import Animations** enabled, and **Skeleton** set to that new boat Skeleton. Use **Exported Time** for the animation length. Import one clip per file. For `A_Goat_Island_Skiff_SailRaiseLower.fbx`, keep morph curves enabled and check that its `Furled` curve imports with the yard bone animation. [Epic's FBX morph target guide](https://dev.epicgames.com/documentation/unreal-engine/fbx-morph-target-pipeline-in-unreal-engine) explains the curve workflow.
3. Place the boat in a test level. The Blender scene was authored in metres with **+X toward the bow, +Y to starboard, +Z up**; the FBX exporter writes centimetre unit metadata. Verify the resulting size and forward direction in Unreal. If an axis or scale correction is needed, apply it consistently to the base asset and clips.
4. Import `fir_varnished_basecolor.png` if Unreal has not linked it automatically. Connect it to Base Color on the varnished fir material. Check the interior and exterior paint material slots and tune their Unreal roughness to match the intended finish. The texture is an external file, so keep it alongside the FBX package.

## Controls

The `GIS_GameRig` bones divide the boat into movable groups:

| Bone | Gameplay control |
| --- | --- |
| `Root` | Boat body and fixed mast; move the whole boat with its Actor/Pawn transform. |
| `RudderYaw` | Steer the tiller, rudder stock, and blade around the transom pintle. The supplied plan describes about 45 degrees of travel each way. |
| `RudderBladeSlide` | Raise the distinctive blade vertically inside its stock; it does not hinge upward. |
| `CenterboardSlide` | Raise/lower the centerboard vertically in its trunk. |
| `SailSwing` | Swing the balanced lug boom and sail around the fixed mast for trim, tacks, and jibes. The rig remains on its original side of the mast as it crosses the boat. |
| `SailHoist` | Lower/raise the yard. Coordinate its motion with the sail's `Furled` morph target. |

The six supplied clips are `TillerPortStarboard`, `RudderBladeLift`, `CenterboardLift`, `TackPortToStarboard`, `JibeStarboardToPort`, and `SailRaiseLower`. The last clip contains **both** `SailHoist` yard animation and a keyed `Furled` morph curve in one FBX; this pairing survived a Blender FBX export/import check.

The animation FBXs provide example travel and timing. For interactive steering and trim, create an Animation Blueprint on this Skeleton and expose `TillerAngle`, `SailAngle`, `Hoist`, `RudderLift`, and `CenterboardLift` values. Drive the corresponding bones with **Transform (Modify) Bone** nodes, or use a Control Rig with the same pivots. Inspect the imported bone axes before choosing a rotation channel; use one consistent signed convention for both tack and jibe. [Epic's Animation Blueprint guide](https://dev.epicgames.com/documentation/unreal-engine/animation-blueprints-in-unreal-engine) and [Transform Bone reference](https://dev.epicgames.com/documentation/unreal-engine/animation-blueprint-transform-bone-in-unreal-engine) cover the node setup.

Keep sail trim continuous as the sail passes across the boat. A tack and a jibe can use the same `SailSwing` angle path with different timing. Interpolate the target angle during play rather than swapping mirrored sail meshes. Drive `SailHoist` and the `Furled` morph together so the yard descends while the cloth gathers. Verify the `Furled` target and curve over the whole `SailRaiseLower` clip in Unreal; the Blender source remains the visual reference if the Unreal importer needs adjustment. Epic documents [animation curves for morph targets](https://dev.epicgames.com/documentation/unreal-engine/animation-curves-in-unreal-engine).

## Moving ropes and gameplay

The halyard, mainsheet, and downhaul each connect a fixed point to a moving spar. The rig already includes paired helper bones at those endpoints. Use their transforms directly, or add zero-offset Skeleton sockets to them, and update a spline or cable between each pair as the rig moves:

| Line | Helper bone pair |
| --- | --- |
| Halyard | `HalyardMast` / `HalyardYard` |
| Mainsheet | `SheetTraveller` / `SheetBoom` |
| Downhaul | `DownhaulDeck` / `DownhaulBoom` |
| Rudder shock cord | `ShockCordStock` / `ShockCordBlade` |

The moving spans of the halyard, downhaul, and upper mainsheet fall are intentionally absent from the art mesh; draw them from those live endpoints in Unreal. [Epic's socket guide](https://dev.epicgames.com/documentation/unreal-engine/skeletal-mesh-sockets-in-unreal-engine) describes creating and attaching sockets.

This folder is the editable visual and animation source. The playable `../gis_game/unreal` project already contains imported versions of the boat assets and uses a native animation instance to drive the tiller, sail, centerboard, sliding rudder blade, and moving rigging. Sailing forces and player input live in that game project. The FBX package was checked through a Blender import roundtrip, and the imported boat was verified in the packaged Unreal game.
