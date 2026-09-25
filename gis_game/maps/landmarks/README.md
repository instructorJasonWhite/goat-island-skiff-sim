# Lake Greenwood landmark catalog

`greenwood_landmarks.json` is the game placement catalog. It includes 19
located features: nine road bridge inventory points, three rail crossings,
three components of Buzzards Roost Dam, and four publicly owned or state park
boat access points. `greenwood_landmarks.geojson` contains the same features
for GIS review. The [QA overview](greenwood_landmarks_overview.png) plots them
against the project's USGS lake polygon. Orange road and purple rail spans
follow transport centerlines clipped against mapped water; their endpoints are
inferred. This map is **for a visual game only and
must not be used for navigation**.

Coordinates use WGS84 longitude/latitude. The catalog's `east_m` and `north_m`
use the existing Greenwood game's equirectangular origin at
**-82.0408735°, 34.265721°**. Positive east is right; positive north is up.
For Unreal placement, the project currently maps local east to Unreal +X and
local north to Unreal -Y, then multiplies metres by 100 for centimetres.

## Sources and placement limits

| Source | Use here | Placement limit |
| --- | --- | --- |
| [SCDOT Bridges FeatureServer](https://gis.scdot.org/hosting/rest/services/Bridges/FeatureServer/4) | Bridge point and route/crossing IDs | Inventory points identify crossings, but do not specify span shape, deck height, or clearance. Public service lists no explicit redistribution license. Credit SCDOT. |
| [USGS National Transportation Dataset road layers](https://carto-wfs.nationalmap.gov/arcgis/rest/services/transportation/MapServer) | Road direction at each SCDOT bridge | Approximate deck endpoints come from clipping the nearest road centerline against the USGS water polygon at about 5 m sampling. The road source includes U.S. Census Bureau TIGER/Line geometry. Actual bridge dimensions and clearance remain unknown. |
| [SCDNR boat-ramp metadata](https://www.dnr.sc.gov/GIS/metadata/scBoatRamps.htm) and [public ArcGIS copy](https://services.arcgis.com/F7DSX1DSNSiWmOqh/arcgis/rest/services/Boat_Ramps/FeatureServer/0) | Four access locations | Source metadata dates to 2007; ArcGIS copy is from 2019. Point locations are approximate, and current access needs independent recheck. Credit SCDNR and The Nature Conservancy copy. |
| [SCDNR boating facilities guide](https://www.dnr.sc.gov/pubs/boatfacilities.pdf) | Confirms Greenwood State Park has a courtesy dock | Dock shares the ramp facility's approximate point; no separate dock footprint was supplied. |
| [U.S. Army Corps National Inventory of Dams](https://nid.sec.usace.army.mil/nid/) | Buzzards Roost spillway, embankment, fuse plug points (NID `SC00109`) | Component points do not trace the actual dam barrier or prescribe water collision geometry. |
| [USGS National Transportation Dataset railroad layer](https://carto-wfs.nationalmap.gov/arcgis/rest/services/transportation/MapServer/6) | FRA/CSX rail alignments | Three crossings were calculated by intersecting the rail lines with the USGS lake polygon at about 5 metre sampling. Two are substantial crossing candidates; one is a short inlet. Structural construction, current operability, and clearances are not independently verified. Credit USGS and FRA. |
| [USGS NHD shoreline](https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/12) | Water intersection and QA backdrop | Shoreline is a GIS polygon, not a live water level or hazard chart. Public domain; credit USGS. |

The four ramp points are listed as open in the older SCDNR-derived dataset, but
this catalog does not claim they are currently open. The 2019 copy also lists
Laurens Shrine Club (facility 30001); it is excluded because public access is
not established by the available record. Individual private docks are excluded
because no verified, licensed footprint source was found. The lake's existing
spawn is shown in white on the QA image.

## Rebuild and test

```text
python build_catalog.py --refresh
python -m unittest test_catalog.py
```

Raw service responses are not distributed in this public repository. The first
rebuild needs `--refresh` and an internet connection; later offline rebuilds
can use `python build_catalog.py` with the downloaded responses. Use `--refresh`
again to update the four lake-wide GIS extracts and nine bridge-alignment
extracts in `raw/`. The URLs, query bounds, source record
IDs, and attribution are preserved in `build_catalog.py` and the catalog. A
refresh can change a public layer's schema or point locations, so review the
QA image and tests again before updating game placement.
