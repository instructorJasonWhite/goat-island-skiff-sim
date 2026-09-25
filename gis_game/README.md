# Goat Island Skiff sailing game

This project contains a playable Unreal Engine 5.8.3 game and a simpler browser
prototype. The Unreal game uses the imported Goat Island Skiff boat, a mapped
Lake Greenwood shoreline, terrain elevations, aerial imagery, landmarks, and a
portable C++ sailing solver. Both versions let you steer, trim the mainsheet,
shift crew weight, move the centerboard and sliding rudder blade, lower the
sail, tack, jibe, and recover after a capsize.

## Play in Unreal

Install Unreal Engine **5.8.3**, a supported Visual Studio 2022 C++ toolchain,
and a Windows SDK. Keep the [`unreal`](unreal) and [`sim_core`](sim_core)
directories together, then open [`GISGame.uproject`](unreal/GISGame.uproject).
Let Unreal compile the C++ module if prompted, open the included `GISLake` map,
and press **Play**. The boat and environment assets are already in the project;
no separate FBX import is required.

The Unreal Editor project and a Windows Development package have been built and
verified. To make a portable playable build, package the project for Windows
from Unreal Editor and run `Windows/GISGame.exe` inside the resulting package.
Keep that package folder intact so the lake data and other game assets remain
available. See the [Unreal setup and controls](unreal/README.md) for details,
including the pause menu, settings, map, and sailing controls.

## Browser prototype

Open [`web/index.html`](web/index.html) in a current desktop browser. Its
offline copy of the Lake Greenwood map loads automatically. On a local web
server, the page loads
[`maps/greenwood_usgs.json`](maps/greenwood_usgs.json). See the
[browser setup](web/README.md) for the server command. The **Load lake** button
accepts another lake JSON file.

The browser opens in a close third-person, over-the-shoulder perspective;
press **F** or the view button for first person. This is Canvas perspective
art, not a rendered Unreal scene or the detailed Blender boat. A moving wake,
shoreline, minimap, speed, and distance-sailed readout show progress.
The wind dial is fixed to the bow and points toward the apparent wind source;
the true wind's compass direction remains in the readout.
Click the course map to open a three-times-larger lake view with your boat's
position and heading. Sailing pauses while the large map is open.

**Hold the left mouse button and drag left or right over the water to move
the tiller in the same direction**; the bow turns the opposite way. Release
to center it. **Scroll up to pull the mainsheet in;
scroll down to ease it.** Arrow keys or screen buttons also steer; W/S trim
and ease the sail; A/D shift the crew; C moves the centerboard; V moves the
rudder blade; H lowers or hoists the sail; R recovers at the starting point;
Space pauses. Sliders work with mouse or touch input.

The default Lake Greenwood outline is derived from a USGS National
Hydrography Dataset polygon. It has 13,714 shoreline vertices and 35 island
rings. It is more geographically faithful than the earlier schematic course,
but **not for navigation**. Water levels, depths, shoals, hazards, currents,
bridge clearances, and live weather are absent. Land appearance is procedural
game art. See the [map sources and conversion details](maps/README.md).
The browser uses its own JavaScript approximation with matching map and
control conventions; its numbers are not identical to the Unreal C++ solver.

## Add lakes

See the [map format](maps/README.md). A lake JSON file describes a water
polygon, islands, starting point, and starting wind. Use the browser's
**Load lake** button to
choose one. `maps/import_geojson.py` converts a GeoJSON shoreline to a local
metre grid; `maps/validate_maps.py` checks the result. Converted shorelines
need review before use. The earlier original schematic course remains in
`maps/greenwood_prototype.json`.

## Simulation scope

The C++ solver evaluates apparent wind at the sail, stall and drag, foil
forces from the centerboard and rudder, hull drag with a smooth planing
transition, heeling and righting from crew position, and seeded gusts that
vary smoothly with position and time. A slow tack can stall in irons, and
strong wind with poor trim or crew placement can capsize the skiff. The
browser has the same broad behaviors through a separate, simpler solver.

Boat dimensions are based on the published GIS specification; other
coefficients, crew mass, righting curve, planing transition, and gust
strength are tuning estimates. The physics are **not calibrated** to measured
GIS performance or Lake Greenwood conditions. This is a game prototype, not
a validated sailing trainer or performance predictor.

## Tests

- `sim_core/run_tests.cmd` builds and runs the portable C++ scenarios with a
  complete Visual Studio C++ toolchain on Windows.
- `node --test tests/input.test.cjs tests/physics.test.cjs tests/movement.test.cjs tests/view3d.test.cjs tests/wind_indicator.test.cjs`
  from `web` runs browser controls, sailing, motion, and view checks.
- `python -m unittest discover -s maps -p "test_*.py"` checks the map
  validator and GeoJSON converter.
- The Unreal C++ project has been compiled for Editor and Windows Development;
  the imported boat, packaged startup, and rendered map and HUD have been
  checked. The additional checks are listed in the [Unreal README](unreal/README.md).

Human play testing of every sailing maneuver and capsize case remains to be
done. The existing boat assets use a native animation instance, so no separate
Animation Blueprint setup is needed.
