# Goat Island Skiff Sail Lab — browser prototype

Open `index.html` directly for offline play, or run the local server from
`output/gis_game`:

```powershell
node --preserve-symlinks --preserve-symlinks-main web/dev-server.cjs
```

Then open `http://127.0.0.1:8765/web/index.html`. Both methods start with the
USGS-derived Lake Greenwood shoreline. The direct-file version carries an
embedded copy; the server loads `maps/greenwood_usgs.json`. The view is a
Canvas perspective drawing of the boat and lake, with a close camera behind
the sailor and a first-person cockpit toggle. It does not render the detailed
Blender/Unreal mesh or use a 3D game engine.

## Controls

| Control | Action |
| --- | --- |
| Hold left mouse button and drag horizontally on the water | Tiller handle follows the mouse; the bow turns opposite. Release to center it. |
| Click the course map (or Map button on a small screen) | Open a three-times-larger map with the boat's position and heading; sailing pauses until you close it. |
| Mouse wheel over the water | Wheel up trims the mainsheet in; wheel down eases it |
| Left / right arrows or helm buttons | Steer port / starboard while held |
| F or the view button | Toggle close third-person and first-person views |
| W / S or sheet slider | Trim in / ease sail |
| A / D or crew slider | Shift crew port / starboard |
| C | Raise / lower centerboard |
| V | Raise / lower the sliding rudder blade |
| H | Lower / raise sail |
| R | Recover and reset the boat |
| Space | Pause / resume |

Sail around the colored buoys in order. Shoreline movement, a wake, and the
distance-sailed readout make the boat's progress visible. The minimap shows
the wider lake and course.

The wind dial keeps the bow at the top. Its arrow shows where the **apparent
wind comes from relative to the boat**, and moves as you turn or gain speed.
The number names the port or starboard angle; the smaller true-wind line keeps
the compass direction and wind speed for reference.

## Lake Greenwood map and adding lakes

The default map is derived from the USGS National Hydrography Dataset Lake
Greenwood waterbody polygon. It contains 13,714 outer shoreline vertices and
35 island rings. See `../maps/README.md` for the source feature, conversion,
and attribution. The shoreline is a mapped outline, while the land and water
appearance are game artwork. **The map is not for navigation.** It has no
soundings, shoals, hazards, bridge clearances, water-level updates, currents,
or live weather. The starting wind is a scenario setting.

Use **+ Load lake** to pick a local JSON file. With the server running, a map
can also be loaded from a same-origin relative URL, for example:

`http://127.0.0.1:8765/web/index.html?map=../maps/my_lake.json`

The game reads `id`, `name`, `approximate`, `bounds_m`, `water_polygon`,
optional `islands`, `spawn`, and `wind`. Coordinates are local metres, with
+x east and +y north. Compass headings and wind-from directions are clockwise
from north. The boat must spawn within the water polygon and outside islands.
The browser checks the basic schema; use `../maps/validate_maps.py` for fuller
validation. The original schematic course remains available as
`../maps/greenwood_prototype.json`.

## Physics and limits

The simulator uses true wind plus boat velocity to calculate apparent wind,
sail lift and drag, centerboard leeway resistance, water flow over the rudder,
yaw inertia, crew righting moment, and roll. Gusts vary smoothly over time and
space. Sail force fades in the no-go zone, so a slow tack can stall in irons.
The boom changes side as the wind crosses during a tack or jibe. Sustained
severe heel capsizes the boat; `R` recovers it.

These equations produce distinct sailing behavior but are **not calibrated**
to measured GIS sail polars, hull resistance, hydrostatics, or Lake Greenwood
wind observations. The view and map are for a game prototype, not a sailing
trainer or performance predictor.

Run the behavior checks from this `web` directory:

```powershell
node --test tests/input.test.cjs tests/physics.test.cjs tests/movement.test.cjs tests/view3d.test.cjs tests/wind_indicator.test.cjs
```
