#!/usr/bin/env python3
"""Fetch Central Park Conservancy events from centralparknyc.org.

The Conservancy publishes its full activity catalog (events, tours, exhibits,
etc.) at ``https://www.centralparknyc.org/activities.json``. The endpoint is
paginated (16 items per page) and we follow ``meta.pagination.links.next``
until it disappears.

We keep only items whose ``type`` field contains ``Event`` (covers "Events",
"Benefit Events", "Arts & Entertainment, Events", "Events, Activities"), then
fetch each event's detail page to harvest:

* ``schema_org`` -- the JSON-LD ``Event``-typed block on the page
* ``detail_page_data`` -- best-effort dict with ``location_detail``,
  ``date_detail``, ``time_detail``, ``cost``, ``description_detail``,
  ``duration``, ``organizer``, ``status`` (keys are omitted when not found)
* ``meta`` -- ``og_title``/``og_description``/``og_url`` from the
  ``<meta property="og:..."`` tags on the detail page

The listing-level fields are preserved verbatim (renamed to snake_case to
match the prior cache shape: ``thumbnailSrc`` -> ``image.thumbnail`` etc.).

Output is written to ``_data/central-park-conservancy-events.json`` and is the
sole input the merge step reads -- no other files are touched here.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
API = "https://www.centralparknyc.org/activities.json"
PER_PAGE = 16
DETAIL_DELAY_SEC = 0.5

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
OUT_PATH = os.path.join(REPO_ROOT, "_data", "central-park-conservancy-events.json")


# ---------------------------------------------------------------------------
# HTTP

def fetch_text(url: str, accept: str = "text/html") -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url: str) -> dict:
    return json.loads(fetch_text(url, accept="application/json"))


# ---------------------------------------------------------------------------
# Listing

def is_event_type(type_str: str) -> bool:
    """Conservancy `type` field is comma-separated; match any "Event" token."""
    if not type_str:
        return False
    return "event" in type_str.lower()


def normalize_listing(item: dict) -> dict:
    """Map the API's camelCase listing fields to the cache's snake_case shape."""
    return {
        "id": item.get("id"),
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "type": item.get("type", ""),
        "tags": item.get("tags", []) or [],
        "summary": item.get("summary", "") or "",
        # `description` is the listing-level description; we mirror summary
        # when the listing omits an explicit field (the API typically gives
        # us only `summary`). The detail page's schema.org description wins
        # downstream and ends up under schema_org.description.
        "description": item.get("description") or item.get("summary", "") or "",
        "image": {
            "og_image": "",
            "schema_image": "",
            "thumbnail": item.get("thumbnailSrc", "") or "",
            "thumbnail_srcset": item.get("thumbnailSrcset", "") or "",
        },
        "start_date": item.get("startDate"),
        "event_instances": item.get("eventInstances", []) or [],
        "nested_instances": item.get("nestedInstances", {}) or {},
        "meta": {"og_title": "", "og_description": "", "og_url": ""},
        "schema_org": None,
        "detail_page_data": {},
    }


def fetch_all_listings() -> tuple[list[dict], dict]:
    """Walk the paginated JSON feed; return (raw event-typed items, last meta)."""
    page_url = f"{API}?page=1"
    events: list[dict] = []
    last_meta: dict = {}
    pages_fetched = 0
    while page_url:
        payload = fetch_json(page_url)
        last_meta = payload.get("meta", {}) or {}
        for item in payload.get("data", []) or []:
            if is_event_type(item.get("type", "")):
                events.append(item)
        pages_fetched += 1
        next_url = (
            (last_meta.get("pagination", {}) or {})
            .get("links", {})
            .get("next")
        )
        page_url = next_url
    return events, last_meta


# ---------------------------------------------------------------------------
# Detail-page parsing

META_OG_RE = re.compile(
    r'<meta\s+[^>]*\bcontent="([^"]*)"[^>]*\bproperty="og:([^"]+)"',
    re.IGNORECASE,
)
META_OG_REVERSE_RE = re.compile(
    r'<meta\s+[^>]*\bproperty="og:([^"]+)"[^>]*\bcontent="([^"]*)"',
    re.IGNORECASE,
)
JSONLD_RE = re.compile(
    r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
H3_BLOCK_RE = re.compile(
    r'<h3[^>]*>([^<]+)</h3>(.*?)(?=<h3\b|</section\b|</article\b|<footer\b)',
    re.DOTALL | re.IGNORECASE,
)
STRONG_PAIRS_RE = re.compile(
    r'<strong>([^<:]+):?\s*</strong>\s*([^<]+(?:<(?!strong|/p)[^>]+>[^<]*)*)',
    re.IGNORECASE,
)


def collect_og_meta(html: str) -> dict:
    out: dict[str, str] = {}
    for m in META_OG_RE.finditer(html):
        content, key = m.group(1), m.group(2).lower()
        out.setdefault(key, unescape(content).strip())
    for m in META_OG_REVERSE_RE.finditer(html):
        key, content = m.group(1).lower(), m.group(2)
        out.setdefault(key, unescape(content).strip())
    return out


def extract_event_jsonld(html: str) -> Any:
    """Return the first @type=='Event' object found in any JSON-LD block."""
    for raw in JSONLD_RE.findall(html):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        # JSON-LD can be a single object, an @graph array, or a top-level list
        candidates: list[Any] = []
        if isinstance(parsed, list):
            candidates.extend(parsed)
        elif isinstance(parsed, dict):
            graph = parsed.get("@graph")
            if isinstance(graph, list):
                candidates.extend(graph)
            else:
                candidates.append(parsed)
        for obj in candidates:
            if isinstance(obj, dict):
                t = obj.get("@type")
                if t == "Event" or (isinstance(t, list) and "Event" in t):
                    return obj
    return None


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_h3_sections(html: str) -> dict[str, str]:
    """Pull text under each <h3>Label</h3> until the next h3/section close."""
    out: dict[str, str] = {}
    for m in H3_BLOCK_RE.finditer(html):
        label = m.group(1).strip()
        body = strip_tags(m.group(2))
        if body:
            out[label.lower()] = body
    return out


def parse_strong_labeled_paragraph(html: str) -> dict[str, str]:
    """Find <p> blocks containing <strong>Label:</strong> value pairs.

    Conservancy detail pages embed canonical event metadata as a single
    paragraph at the top of the event-info column, e.g.::

        <p><strong>Date: </strong>May 30, 2026, 11:00 am-1:00 pm<br>
           <strong>Starting location:</strong> West 85th Street...</p>
    """
    out: dict[str, str] = {}
    # Restrict to paragraphs that contain at least one <strong> tag.
    for p in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.DOTALL | re.IGNORECASE):
        body = p.group(1)
        if "<strong>" not in body.lower():
            continue
        # Split the paragraph by <br> separators to keep label/value pairs together.
        chunks = re.split(r"<br\s*/?>", body, flags=re.IGNORECASE)
        for chunk in chunks:
            m = re.search(
                r"<strong>\s*([^<:]+?)\s*:?\s*</strong>\s*(.*)",
                chunk,
                re.IGNORECASE | re.DOTALL,
            )
            if not m:
                continue
            label = strip_tags(m.group(1)).rstrip(":").strip().lower()
            value = strip_tags(m.group(2)).strip()
            if label and value and label not in out:
                out[label] = value
    return out


def first_present(d: dict[str, str], keys: list[str]) -> str | None:
    for k in keys:
        v = d.get(k)
        if v:
            return v
    return None


def extract_main_description(html: str, schema_obj: dict | None) -> str | None:
    """Pick a one-sentence-ish description.

    Order of preference: og:description, schema.org description, first <p>
    in the main content area that isn't site chrome.
    """
    if schema_obj:
        d = schema_obj.get("description")
        if isinstance(d, str) and d.strip():
            return d.strip()
    og = collect_og_meta(html).get("description")
    if og:
        return og
    # Last resort: first sufficiently long paragraph excluding boilerplate.
    for m in re.finditer(r"<p[^>]*>([^<]{60,800})</p>", html):
        txt = unescape(m.group(1)).strip()
        if not txt:
            continue
        lower = txt.lower()
        if any(
            bad in lower
            for bad in ("cookie", "newsletter", "central park is located")
        ):
            continue
        return txt
    return None


def derive_detail_page_data(html: str, schema_obj: dict | None) -> dict[str, str]:
    """Best-effort extract of the fixed key set the cache expects."""
    h3 = parse_h3_sections(html)
    strong = parse_strong_labeled_paragraph(html)

    detail: dict[str, str] = {}

    # date_detail: prefer "When" h3, fall back to a "Date:" strong-labeled value
    date_val = first_present(h3, ["when", "date"]) or first_present(
        strong, ["date", "when"]
    )
    if date_val:
        detail["date_detail"] = date_val

    # time_detail
    time_val = first_present(h3, ["time", "hours"]) or first_present(
        strong, ["time", "hours", "start time"]
    )
    if time_val:
        detail["time_detail"] = time_val

    # location_detail
    loc_val = first_present(h3, ["location", "where"]) or first_present(
        strong,
        [
            "location",
            "starting location",
            "meeting location",
            "where",
            "meet at",
        ],
    )
    if loc_val:
        detail["location_detail"] = loc_val

    # cost
    cost_val = first_present(h3, ["cost", "price", "admission"]) or first_present(
        strong, ["cost", "price", "admission", "tickets"]
    )
    if cost_val:
        detail["cost"] = cost_val

    # duration
    dur_val = first_present(h3, ["duration"]) or first_present(strong, ["duration"])
    if dur_val:
        detail["duration"] = dur_val

    # organizer / host / presented by
    org_val = first_present(
        h3, ["organizer", "host", "presented by", "in partnership with"]
    ) or first_present(
        strong, ["organizer", "host", "presented by", "in partnership with"]
    )
    if not org_val and isinstance(schema_obj, dict):
        organizer = schema_obj.get("organizer")
        if isinstance(organizer, dict):
            org_val = organizer.get("name")
        elif isinstance(organizer, str):
            org_val = organizer
    if org_val:
        detail["organizer"] = org_val

    # status (event-page status -- often "Registration closed", "Sold out",
    # or schema.org eventStatus). Skip the generic accessibility "status"
    # role that wraps the success message.
    status_val = first_present(h3, ["status"])
    if not status_val:
        # Look for explicit registration-status callouts in italic/text blocks.
        m = re.search(
            r"<em>\s*\*?\s*([Rr]egistration[^<*]+)\*?\s*</em>",
            html,
        )
        if m:
            status_val = strip_tags(m.group(1))
    if not status_val and isinstance(schema_obj, dict):
        es = schema_obj.get("eventStatus")
        if isinstance(es, str):
            # schema.org URIs like https://schema.org/EventScheduled -> EventScheduled
            status_val = es.rsplit("/", 1)[-1] or es
    if status_val:
        detail["status"] = status_val

    # description_detail
    desc = extract_main_description(html, schema_obj)
    if desc:
        detail["description_detail"] = desc

    return detail


# ---------------------------------------------------------------------------
# Per-event enrichment

def enrich_event(listing_item: dict) -> tuple[dict, str | None]:
    """Normalize the listing, fetch its detail page, attach extracted fields.

    Returns ``(record, error_message_or_None)``. On detail-page error the
    record is returned with empty ``detail_page_data`` / ``schema_org`` /
    ``meta`` so the cache schema stays uniform.
    """
    record = normalize_listing(listing_item)
    url = record.get("url") or ""
    if not url:
        return record, "no detail url"

    try:
        html = fetch_text(url)
    except (HTTPError, URLError, TimeoutError) as exc:
        return record, f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 — be conservative for the cache build
        return record, f"{type(exc).__name__}: {exc}"

    og = collect_og_meta(html)
    record["meta"] = {
        "og_title": og.get("title", "") or "",
        "og_description": og.get("description", "") or "",
        "og_url": og.get("url", "") or "",
    }
    if og.get("image"):
        record["image"]["og_image"] = og["image"]

    schema_obj = extract_event_jsonld(html)
    if schema_obj is not None:
        record["schema_org"] = schema_obj
        # Surface the schema.org image URL into the image bag (prior cache shape).
        img = schema_obj.get("image") if isinstance(schema_obj, dict) else None
        if isinstance(img, dict) and isinstance(img.get("url"), str):
            record["image"]["schema_image"] = img["url"]
        elif isinstance(img, str):
            record["image"]["schema_image"] = img

    record["detail_page_data"] = derive_detail_page_data(html, schema_obj)
    return record, None


# ---------------------------------------------------------------------------
# Main

def main() -> int:
    print(f"Fetching listings from {API} ...")
    raw_events, last_meta = fetch_all_listings()
    pagination = (last_meta.get("pagination") or {}) if last_meta else {}
    total_activities = pagination.get("total") or 0
    total_pages = pagination.get("total_pages") or 0
    print(
        f"  pages fetched: {total_pages}  "
        f"site-wide activities: {total_activities}  "
        f"event-typed: {len(raw_events)}"
    )

    enriched: list[dict] = []
    failures: list[tuple[str, str]] = []
    for i, item in enumerate(raw_events, 1):
        title = item.get("title", "(untitled)")
        print(f"  [{i}/{len(raw_events)}] {title}")
        record, err = enrich_event(item)
        enriched.append(record)
        if err:
            failures.append((record.get("url", ""), err))
            print(f"      detail fetch FAILED: {err}")
        time.sleep(DETAIL_DELAY_SEC)

    out = {
        "source": "Central Park Conservancy - centralparknyc.org",
        "crawl_date": dt.date.today().isoformat(),
        "api_endpoint": API,
        "total_activities_on_site": total_activities,
        "total_events_extracted": len(enriched),
        "pagination": {
            "total_pages": total_pages,
            "items_per_page": PER_PAGE,
            "all_pages_fetched": True,
        },
        "events": enriched,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print()
    print(f"Wrote {OUT_PATH}")
    print(f"  total_events_extracted: {len(enriched)}")
    print(f"  crawl_date: {out['crawl_date']}")
    if failures:
        print(f"  detail-page failures ({len(failures)}):")
        for url, err in failures:
            print(f"    - {url}: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
