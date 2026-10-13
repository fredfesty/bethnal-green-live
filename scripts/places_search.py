#!/usr/bin/env python3
"""Find venues near Bethnal Green on Google Maps, through the official Places API.

Only runs when GOOGLE_MAPS_API_KEY is set (a Google Cloud key with "Places API (New)" enabled).
Without it, it prints "SKIPPED" and exits 0, and the map finder uses the open directories instead.
Scraping Google Maps pages is against Google's terms and blocked by its robots.txt: never do that.

Google's terms let us keep a place's id, but not its name, address or other details. So this script
writes nothing to the repo: it prints leads for the map finder to follow up in this run only.
Every fact in a lead file must then come from a quote on a page anyone can open (the venue's own
site, a ticket page, a directory), and the lead keeps only google_place_id from Google.

Usage
  python scripts/places_search.py                 # every type, around five points covering the area
  python scripts/places_search.py --types bar pub

Output: one JSON object per place, nearest first, after a first line that starts with "OK" or "SKIPPED":
  {"google_place_id", "name", "address", "website", "types", "business_status", "distance_m", "zone",
   "known_id", "known_where"}
known_id is set when it looks like a venue we already know (registry, watchlist, closed list, profiles).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import venuelib  # noqa: E402

ENDPOINT = "https://places.googleapis.com/v1/places:searchNearby"
FIELDS = ("places.id,places.displayName,places.formattedAddress,places.location,places.types,"
          "places.websiteUri,places.businessStatus")
TYPES = ["bar", "pub", "night_club", "karaoke", "comedy_club", "concert_hall", "performing_arts_theater",
         "event_venue", "cultural_center", "art_gallery", "movie_theater"]
# Bethnal Green tube and four points about 800 m away, each searched with a 900 m radius:
# together they cover the core and fringe zones (1,600 m).
CENTRES = [venuelib.BG_TUBE, (51.5342, -0.0549), (51.5198, -0.0549), (51.5270, -0.0433), (51.5270, -0.0665)]
RADIUS_M = 900.0


def search(key: str, centre: tuple[float, float], place_type: str) -> list[dict]:
    body = {"includedTypes": [place_type], "maxResultCount": 20,
            "locationRestriction": {"circle": {"center": {"latitude": centre[0], "longitude": centre[1]}, "radius": RADIUS_M}}}
    req = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "X-Goog-Api-Key": key, "X-Goog-FieldMask": FIELDS})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("places", [])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--types", nargs="+", default=TYPES)
    args = ap.parse_args(argv)
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        print("SKIPPED no GOOGLE_MAPS_API_KEY set; use the open directories instead")
        return 0

    known = venuelib.known_venues()
    seen: dict[str, dict] = {}
    errors = []
    for t in args.types:
        for c in CENTRES:
            try:
                places = search(key, c, t)
            except urllib.error.HTTPError as e:
                errors.append(f"{t}: HTTP {e.code} {e.read()[:200].decode(errors='replace')}")
                break  # an unknown type or a key problem: same answer for every centre
            except (urllib.error.URLError, TimeoutError, ValueError) as e:
                errors.append(f"{t}: {e}")
                continue
            for p in places:
                if p["id"] in seen:
                    seen[p["id"]]["types"] = sorted(set(seen[p["id"]]["types"]) | set(p.get("types", [])))
                    continue
                loc = p.get("location") or {}
                dist = venuelib.distance_m(loc["latitude"], loc["longitude"]) if loc else None
                name = (p.get("displayName") or {}).get("text", "")
                address = p.get("formattedAddress")
                k = venuelib.match_known(name, p.get("websiteUri"), None, known)
                seen[p["id"]] = {
                    "google_place_id": p["id"], "name": name, "address": address, "website": p.get("websiteUri"),
                    "types": p.get("types", []), "business_status": p.get("businessStatus"),
                    "distance_m": dist, "zone": venuelib.zone_for(None, dist),
                    "known_id": k["id"] if k else None, "known_where": k["where"] if k else None,
                }
    rows = sorted(seen.values(), key=lambda r: (r["distance_m"] is None, r["distance_m"] or 0))
    rows = [r for r in rows if r["distance_m"] is not None and r["distance_m"] <= venuelib.FRINGE_M]
    print(f"OK {len(rows)} places within {venuelib.FRINGE_M} m. Do not save these details: confirm each on its own page."
          + (f" Errors: {'; '.join(errors)}" if errors else ""))
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
