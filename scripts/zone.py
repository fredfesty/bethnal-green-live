#!/usr/bin/env python3
"""Where is a postcode, how far from Bethnal Green tube, and which zone is that?

Looks the postcode up on postcodes.io (open data from the ONS). Used by the triage script and the
venue editor to fill a new venue's 'location' and 'zone'.

Usage
  python scripts/zone.py "E2 6NB" "E1 6QL"

Output: one JSON object per postcode:
  {"postcode", "lat", "lon", "distance_m", "zone", "source": "postcodes.io"}  or  {"postcode", "error"}
Zones: core = E2 or within 1,000 m; fringe = within 1,600 m; outer = further.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import venuelib  # noqa: E402

UA = "BethnalGreenLiveBot/0.1 (+https://github.com/fredfesty/bethnal-green-live)"


def lookup(postcode: str) -> dict:
    pc = postcode.strip().upper()
    url = "https://api.postcodes.io/postcodes/" + urllib.parse.quote(pc)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20) as r:
            res = json.load(r)["result"]
    except urllib.error.HTTPError as e:
        return {"postcode": pc, "error": "unknown postcode" if e.code == 404 else f"HTTP {e.code}"}
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        return {"postcode": pc, "error": f"lookup failed ({e})"}
    lat, lon = res["latitude"], res["longitude"]
    if lat is None or lon is None:
        return {"postcode": res["postcode"], "error": "postcode has no location"}
    dist = venuelib.distance_m(lat, lon)
    return {"postcode": res["postcode"], "lat": round(lat, 6), "lon": round(lon, 6), "distance_m": dist,
            "zone": venuelib.zone_for(res["postcode"], dist), "source": "postcodes.io"}


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    ok = True
    for pc in args:
        res = lookup(pc)
        ok &= "error" not in res
        print(json.dumps(res))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
