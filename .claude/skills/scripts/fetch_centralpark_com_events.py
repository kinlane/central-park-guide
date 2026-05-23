#!/usr/bin/env python3
"""Fetch community events from centralpark.com (Metro Publisher platform).

Strategy:
  1. Pull the RSS feed at /search/event/upcoming-events/index.rss to enumerate
     unique event detail-page URLs (one feed item per occurrence; we dedupe by
     the path component, stripping the `?occ_dtstart=...` query string).
  2. Paginate the RSS until a page yields no new event URLs.
  3. For each unique event URL, fetch the detail page and parse:
       - title          (og:title or <h1>)
       - description    (combined article body paragraphs)
       - location       (itemprop="name" inside itemprop="location")
       - coordinates    (itemprop="latitude" / "longitude")
       - schedule       (parsed "Schedule" section bullets, keyed by weekday
                          where possible; fallback to a single "schedule" string)
       - meeting_points (parsed "Meet at ..." references from schedule bullets,
                          keyed by weekday)
       - cost           (parsed Cost / Pricing paragraph)
       - image_url      (og:image)
       - tags           (the `aside.tags` block)
       - start_date / end_date (schema.org itemprop dates)
       - recurrence     (derived from schedule weekday coverage)
  4. Write a flat JSON LIST to _data/centralpark-com-events.json, sorted by
     title for stable diffs.

This is tolerant of varied page structures: anything that fails to parse is
simply absent from that record. Polite 0.5s delay between detail fetches.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
BASE = "https://www.centralpark.com"
RSS_PATH = "/search/event/upcoming-events/index.rss"
LISTING_PATH = "/search/event/upcoming-events/"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
OUT_PATH = os.path.join(REPO_ROOT, "_data", "centralpark-com-events.json")

REQUEST_TIMEOUT = 30
DETAIL_DELAY_SEC = 0.5
MAX_RSS_PAGES = 40  # safety cap; recurring events can span many pages of occurrences

WEEKDAY_TOKENS = {
    "sunday": "sundays",
    "sundays": "sundays",
    "monday": "mondays",
    "mondays": "mondays",
    "tuesday": "tuesdays",
    "tuesdays": "tuesdays",
    "wednesday": "wednesdays",
    "wednesdays": "wednesdays",
    "thursday": "thursdays",
    "thursdays": "thursdays",
    "friday": "fridays",
    "fridays": "fridays",
    "saturday": "saturdays",
    "saturdays": "saturdays",
}


def fetch(url):
    req = Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml,application/rss+xml;q=0.9,*/*;q=0.8",
    })
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        raw = resp.read()
        # Try utf-8 first, fall back to latin-1 if needed.
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")


def canonical_event_url(link):
    """Strip the ?occ_dtstart=... query string so recurring occurrences collapse
    to one URL per event."""
    parsed = urllib.parse.urlparse(link)
    return urllib.parse.urlunparse(parsed._replace(query="", fragment=""))


def discover_event_urls_via_rss():
    """Walk the paginated RSS feed; return a list of unique detail-page URLs in
    the order they're first seen."""
    seen = set()
    ordered = []
    for page in range(1, MAX_RSS_PAGES + 1):
        url = f"{BASE}{RSS_PATH}" + (f"?page={page}" if page > 1 else "")
        try:
            xml_text = fetch(url)
        except (HTTPError, URLError) as exc:
            print(f"  RSS page {page} fetch failed: {exc}", file=sys.stderr)
            break
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            print(f"  RSS page {page} parse failed: {exc}", file=sys.stderr)
            break
        items = root.findall(".//item")
        if not items:
            break
        new_on_page = 0
        for item in items:
            link_el = item.find("link")
            if link_el is None or not link_el.text:
                continue
            canon = canonical_event_url(link_el.text.strip())
            if canon in seen:
                continue
            seen.add(canon)
            ordered.append(canon)
            new_on_page += 1
        print(f"  RSS page {page}: {len(items)} items, +{new_on_page} new unique events (total {len(ordered)})")
        if new_on_page == 0:
            # Page returned no new events — we've cycled through.
            break
    return ordered


def discover_event_urls_via_html():
    """Fallback when RSS fails. Scrape the listing HTML for /events/{slug}/
    anchors."""
    seen = set()
    ordered = []
    href_re = re.compile(r'href="(/events/[^"#?]+/)"')
    for page in range(1, MAX_RSS_PAGES + 1):
        url = f"{BASE}{LISTING_PATH}" + (f"?page={page}" if page > 1 else "")
        try:
            html = fetch(url)
        except (HTTPError, URLError) as exc:
            print(f"  HTML page {page} fetch failed: {exc}", file=sys.stderr)
            break
        new = 0
        for path in href_re.findall(html):
            canon = canonical_event_url(BASE + path)
            if canon in seen:
                continue
            seen.add(canon)
            ordered.append(canon)
            new += 1
        print(f"  HTML page {page}: +{new} new")
        if new == 0:
            break
    return ordered


# ---------------------------------------------------------------------------
# Detail-page parsing helpers (regex-based; resilient to small markup shifts).
# ---------------------------------------------------------------------------

META_RE_TEMPLATE = r'<meta[^>]*property="{0}"[^>]*content="([^"]*)"'
META_NAME_RE_TEMPLATE = r'<meta[^>]*name="{0}"[^>]*content="([^"]*)"'
ITEMPROP_META_RE_TEMPLATE = r'<meta[^>]*itemprop="{0}"[^>]*content="([^"]*)"'


def find_meta(html, prop):
    m = re.search(META_RE_TEMPLATE.format(re.escape(prop)), html)
    return unescape(m.group(1)).strip() if m else None


def find_meta_name(html, name):
    m = re.search(META_NAME_RE_TEMPLATE.format(re.escape(name)), html)
    return unescape(m.group(1)).strip() if m else None


def find_itemprop_meta(html, prop):
    m = re.search(ITEMPROP_META_RE_TEMPLATE.format(re.escape(prop)), html)
    return unescape(m.group(1)).strip() if m else None


def find_itemprop_time(html, prop):
    """Match <time itemprop="startDate" datetime="2026-05-22T00:00:00">."""
    pat = r'<time[^>]*itemprop="' + re.escape(prop) + r'"[^>]*datetime="([^"]*)"'
    m = re.search(pat, html)
    return m.group(1) if m else None


def strip_tags(s):
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_location(html):
    """Pull the `Location` panel's itemprop=name + lat/lng. Centralpark.com
    renders this twice — once in the header, once in the sidebar. Either works."""
    # The sidebar block starts with `<label class="location">Location</label>`.
    m = re.search(
        r'<label class="location">Location</label>.*?'
        r'<span\s+itemprop="name"\s*>([^<]+)</span>',
        html, re.DOTALL,
    )
    if not m:
        # Header variant.
        m = re.search(
            r'itemprop="location"[^>]*>.*?<span[^>]*itemprop="name"\s*>([^<]+)</span>',
            html, re.DOTALL,
        )
    return unescape(m.group(1)).strip() if m else None


def extract_coordinates(html):
    lat = find_itemprop_meta(html, "latitude")
    lng = find_itemprop_meta(html, "longitude")
    if lat and lng:
        try:
            return {"lat": float(lat), "lng": float(lng)}
        except ValueError:
            return None
    return None


def extract_article_body(html):
    """Concatenate text from <h2>, <h3>, <p>, <ul><li> inside the article
    content area for use as `description` (capped at ~1500 chars)."""
    # Narrow to the content carousel block where the article body lives.
    m = re.search(
        r'<div id="content"[^>]*>(.*?)<div id="backlink_container"',
        html, re.DOTALL,
    )
    body_html = m.group(1) if m else html
    paras = []
    for tag in re.finditer(r"<(p|h2|h3|li)\b[^>]*>(.*?)</\1>", body_html, re.DOTALL):
        text = strip_tags(tag.group(2))
        if text and len(text) > 1:
            paras.append(text)
    text = " ".join(paras)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1500] if text else None


def extract_schedule_bullets(html):
    """Pull <li> items from the Schedule/Locations <ul>. Returns a list of
    plain-text bullets and the parent section title (if found)."""
    # Metro Publisher injects `&#13;` carriage-return entities between block
    # elements, sometimes multiple in a row. Match any run of whitespace +
    # &#13; tokens between the </h3> and the <ul>.
    sep = r'(?:\s|&\#13;)*'
    m = re.search(
        r'<h3[^>]*>\s*<strong>\s*Schedule(?:\s*&amp;\s*Locations)?\s*</strong>\s*</h3>'
        + sep + r'<ul>(.*?)</ul>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if not m:
        # More permissive fallback — any h3 whose text contains "Schedule".
        m = re.search(
            r'<h3[^>]*>(?:<[^>]+>|[^<])*Schedule(?:<[^>]+>|[^<])*</h3>'
            + sep + r'<ul>(.*?)</ul>',
            html, re.DOTALL | re.IGNORECASE,
        )
    if not m:
        return []
    bullets = []
    for li in re.finditer(r"<li[^>]*>(.*?)</li>", m.group(1), re.DOTALL):
        bullets.append(strip_tags(li.group(1)))
    return bullets


def parse_schedule_and_meeting_points(bullets):
    """For each schedule bullet, try to identify the weekday and the
    time/meeting-point. Returns (schedule_dict, meeting_points_dict). When
    nothing structured is found, returns ({}, {})."""
    schedule = {}
    meeting_points = {}
    for line in bullets:
        lower = line.lower()
        days_hit = []
        for tok, key in WEEKDAY_TOKENS.items():
            if re.search(r"\b" + re.escape(tok) + r"\b", lower):
                if key not in days_hit:
                    days_hit.append(key)
        if not days_hit:
            continue
        # Only consider the portion of the bullet BEFORE the first period —
        # that's the lead clause with the day + time. The follow-on sentences
        # ("If you do the 7:30 AM walk..." / "Friday walks are led by...") get
        # parsed separately below.
        head = line.split(".", 1)[0]
        # Time(s) like "7:30 AM" or "7:30 AM and 9:30 AM" — dedupe while
        # preserving order.
        raw_times = re.findall(r"\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)", head)
        seen_t = set()
        times = []
        for t in raw_times:
            tk = t.upper().replace(" ", "")
            if tk not in seen_t:
                seen_t.add(tk)
                times.append(t.strip())
        time_str = " & ".join(times) if times else None

        # Meeting place: "Meet at <Name> (...)" — capture the name and any
        # parenthesised street reference that follows.
        meet_match = re.search(
            r"Meet at\s+([^.(]+?)(?:\s*\(([^)]+)\))?(?:\.|$)",
            line, re.IGNORECASE,
        )
        meet_str = None
        if meet_match:
            name = meet_match.group(1).strip()
            paren = (meet_match.group(2) or "").strip()
            meet_str = f"{name} ({paren})" if paren else name

        # "led by Ms. Deborah Allen" — period-tolerant capture (matches the
        # honorific dot in "Mr." / "Ms." / "Dr." without ending the name).
        led_by = re.search(
            r"led by\s+((?:[A-Z][a-z]+\.?\s+)+[A-Z][A-Za-z'-]+)",
            line,
        )
        for key in days_hit:
            entry = time_str or ""
            if led_by:
                entry = f"{entry} (led by {led_by.group(1).strip()})".strip()
            if entry:
                schedule[key] = entry
            if meet_str:
                meeting_points[key] = meet_str
    return schedule, meeting_points


def extract_cost(html):
    """Look for a paragraph beginning with <strong>Cost</strong> (or 'Price'
    or 'Admission'). Returns the post-colon text."""
    m = re.search(
        r'<p[^>]*>\s*<strong>\s*(?:Cost|Price|Admission)\s*</strong>\s*:?\s*(.*?)</p>',
        html, re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return None
    return strip_tags(m.group(1))


def extract_tags(html):
    """Pull anchor text from `<aside class="tags">` block."""
    m = re.search(r'<aside class="tags">(.*?)</aside>', html, re.DOTALL)
    if not m:
        return []
    tags = re.findall(r'rel="tag"[^>]*>([^<]+)</a>', m.group(1))
    # Drop the "Annual Events 2026"-style year tags; not useful downstream.
    cleaned = []
    for t in tags:
        t = unescape(t).strip()
        if not t:
            continue
        if re.fullmatch(r"Annual Events \d{4}", t):
            continue
        cleaned.append(t)
    return cleaned


def derive_recurrence(schedule):
    """Build a plain-English recurrence string from the schedule weekday set."""
    if not schedule:
        return None
    order = ["mondays", "tuesdays", "wednesdays", "thursdays",
             "fridays", "saturdays", "sundays"]
    pretty = {"mondays": "Monday", "tuesdays": "Tuesday", "wednesdays": "Wednesday",
              "thursdays": "Thursday", "fridays": "Friday", "saturdays": "Saturday",
              "sundays": "Sunday"}
    days = [pretty[d] for d in order if d in schedule]
    if not days:
        return None
    return "Weekly - " + ", ".join(days)


def parse_detail(url, html):
    title = find_meta(html, "og:title") or None
    if not title:
        h1 = re.search(r"<h1>([^<]+)</h1>", html)
        title = unescape(h1.group(1)).strip() if h1 else None
    if not title:
        return None

    image_url = find_meta(html, "og:image")
    # Strip the resize params off the og:image so the canonical URL is stored.
    if image_url:
        image_url = re.sub(r"&(?:amp;)?w=\d+$", "", image_url)

    description = (
        find_meta(html, "og:description")
        or find_meta_name(html, "description")
        or extract_article_body(html)
    )

    location = extract_location(html)
    coordinates = extract_coordinates(html)
    bullets = extract_schedule_bullets(html)
    schedule, meeting_points = parse_schedule_and_meeting_points(bullets)
    # If we got bullets but no structured schedule, fall back to the raw bullets
    # joined as a single string so the data isn't lost.
    if bullets and not schedule:
        schedule = {"raw": " | ".join(bullets)}
    cost = extract_cost(html)
    tags = extract_tags(html)
    start_date = find_itemprop_time(html, "startDate")
    end_date = find_itemprop_time(html, "endDate")
    recurrence = derive_recurrence(schedule)

    record = {
        "title": title,
        "url": url,
        "source": "centralpark.com",
    }
    if description:
        record["description"] = description
    if location:
        record["location"] = location
    if coordinates:
        record["coordinates"] = coordinates
    if schedule:
        record["schedule"] = schedule
    if meeting_points:
        record["meeting_points"] = meeting_points
    if cost:
        record["cost"] = cost
    if tags:
        record["tags"] = tags
    if image_url:
        record["image_url"] = image_url
    if start_date:
        record["start_date"] = start_date
    if end_date and end_date != start_date:
        record["end_date"] = end_date
    if recurrence:
        record["recurrence"] = recurrence
    return record


def main():
    print("Step 1: discovering event URLs via RSS...")
    urls = discover_event_urls_via_rss()
    method = "RSS"
    if not urls:
        print("  RSS yielded zero URLs; falling back to HTML listing scrape.")
        urls = discover_event_urls_via_html()
        method = "HTML"
    if not urls:
        print("ERROR: no event URLs discovered via RSS or HTML.", file=sys.stderr)
        sys.exit(1)
    print(f"Discovered {len(urls)} unique event URLs via {method}.")

    print(f"Step 2: fetching detail pages (delay {DETAIL_DELAY_SEC}s between)...")
    events = []
    failures = []
    for i, url in enumerate(urls, 1):
        try:
            html = fetch(url)
            rec = parse_detail(url, html)
            if rec is None:
                failures.append((url, "no title parsed"))
                print(f"  [{i}/{len(urls)}] SKIP (no title): {url}")
            else:
                events.append(rec)
                print(f"  [{i}/{len(urls)}] OK: {rec['title']}")
        except (HTTPError, URLError) as exc:
            failures.append((url, str(exc)))
            print(f"  [{i}/{len(urls)}] FAIL: {url} -> {exc}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 — log and move on
            failures.append((url, repr(exc)))
            print(f"  [{i}/{len(urls)}] ERROR: {url} -> {exc!r}", file=sys.stderr)
        if i < len(urls):
            time.sleep(DETAIL_DELAY_SEC)

    # Sort by title for stable diffs.
    events.sort(key=lambda e: e.get("title", "").lower())

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print()
    print(f"Wrote {len(events)} events -> {OUT_PATH}")
    print(f"Discovery method: {method}")
    if failures:
        print(f"Failures: {len(failures)}")
        for url, err in failures:
            print(f"  - {url}: {err}")
    else:
        print("Failures: 0")


if __name__ == "__main__":
    main()
