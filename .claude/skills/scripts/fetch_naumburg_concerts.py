#!/usr/bin/env python3
"""Fetch Naumburg Orchestral Concerts at the Naumburg Bandshell.

Site is Squarespace; events page uses Squarespace's eventlist-event markup.
Each concert is an <article class="eventlist-event ...">.

Output: _data/naumburg-events.json
"""
import json
import os
import re
import time
from html import unescape
from urllib.request import Request, urlopen

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
URL = "https://naumburgconcerts.org/concerts/"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
OUT_PATH = os.path.join(REPO_ROOT, "_data", "naumburg-events.json")

ARTICLE_RE = re.compile(
    r'<article[^>]*class="[^"]*eventlist-event[^"]*"[^>]*>(.*?)</article>',
    re.DOTALL,
)
TITLE_RE = re.compile(
    r'<a href="([^"]+)" class="eventlist-title-link">([^<]+)</a>',
    re.DOTALL,
)
DATE_RE = re.compile(r'<time class="event-date" datetime="([^"]+)"')
TIME12_RE = re.compile(r'<time class="event-time-localized"[^>]*>\s*([^<]+?)\s*</time>')
THUMB_RE = re.compile(r'data-image="([^"]+)"')


def fetch(url):
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse(html):
    events = []
    for block in ARTICLE_RE.findall(html):
        tm = TITLE_RE.search(block)
        if not tm:
            continue
        href, title = tm.group(1), unescape(tm.group(2)).strip()
        dm = DATE_RE.search(block)
        if not dm:
            continue
        time_m = TIME12_RE.search(block)
        thumb = THUMB_RE.search(block)
        events.append({
            "id": "naumburg-" + re.sub(r"[^a-z0-9]+", "-", href.lower()).strip("-"),
            "url": "https://naumburgconcerts.org" + href if href.startswith("/") else href,
            "title": title,
            "date": dm.group(1),
            "time_display": time_m.group(1).strip() if time_m else "",
            "image": thumb.group(1) if thumb else None,
            "venue": "Naumburg Bandshell",
        })
    return events


def main():
    html = fetch(URL)
    events = parse(html)
    print(f"Parsed {len(events)} events from {URL}")
    for e in events[:10]:
        print(f"  {e['date']} {e['time_display']:12s} | {e['title']}")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"events": events, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, f, indent=2)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
