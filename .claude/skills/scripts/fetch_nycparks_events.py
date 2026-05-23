#!/usr/bin/env python3
"""Fetch Central Park events from NYC Parks Department's per-park events page.

The events are exposed as hCalendar microformat (`.vevent` divs) on
https://www.nycgovparks.org/parks/central-park/events with pagination at
/parks/central-park/events/page/N.

Each event has:
- `.vevent` wrapper
- `.summary` (title + permalink)
- `.dtstart` and `.dtend` with ISO `title=` attribute
- `.location` (venue text — used as a hint for places vocabulary)
- A category and "Free!" marker

Caches to _data/nycparks-events.json. The merge script reads from this cache.
"""
import json
import os
import re
import time
from html import unescape
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BASE = "https://www.nycgovparks.org"
PARK_PATH = "/parks/central-park/events"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
OUT_PATH = os.path.join(REPO_ROOT, "_data", "nycparks-events.json")


VEVENT_RE = re.compile(r'<div class="vevent">(.*?)</div>', re.DOTALL)
SUMMARY_RE = re.compile(r'<h4 class="summary"><a href="([^"]+)">([^<]+)</a></h4>', re.DOTALL)
# Attribute order is `title="..." class="dtstart"` on the live page (May 2026),
# so match title-then-class rather than relying on a fixed order.
DTSTART_RE = re.compile(r'title="([^"]+)"[^>]*class="dtstart"')
DTEND_RE = re.compile(r'title="([^"]+)"[^>]*class="dtend"')
LOCATION_RE = re.compile(r'<span class="location">([^<]+)</span>')
CATEGORY_RE = re.compile(r'<strong>Category:\s*</strong>([^<]+)')
FREE_RE = re.compile(r'Free!', re.IGNORECASE)
NEXT_PAGE_RE = re.compile(r'<a href="(/parks/central-park/events/page/\d+)">Next')


def fetch(path):
    url = path if path.startswith("http") else BASE + path
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_events(html):
    out = []
    for block in VEVENT_RE.findall(html):
        m = SUMMARY_RE.search(block)
        if not m:
            continue
        href, title = m.group(1), unescape(m.group(2)).strip()
        dtstart = DTSTART_RE.search(block)
        dtend = DTEND_RE.search(block)
        loc = LOCATION_RE.search(block)
        cat = CATEGORY_RE.search(block)
        free = bool(FREE_RE.search(block))
        if not dtstart:
            continue
        out.append({
            "id": "nycparks-" + re.sub(r"[^a-z0-9]+", "-", href.lower()).strip("-"),
            "url": BASE + href if href.startswith("/") else href,
            "title": title,
            "start_date": dtstart.group(1),
            "end_date": dtend.group(1) if dtend else None,
            # NYC Parks suffixes every location with "(in Central Park)" — strip
            # it so the merge script's match_places() sees the clean venue name.
            "location": re.sub(r"\s*\(in Central Park\)\s*$", "",
                               unescape(loc.group(1)).strip()) if loc else "Central Park",
            "category": unescape(cat.group(1)).strip() if cat else "",
            "free": free,
        })
    return out


def main():
    page_path = PARK_PATH
    all_events = []
    seen_ids = set()
    page_num = 0
    while page_path and page_num < 20:  # safety cap
        page_num += 1
        print(f"  fetching page {page_num}: {page_path}")
        html = fetch(page_path)
        events = parse_events(html)
        new = 0
        for e in events:
            if e["id"] in seen_ids:
                continue
            seen_ids.add(e["id"])
            all_events.append(e)
            new += 1
        print(f"    +{new} new")
        m = NEXT_PAGE_RE.search(html)
        if not m or page_num >= 20:
            break
        page_path = m.group(1)
        time.sleep(0.3)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"events": all_events, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f, indent=2)
    print(f"Wrote {len(all_events)} events -> {OUT_PATH}")


if __name__ == "__main__":
    main()
