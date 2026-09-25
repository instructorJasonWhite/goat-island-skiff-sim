# Goat Island Skiff on Lake Greenwood

This is the Unreal Engine 5.8.3 project for the Goat Island Skiff sailing game. It includes the detailed Blender boat, a mapped Lake Greenwood shoreline, real land elevation and aerial color, and located crossings and access sites. The sailing simulation models wind, sail trim, heel, yaw, tacks, jibes, getting stuck in irons, and capsizing. The scene and infrastructure are still being developed; see [Accuracy and current limits](#accuracy-and-current-limits).

## Open the game

1. Keep this `unreal` directory beside `../sim_core`; the Unreal module compiles the shared sailing solver from there.
2. Install Unreal Engine **5.8.3**, a supported Visual Studio 2022 C++ toolchain, and a Windows SDK. Open `GISGame.uproject` and allow Unreal to compile the `GISGame` module if prompted.
3. Open the included `/Game/Maps/GISLake` level if it does not open automatically, then press **Play**. It is already the editor and game default map. The game assembles its terrain, water, landmarks, lighting, boat, and HUD when play starts.

The imported boat and environment assets are already in `Content/Boat` and `Content/Environment`. No FBX import, Animation Blueprint, or new level creation is needed. The Unreal Editor project and Windows Development package have been built and verified. To play outside the editor, package the project for Windows and run `GISGame.exe` in the generated `Windows` folder; keep that packaged folder intact so the Lake Greenwood data remains available. Packaged screenshots confirm the lake, boat, wind instrument, and both map views render.

## Sail and look around

| Input | Action |
| --- | --- |
| Hold left mouse button and drag left/right | Move the tiller handle left/right. The bow turns opposite the tiller while moving ahead. Release to center the helm input. |
| Mouse wheel up/down | Pull in / ease the mainsheet |
| M, or click the minimap | Open the full Lake Greenwood map; press M again or click X to close it |
| Tab, or click the data card's +/- button | Collapse / expand the sailing data |
| A / D; Q / E | Keyboard tiller; sheet fallback |
| J / L | Move crew weight port / starboard |
| R / F | Lower / raise centerboard |
| T / G | Lower / raise the sliding rudder blade |
| U / H | Hoist / lower the balanced lug sail |
| V | Toggle close third person / first person |
| Arrow keys; Z / X | Look around; zoom the third person camera |
| Esc, P, or click MENU | Open the pause menu. Choose Resume, Settings, or Quit to Desktop. Esc backs out of Settings or resumes sailing. |
| Backspace | Recover after capsize |

The smaller HUD card shows speed, heading, heel, wind, and control positions. The brass wind instrument keeps its apparent-wind needle relative to the bow while the compass tape scrolls under a fixed heading mark. The north-up minimap follows the boat at a closer scale; the expanded aerial map shows the whole lake, its shoreline, landmarks, and your position. The boat runs the shared sailing solver at 120 fixed steps per second. The detailed skeletal boat uses a native animation instance to combine the authored tiller, sliding blade, centerboard, sail swing, and hoist clips continuously. The `Furled` morph follows hoist, and live halyard, mainsheet, downhaul, and rudder shock cord spans follow rig helper bones. The original editable art is `../../game_asset/Goat_Island_Skiff_Game.blend`.

The Settings page changes graphics quality, windowed or borderless fullscreen display, and mouse helm sensitivity (0.50x to 2.00x). Changes take effect immediately and are saved for the next session. The pause menu stops sailing motion while it is open; clicking outside its controls does not move the tiller.

The visible tiller follows the helm hand: moving it to port makes the boat bear to starboard while moving ahead. The sail moves to the leeward side, including on a run. If a wind shift catches the sail on the windward side, the temporary backwind load can knock the boat down in a strong gust; ordinary wind leaves more time to recover. Near irons, a luffing sail does not create windward heeling lift.

## Lake data and adding maps

The default Lake Greenwood uses the [USGS NHD waterbody polygon](https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/12) for sailing limits, a **2,017 × 2,017** local grid of [USGS 3DEP](https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer) land heights at 16 m spacing, and a georeferenced **4,096 × 4,096** [USGS/USDA NAIP](https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer) aerial texture. Terrain and water sections stream around the boat. The 19 located landmarks include road bridges, rail trestles, Buzzards Roost Dam components, and public access locations. Their visual spans, piers, ramp, and courtesy dock are game approximations.

The editable GIS inputs and rebuild scripts are in `../maps/terrain`, `../maps/imagery`, and `../maps/landmarks`. Each folder has a README with its source links, acquisition details, alignment, and tests. The staged runtime files are in `Content/Data`; the water boundary is `greenwood_usgs.json`, with its associated terrain R16/manifest and landmark catalog. Map coordinates are local metres, +X east and +Y north. Unreal places them at `(100 × east, −100 × north)` centimetres.

To try another water polygon, place a contract-compatible `.json` file in `Content/Data` and set `MapFileName` in `Config/DefaultGame.ini`, or pass `?GISMap=your_lake.json` in the Unreal launch URL. Only a plain JSON filename in `Content/Data` is accepted. The current terrain, aerial texture, and landmark runtime setup is specific to **Lake Greenwood**; another lake uses the simpler water scene until matching data and placement code are added. This is the path for extending the game, not a complete map editor yet.

## Accuracy and current limits

- The shoreline, bare-earth heights, aerial pixels, and landmark positions come from public GIS sources. The 3DEP grid is hydroflattened; it contains **no lakebed bathymetry**. Water height is an estimate from the DEM, not a live gauge reading.
- Bridge deck heights, clearances, piers, dam shape, ramps, and docks are scenic geometry. Private docks, hazards, and navigable depths are not mapped. This game is **not for navigation**.
- Landmark records and alignments credit [SCDOT bridges](https://gis.scdot.org/hosting/rest/services/Bridges/FeatureServer/4), [SCDNR boat ramps](https://www.dnr.sc.gov/GIS/metadata/scBoatRamps.htm), the [USACE National Inventory of Dams](https://nid.sec.usace.army.mil/nid/), and [USGS transportation data](https://carto-wfs.nationalmap.gov/arcgis/rest/services/transportation/MapServer). Full attribution and source record IDs are in `../maps/landmarks/README.md` and `Content/Data/greenwood_landmarks.json`.
- The sailing coefficients are game tuning rather than measured Goat Island Skiff performance. Builds, staged map data, packaged startup, and rendering have been verified. Steering, sail trim, tacks, jibes, and capsize behavior have not yet had a human interactive play session.

For code checks, run `../sim_core/run_tests.cmd`, `Tests/run_coordinates.cmd`, `Tests/run_rig_sampling.cmd`, `Tests/run_hud_layout.cmd`, `Tests/run_settings_policy.cmd`, `Tests/run_map_projection.cmd`, and `Tests/run_compass_tape.cmd` from a Windows developer environment. The map-data tests are beside their rebuild scripts in `../maps`.
