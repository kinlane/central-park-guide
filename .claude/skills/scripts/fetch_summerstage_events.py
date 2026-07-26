#!/usr/bin/env python3
"""Fetch SummerStage events from City Parks Foundation Tribe Events REST API.

Caches Central Park-relevant events to _data/summerstage-events.json. The merge
script in merge_nyc_events.py reads from this cache.

API: https://cityparksfoundation.org/wp-json/tribe/events/v1/events
SummerStage category id: 25 (verified May 2026 — re-check if filtering changes).

Central Park filtering (rewritten 2026-07-26)
---------------------------------------------
SummerStage plays all five boroughs, and the API is useless for venue: the
`venue` object is just the borough ("Manhattan"), and most event descriptions
never name the park. The old keyword filter (title + description matched
against rumsey|central park|dana discovery|harlem meer) therefore dropped most
of the Central Park season — on 2026-07-26 it kept 7 of 33 Manhattan shows,
silently losing Blues Traveler, Chance the Rapper, Danny Elfman and the rest.

The park name IS published on each event's detail page, in two Elementor text
blocks: the park ("Central Park") followed by the address ("Rumsey Playfield,
New York, NY, 10021"). So we fetch the detail page for every upcoming event and
read the venue from it. That also correctly rejects the Manhattan-but-not-
Central-Park shows — the Charlie Parker Jazz Festival's Marcus Garvey Park and
Tompkins Square Park dates, and the CPJF ancillary events around Harlem.

The detail pages sit behind Cloudflare and 403 a bare request, but a normal
browser User-Agent + Accept headers pass. When a detail fetch fails we fall
back to the old keyword match so a bad network day degrades instead of
emptying the cache; `venue_source` on each cached record says which path ran
("detail" or "keyword-fallback").
"""
import json
import os
import re
import time
from html import unescape
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BROWSER_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
API = "https://cityparksfoundation.org/wp-json/tribe/events/v1/events"
SUMMERSTAGE_CATEGORY_ID = 25

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
OUT_PATH = os.path.join(REPO_ROOT, "_data", "summerstage-events.json")

# Venue strings that mean "this is in Central Park".
CP_PATTERNS = re.compile(
    r"rumsey|central park|dana discovery|harlem meer",
    re.IGNORECASE,
)

# A detail-page text block that looks like a venue name rather than a time,
# a price, or ad copy.
VENUE_NAME = re.compile(
    r"\b(park|playfield|playground|plaza|square|meer|bandshell|amphitheater|center|centre|field|green"
    r"|meadow|lawn|garden|oval|harbor|terrace|pier|beach|house|hall|theater|theatre)\b",
    re.IGNORECASE,
)
BLOCK_RE = re.compile(
    r'<div class="elementor-widget-container">(.*?)</div>',
    re.DOTALL,
)
TAG_RE = re.compile(r"<[^>]+>")


def fetch_page(page):
    url = f"{API}?per_page=50&page={page}&categories={SUMMERSTAGE_CATEGORY_ID}"
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def text_blocks(html):
    """Every Elementor widget's plain text, in document order."""
    out = []
    for raw in BLOCK_RE.findall(html):
        txt = unescape(TAG_RE.sub(" ", raw))
        txt = re.sub(r"\s+", " ", txt).strip()
        if txt:
            out.append(txt)
    return out


def parse_venue(html):
    """Pull (park, address) out of an event detail page.

    The page renders the park name and the street address as two consecutive
    short text widgets, e.g. "Central Park" then "Rumsey Playfield, New York,
    NY, 10021". Returns (None, None) when neither can be identified.
    """
    blocks = [b for b in text_blocks(html) if len(b) <= 90]
    candidates = []
    for i, b in enumerate(blocks):
        if not VENUE_NAME.search(b):
            continue
        # Skip obvious non-venue copy: times, prices, calls to action.
        if re.search(r"\b(doors|pm|am|\$|free|tickets?|member|donate|subscribe)\b", b, re.IGNORECASE):
            continue
        nxt = blocks[i + 1] if i + 1 < len(blocks) else ""
        addr = nxt if re.search(r"\bNY\b|\b\d{5}\b|\bStreet\b|\bAve\b|\bAvenue\b", nxt) else None
        candidates.append((b, addr))
    if not candidates:
        return None, None
    # A venue block followed by a street address is the real one; blocks with no
    # address behind them are usually ad copy that happens to contain "Park".
    for park, addr in candidates:
        if addr:
            return park, addr
    return candidates[0][0], None


def fetch_detail_venue(url):
    req = Request(url, headers=BROWSER_HEADERS)
    with urlopen(req, timeout=45) as resp:
        html = resp.read().decode("utf-8", "replace")
    return parse_venue(html)


def keyword_is_central_park(event):
    blob = (event.get("title", "") or "") + " " + (event.get("description", "") or "")
    return bool(CP_PATTERNS.search(blob))


def derive_place(venue_blob, event):
    """Map an event to a Central Park place. The merge script does the final
    vocabulary match via match_places(), so this is only a hint."""
    blob = (venue_blob or "").lower()
    if not blob:
        blob = ((event.get("title", "") or "") + " " + (event.get("description", "") or "")).lower()
    if "dana discovery" in blob or "harlem meer" in blob:
        return "Dana Discovery Center"
    # Rumsey Playfield is the main SummerStage stage in Central Park.
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

    today = time.strftime("%Y-%m-%d")
    cache = []
    unresolved = []  # venue couldn't be read — reported so drops are never silent
    stats = {"detail": 0, "keyword-fallback": 0, "detail_failed": 0, "rejected": 0, "past": 0}

    for e in all_events:
        start = (e.get("start_date") or "")[:10]
        if start and start < today:
            stats["past"] += 1
            continue

        park = address = None
        venue_source = None
        url = e.get("url")
        if url:
            try:
                park, address = fetch_detail_venue(url)
                venue_source = "detail"
                stats["detail"] += 1
            except Exception as exc:  # network, Cloudflare, layout change
                print(f"  detail fetch failed ({exc}): {url}")
                stats["detail_failed"] += 1
            time.sleep(0.4)

        venue_blob = " ".join(x for x in (park, address) if x)
        if venue_source == "detail" and venue_blob:
            keep = bool(CP_PATTERNS.search(venue_blob))
        else:
            # No usable detail page — fall back to the old title/description
            # keyword match rather than dropping or blindly keeping the event.
            venue_source = "keyword-fallback"
            stats["keyword-fallback"] += 1
            keep = keyword_is_central_park(e)
            unresolved.append((start, unescape(e.get("title", ""))[:60], "kept" if keep else "dropped"))

        if not keep:
            stats["rejected"] += 1
            continue

        cache.append({
            "id": f"summerstage-{e.get('id')}",
            "title": unescape(e.get("title", "")),
            "start_date": e.get("start_date"),
            "end_date": e.get("end_date"),
            "url": url,
            "description": unescape(re.sub(r"<[^>]+>", " ", e.get("description", "") or "")).strip(),
            "image": (e.get("image") or {}).get("url") if isinstance(e.get("image"), dict) else None,
            "cost": e.get("cost") or "",
            "venue": (e.get("venue") or {}).get("venue", ""),
            "venue_park": park,
            "venue_address": address,
            "venue_source": venue_source,
            "tags": [t.get("slug") for t in (e.get("tags") or []) if isinstance(t, dict)],
            "categories": [c.get("slug") for c in (e.get("categories") or []) if isinstance(c, dict)],
            "place_hint": derive_place(venue_blob, e),
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    print(
        f"  upcoming kept: {len(cache)} | rejected (not Central Park): {stats['rejected']} | "
        f"past skipped: {stats['past']}"
    )
    print(
        f"  venue resolved from detail page: {stats['detail'] - stats['detail_failed']} | "
        f"detail fetch failures: {stats['detail_failed']} | keyword fallbacks: {stats['keyword-fallback']}"
    )

    if unresolved:
        print(f"  no venue on detail page — decided by keyword fallback ({len(unresolved)}):")
        for start, title, verdict in unresolved:
            print(f"    {start} [{verdict}] {title}")
        print("    ^ check these by hand if a Central Park show looks missing.")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"events": cache, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f, indent=2)
    print(f"Wrote {len(cache)} events -> {OUT_PATH}")


if __name__ == "__main__":
    main()
