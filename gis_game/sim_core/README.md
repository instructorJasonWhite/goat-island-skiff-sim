# GIS sailing simulation core

`SailingSim.h` and `SailingSim.cpp` are portable C++17 with no Unreal dependency. `step` advances one fixed physics substep (recommended 1/120 s) and returns force diagnostics for telemetry, UI, sound, and debugging. Use the state and input fields directly for the boat, boom, rudder, centerboard, and sail controls.

## Coordinates and controls

- World `x,y` are easting and northing in metres. Heading is counterclockwise from east. To convert a compass heading clockwise from north: `core_heading = 90 degrees - compass_heading`.
- Boat local `+X` is forward and `+Y` is **port**. Positive yaw turns port. Positive heel lowers the starboard rail.
- `true_wind` is the air **flow** vector in world m/s. For wind *from* the north at 6 m/s, set `{0, -6}`.
- `sheet_ease` ranges from 0 (roughly 10 degrees from centerline) to 1 (roughly 85 degrees). The sail chooses the leeward side and the boom traverses at a finite rate during a tack or jibe.
- `helm` ranges from -1 to +1. Positive deflects the rudder's trailing edge toward port and turns the boat port **when moving ahead**. Astern steering reverses from foil hydrodynamics.
- `crew_shift` is metres toward port. `centerboard`, `rudder_immersion`, and `sail_hoist` range 0 to 1. Raising either underwater blade reduces its hydrodynamic force.
- The delivered Blender boat uses local `+Y` **starboard**. The Unreal visual bridge must invert lateral motion and signs for heel and steering. The simulation's yaw convention also needs mapping to Unreal rotation conventions.

## Force model

Starting GIS figures are 4.73 m length, 1.52 m beam, 58 kg hull, and 9.75 m² sail; crew mass defaults to 80 kg. Apparent wind is sampled at the sail center of effort and includes yaw motion. The sail force uses dynamic pressure `0.5 ρ V² A`, signed lift normal to airflow, pressure drag along airflow, and a lift curve that stalls beyond about 20 degrees incidence. The drag term increases when the sail presents broadside area, giving a run pressure drive. The boom changes sides at a limited rate as apparent crosswind changes sign. Nothing sets an `in_irons` state: reduced sail drive and speed-squared rudder force let the boat become stuck naturally.

The centerboard and rudder are finite area foils. Their lift depends on local water flow, leeway, steering angle, immersion and heel; a foil can lead with either edge so the steering effect reverses astern. Hull resistance has linear and quadratic terms plus a displacement speed hump. A smooth planing fraction reduces the quadratic drag coefficient above the onset speed, while total drag continues to increase. The lateral sail and underwater forces generate yaw and heel moments. Hull and crew righting moments oppose heel. Exceeding the capsize angle (default 80 degrees) sets a sticky capsize state; the game must explicitly reset or right the boat.

Gusts use a seeded, smooth three-dimensional value-noise field over position and time. The same seed, position and time yield the same wind, allowing deterministic replay.

These coefficients are **starting estimates**, not a measured GIS velocity polar or validated hydrostatic curve. The module models four degrees of freedom in flat water. It does not yet calculate waves, pitch, surge from paddle/engine, flooding, crew motion inertia, sail cloth flex, shore wind shadow, or a righting/recovery procedure. Tune against actual GIS GPS tracks, wind measurements, heel observations, and turning tests before describing the result as a realistic sailing simulator.

## Build and test

On Windows run `run_tests.cmd`. It detects Zig 0.14+ on PATH or a complete Visual Studio C++ installation with Windows SDK/UCRT headers. The twelve deterministic tests cover rest, points of sail, wind heel direction, luffing close to the wind, downwind sail side, backwinded gust knockdown, water foils, ahead/astern steering, hiking, capsize, gust repeatability, planing, slow tack in irons, powered tack and jibe. The test source is `tests.cpp`.

The methodology follows the [ORC Velocity Prediction Program description](https://orc.org/organization/velocity-prediction-program-vpp): sail drive balances hydrodynamic drag and sail heeling moment balances righting moment. The implementation is simplified for real-time gameplay.
