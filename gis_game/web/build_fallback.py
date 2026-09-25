"""Embed the default lake map for browsers opening index.html from a file."""

import json
from pathlib import Path


WEB = Path(__file__).resolve().parent
SOURCE = WEB.parent / "maps" / "greenwood_usgs.json"
DESTINATION = WEB / "fallback-map.js"


def main():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    text = "// Generated from ../maps/greenwood_usgs.json for offline file:// play.\n"
    text += "window.GISFallbackMap = " + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";\n"
    DESTINATION.write_text(text, encoding="utf-8")
    print(f"Wrote {DESTINATION} ({len(data['water_polygon'])} shoreline points)")


if __name__ == "__main__":
    main()
