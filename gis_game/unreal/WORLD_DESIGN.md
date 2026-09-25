# Lake Greenwood Unreal world build

## Intended experience

Sail the Blender-built Goat Island Skiff in Unreal Engine 5.8.3 on a recognizable Lake Greenwood. The whole lake keeps the surveyed USGS shoreline and land elevations. The first detailed sailing area covers the main US 221 crossing, nearby rail trestles, and the existing start point; mapped bridges, the Buzzards Roost dam complex, and public access points identify the wider lake. The boat remains controllable in close third person and first person with the existing wind, foil, heel, and capsize simulation.

## Data and coordinate contract

- Retain `greenwood_usgs.json` as the shoreline and sailing boundary. It is a USGS NHD waterbody polygon, not a current water level or navigation chart.
- Use USGS 3DEP bare-earth elevation for terrain. Its geographic bounds and raster georeference must be checked against the shoreline before importing. A 2017 by 2017 sample, 16-metre local grid covers the full lake. Preserve the raw source response, R16 conversion, QA preview, acquisition URL, and vertical encoding manifest.
- Game map coordinates are metres: X east, Y north, zero near 34.265721 N, -82.0408735 E. Unreal world coordinates are centimetres: X = 100 east metres; Y = -100 north metres. North-up DEM row zero therefore appears at Unreal negative Y.
- Use a measured/estimated water datum recorded in the terrain manifest to align land and the game water plane. The bare-earth DEM does not provide lakebed bathymetry; terrain beneath the mapped lake may be lowered only as a rendering step, clearly separate from source elevations.
- Landmark locations come from verifiable public data. Store latitude/longitude, local metre position, type, source URL and confidence. Use schematic game geometry for bridges, trestles, dam, and public docks or ramps until dimensions and imagery have been checked. Do not create unverified private dock positions.

## Unreal components

1. **Boat art:** Import `SK_Goat_Island_Skiff.fbx`, fir texture, and six animation clips into `/Game/Boat`. The Pawn already loads the exact skeletal mesh path and hides primitive placeholders on success. Drive the moving rig from the Pawn's continuous tiller, board, rudder, hoist, and sail swing properties using an animation layer or C++ pose integration.
2. **Terrain:** Read the R16 and manifest from staged `Content/Data`. Build a segmented terrain surface with bounded mesh sizes and level-of-detail sampling, or import the same heightmap as a Landscape asset. Keep lake physics and shoreline collision based on the original polygon. Avoid visible terrain through the water.
3. **Water and scenery:** Apply a continuous water material to the existing mapped water tiles, blend shore colors against elevation and slope, and add vegetation with density limits around the initial sailing area. Preserve the whole-lake view at distance.
4. **Infrastructure:** Spawn named landmarks from the catalog. Align crossings with mapped road/rail bearings and water banks. Expose landmark names and source confidence to the HUD/map. Test the main crossing and dam placement against the geographic preview.
5. **Level and packaging:** Save an authored `GISLake` level and make it the default map. Keep the map JSON, terrain R16/manifest and landmark catalog staged in builds. Build and play in the installed editor, then package a Windows development build.

## Checks and limits

- Automated: projection and raster encoding tests, shoreline/terrain overlay, world data validation, portable sailing tests, Unreal C++ build, imported asset presence, and position checks for named landmarks.
- Interactive: verify boat scale/axis, animated controls, no terrain through the water, bridge/trestle/dam placement, first-person and chase cameras, steering, tack/jibe/irons/capsize, and acceptable frame time on this machine.
- Elevation is real terrain data but shoreline, structures, water level, and imagery may have different survey dates. This scene is a game world and remains unsuitable for navigation or bridge-clearance decisions.
