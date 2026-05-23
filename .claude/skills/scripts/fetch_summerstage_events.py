#!/usr/bin/env python3
"""Fetch SummerStage events from City Parks Foundation Tribe Events REST API.

Caches Central Park-relevant events to _data/summerstage-events.json. The merge
script in merge_nyc_events.py reads from this cache.

API: https://cityparksfoundation.org/wp-json/tribe/events/v1/events
SummerStage category id: 25 (verified May 2026 — re-check if filtering changes).

Central Park filtering: SummerStage runs at multiple boroughs; we keep only
events whose title or description mentions Rumsey Playfield, Central Park, or
the Charles A. Dana Discovery Center / Harlem Meer (the other Central Park
SummerStage stage in the park's north end).
"""
import json
import os
import re
import time
from html import unescape
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
API = "https://cityparksfoundation.org/wp-json/tribe/events/v1/events"
SUMMERSTAGE_CATEGORY_ID = 25

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
OUT_PATH = os.path.join(REPO_ROOT, "_data", "summerstage-events.json")

CP_PATTERNS = re.compile(
    r"rumsey|central park|dana discovery|harlem meer",
    re.IGNORECASE,
)


def fetch_page(page):
    url = f"{API}?per_page=50&page={page}&categories={SUMMERSTAGE_CATEGORY_ID}"
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_central_park(event):
    blob = (event.get("title", "") or "") + " " + (event.get("description", "") or "")
    return bool(CP_PATTERNS.search(blob))


def derive_place(event):
    """Map an event to a Central Park place. Coarse — we just look at title +
    description for the strongest signal. The merge script does the final
    vocabulary match via match_places() so this is only a hint."""
    blob = ((event.get("title", "") or "") + " " + (event.get("description", "") or "")).lower()
    if "dana discovery" in blob or "harlem meer" in blob:
        return "Dana Discovery Center"
    # Default — Rumsey Playfield is the main SummerStage stage in Central Park
    return "Rumsey Playfield"


def main():
    first = fetch_page(1)
    total_pages = first.get("total_pages", 1)
    total = first.get("total", 0)
    print(f"SummerStage category: {total} events across {total_pages} pages")

    all_events = first.get("events", [])
    for p in range(2, total_pages + 1):
        time.sleep(0.3)
        data = fetch_page(p)
        all_events.extend(data.get("events", []))

    cp_events = [e for e in all_events if is_central_park(e)]
    print(f"  filtered to {len(cp_events)} Central Park events")

    cache = []
    for e in cp_events:
        cache.append({
            "id": f"summerstage-{e.get('id')}",
            "title": unescape(e.get("title", "")),
            "start_date": e.get("start_date"),
            "end_date": e.get("end_date"),
            "url": e.get("url"),
            "description": unescape(re.sub(r"<[^>]+>", " ", e.get("description", "") or "")).strip(),
            "image": (e.get("image") or {}).get("url") if isinstance(e.get("image"), dict) else None,
            "cost": e.get("cost") or "",
            "venue": (e.get("venue") or {}).get("venue", ""),
            "tags": [t.get("slug") for t in (e.get("tags") or []) if isinstance(t, dict)],
            "categories": [c.get("slug") for c in (e.get("categories") or []) if isinstance(c, dict)],
            "place_hint": derive_place(e),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"events": cache, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f, indent=2)
    print(f"Wrote {len(cache)} events -> {OUT_PATH}")


if __name__ == "__main__":
    main()
