# Goat Island Skiff prototype implementation plan

**Goal:** Deliver a playable sailing prototype now and a source-only Unreal
project that can be imported, compiled, and refined once the editor is
available.

**Architecture:** A portable deterministic C++ solver owns boat and wind
physics. Unreal adapts that solver to an actor, camera, input, and map. A
standalone browser build offers immediate play with matching controls and map
conventions. Its JavaScript simulation is independently tuned and should not
be treated as numerically identical to the C++ solver. The existing skinned
boat FBX remains the art source.

**Constraints:** Original project `sources/` stays read-only. Lake Greenwood
shoreline art is explicitly approximate. Coefficients are tunable and are
not claimed to be measured GIS performance data. No Unreal Editor is
installed, so Unreal compile, import, PIE, and packaging are later gates.

## Tasks and checks

1. **Portable solver:** Define `State`, `Controls`, `Parameters`, wind field,
   and fixed-step `Step`; compile without Unreal headers. Test apparent wind,
   no wind, foil lift vs immersion, reversed steering astern, heel/capsize,
   deterministic gusts, and tack/jibe cases.
2. **Map contract:** Store local-metre lake polygons, islands, spawn, and
   default wind in JSON. Validate polygon closure and spawn-in-water. The
   Greenwood prototype is explicitly marked schematic.
3. **Browser game:** Implement canvas scene, controls, wind/trim/heel HUD,
   capsize/recovery and map loading. Run local automated JS scenarios and
   manually inspect a playable view.
4. **Unreal source:** Create `.uproject`, module, game mode, sailing pawn,
   camera/input, map/wind adapter, and content import guide. Compile locally
   only the portable solver; review Unreal code against official APIs.
5. **Asset handoff:** Bundle or link the existing FBX boat and six animations;
   map solver controls to the boat's rig bones and sail morph in the Unreal
   integration instructions.
6. **Final verification:** Re-run all available automated tests, check browser
   gameplay, check package contents, and list the exact Unreal Editor gates
   that remain.

## Review focus

- A tack from low speed can stop and drift astern, with correct rudder sign.
- A controlled jibe and an uncontrolled jibe differ in yaw/heel outcome.
- Wind changes smoothly in both time and space, including at zero gust.
- Raising either foil visibly reduces authority and increases leeway.
- Capsize is possible, stable once reached, and recovery restores a valid
  sailing state.
