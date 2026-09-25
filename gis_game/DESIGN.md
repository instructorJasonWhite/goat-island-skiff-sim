# Goat Island Skiff sailing game: prototype design

## Intended experience

Sail the Goat Island Skiff on a Lake Greenwood course. A person can steer,
trim the balanced lug sail, shift crew weight,
raise the centerboard and sliding rudder, lower the sail, and recover after a
capsize. The boat responds continuously to wind and water: a slow tack can
stall in irons, a run and a jibe can produce a sudden heel, and poor trim or
crew placement can capsize it. The initial target is a Windows desktop game
in Unreal Engine. The bundled browser version is a playable tuning and
demonstration build while the Unreal Editor is unavailable here. Its default
camera is a close third-person view behind the sailor, with an F-key
first-person toggle. This browser view uses Canvas perspective drawing; the
Unreal boat asset is a separate deliverable.

"Yawl" in the request was clarified to mean yawing motion, not a second mast.

## Simulation design

- Use local metres and a fixed substep. The boat state contains planar
  position/velocity, heading/yaw rate, heel/roll rate, and capsize state.
- Derive sail forces from apparent wind at the sail's center of effort, with
  trim-dependent angle of attack, lift/drag, stall, and a force moment at the
  boat center of gravity.
- Derive centerboard and rudder lift/drag from water relative velocity at
  each foil. Lifting a foil reduces immersed area; steering weakens at low
  speed and changes sign when the boat moves astern.
- Hull resistance includes longitudinal and lateral drag. Do not impose a
  fixed displacement-hull speed limit because the GIS can plane.
- Heel results from sail moment, gravity/righting moment, damping, and
  movable crew mass. Capsize follows from passing a stability threshold;
  recovery is a deliberate control for this prototype.
- Wind has a prevailing direction and speed plus deterministic, spatially
  continuous advected gusts and veer. Avoid independent per-frame randomness.
- In irons is a measured condition shown in the HUD, not an artificial halt.
  It can arise from low drive near head to wind and low rudder authority.

The force formulas follow published foil/sailing research, but coefficients,
gust strength, planing transition, and righting curve are initial tuning
assumptions. The game does not claim a validated polar diagram or measured
GIS capsize threshold.

## World and controls

Maps are data files with local-metre water polygons, islands, spawn point,
and wind defaults. The default `maps/greenwood_usgs.json` comes from the USGS
National Hydrography Dataset Lake Greenwood waterbody feature. It has 13,714
outer shoreline vertices and 35 island rings, and is included for direct-file
offline browser play. `maps/greenwood_prototype.json` remains an original
schematic course. The displayed map source and navigation notice follow the
loaded lake. The GIS outline is not for navigation: it contains no measured
depths, hazards, currents, water-level updates, bridge clearances, or live
weather. Land appearance is procedural game art.

Desktop controls: tiller, sail sheet, crew shift, centerboard, rudder blade,
sail hoist, camera toggle, pause, and capsize recovery. The browser build
includes an onscreen control list and a wind/point-of-sail/speed/heel HUD.
A moving wake, shoreline, minimap, and distance counter make travel visible.
The Unreal project uses the previously delivered seven-part skeletal boat
and its 14 bones and `Furled` sail morph. Moving rope spans use its helper
bones as endpoints.

## Deliverables and gates

1. Portable C++ simulation with deterministic scenario tests.
2. Playable, offline-capable browser prototype using the same map contract
   and sailing behaviors, with close third-person and first-person Canvas
   views. Its JavaScript physics is a separate, uncalibrated approximation;
   the C++ solver is authoritative for the Unreal project.
3. Unreal C++ project source with boat pawn, wind and map setup, input,
   simulation bridge, and instructions for importing the existing FBX asset.
4. Scenario checks: no wind, close-hauled/beam/broad/run trim, fast and slow
   tack, controlled and uncontrolled jibe, foils raised, crew shift, gust,
   capsize/recovery, and deterministic repeatability.

There is no Unreal Editor or existing `.uproject` on this computer. C++
source and the portable solver can be tested locally; Unreal import,
compilation, play-in-editor, and packaging require an installed editor.

## Source notes

- [GIS dimensions and rig notes](https://www.fyneboatkits.co.uk/kits/sailing/goat-island-skiff/)
- [Sailboat foil-force model](https://ceur-ws.org/Vol-2331/paper3.pdf)
- [Dinghy performance and righting model](https://strathprints.strath.ac.uk/59980/1/Day_OE_2017_Performance_prediction_for_sailing_dinghies.pdf)
- [Dinghy points of sail and maneuver guidance](https://www.cal-sailing.org/images/official_files/Dinghy17.pdf)
- [Lake Greenwood general facts](https://www.dnr.sc.gov/water/lakes/greenwood.pdf)
