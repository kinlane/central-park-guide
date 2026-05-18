#!/usr/bin/env python3
"""
Fetch the New York Cycle Club upcoming rides listing and persist a structured
cache to _data/nycc-rides.json. The cache is checked into git so the merge step
can run offline.

Pipeline:
  1. Try live fetch of https://nycc.org/upcoming-rides. Expect HTTP 403 from
     Cloudflare's managed JS challenge (same pattern as NYRR's Queue-It).
  2. Fall back to the most recent Wayback snapshot.
  3. Parse the rides table (one <tr> per ride, 8 <td> cells in order).
  4. Resolve each ride's day-of-week + "Mon DD" string into a YYYY-MM-DD date
     using a forward-only horizon (rides on the listing page are upcoming).
  5. For each ride, fetch the detail page (also via Wayback if needed) to read
     the "Meet Up" field; keep only rides where the Meet Up matches a Central
     Park place (Loeb Boathouse, Engineers' Gate, etc.).
  6. Write/refresh _data/nycc-rides.json.

Usage:
  python3 .claude/skills/scripts/fetch_nycc_rides.py            # default
  python3 .claude/skills/scripts/fetch_nycc_rides.py --wayback  # skip live attempt
  python3 .claude/skills/scripts/fetch_nycc_rides.py --no-detail # skip detail fetches; keep all rides on listing
"""

import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
PLACES_PATH = os.path.join(REPO_ROOT, '_data', 'central-park-places.yml')
NYCC_JSON_PATH = os.path.join(REPO_ROOT, '_data', 'nycc-rides.json')

LISTING_URL = 'https://nycc.org/upcoming-rides'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) '
      'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15')
WAIT_BETWEEN = 1.5  # seconds between detail fetches

CF_CHALLENGE_MARKERS = ('just a moment', 'cf-chl-', 'cloudflare', 'challenge-platform')

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'june': 6,
    'july': 7, 'august': 8, 'september': 9, 'october': 10,
    'november': 11, 'december': 12,
}


# ── Places vocabulary (for CP filter) ─────────────────────────────────
with open(PLACES_PATH) as f:
    _places_data = yaml.safe_load(f)
_place_lookup = {}
for _cat, _items in _places_data.items():
    if not isinstance(_items, list):
        continue
    for _it in _items:
        _place_lookup[_it['name'].lower()] = {'name': _it['name'], 'category': _cat}
        for _alt in _it.get('alternate_names', []) or []:
            _place_lookup[_alt.lower()] = {'name': _it['name'], 'category': _cat}
_search_tokens = sorted(_place_lookup.keys(), key=len, reverse=True)


def match_place(text):
    """Return the first matching place from the vocabulary, or None."""
    if not text:
        return None
    lo = text.lower()
    for tok in _search_tokens:
        if tok in lo:
            return _place_lookup[tok]
    return None


# ── HTTP helpers ──────────────────────────────────────────────────────

def _read_response(resp):
    data = resp.read()
    if resp.headers.get('Content-Encoding') == 'gzip':
        data = gzip.decompress(data)
    return data.decode('utf-8', errors='replace')


def _is_cf_challenge(html):
    head = html.lower()[:4000]
    return any(m in head for m in CF_CHALLENGE_MARKERS)


def fetch_url(url, timeout=15):
    """Returns (html, 'live') or (None, reason)."""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': UA, 'Accept-Encoding': 'gzip', 'Accept': 'text/html'},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = _read_response(r)
            if _is_cf_challenge(html):
                return None, 'cloudflare'
            return html, 'live'
    except urllib.error.HTTPError as e:
        return None, f'http_{e.code}'
    except Exception as e:
        return None, f'err_{type(e).__name__}'


def fetch_wayback(url, timeout=25):
    """Look up the most recent Wayback snapshot and fetch it. Returns (html, 'wayback') or (None, reason)."""
    cdx = ('https://web.archive.org/cdx/search/cdx?'
           + urllib.parse.urlencode({
               'url': url,
               'limit': '-1',
               'filter': 'statuscode:200',
               'output': 'json',
               'from': '20230101',
           }))
    try:
        req = urllib.request.Request(cdx, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rows = json.loads(_read_response(r))
    except Exception as e:
        return None, f'wayback_cdx_err_{type(e).__name__}'
    if len(rows) < 2:
        return None, 'no_wayback'
    ts = rows[-1][1]
    wb_url = f'https://web.archive.org/web/{ts}/{url}'
    html, _ = fetch_url(wb_url, timeout)
    return (html, 'wayback') if html else (None, 'wayback_fetch_fail')


def fetch_with_fallback(url, wayback_only=False, timeout=20):
    """Try live first (unless wayback_only), then Wayback."""
    if not wayback_only:
        html, src = fetch_url(url, timeout)
        if html:
            return html, src
    return fetch_wayback(url, timeout)


# ── Parsers ───────────────────────────────────────────────────────────

def _strip_wayback_chrome(html):
    return re.sub(
        r'<!--\s*BEGIN WAYBACK TOOLBAR INSERT.*?END WAYBACK TOOLBAR INSERT\s*-->',
        '', html, flags=re.S,
    )


def _strip_wb_url_prefix(url):
    """Remove a Wayback rewriter prefix from a URL. Handles three forms:
      - Absolute:  https://web.archive.org/web/{ts}/https://nycc.org/...
      - Relative:  /web/{ts}/https://nycc.org/...
      - Relative + scheme-stripped: /web/{ts}/nycc.org/...
    """
    url = re.sub(r'^https?://web\.archive\.org/web/\d+(?:im_)?/', '', url)
    url = re.sub(r'^/web/\d+(?:im_)?/', '', url)
    return url


def _text(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    s = s.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&#160;', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def parse_date(day_date_str, today=None):
    """Resolve a string like 'Sun, Feb 15' to a YYYY-MM-DD date in the
    forward-only horizon (today through today+180 days)."""
    if today is None:
        today = date.today()
    m = re.search(r'([A-Za-z]{3,9})\s+(\d{1,2})', day_date_str)
    if not m:
        return None
    mon = MONTHS.get(m.group(1).lower()[:3] if len(m.group(1)) >= 3 else m.group(1).lower())
    if not mon:
        return None
    day = int(m.group(2))
    # Pick year so the resulting date is in [today, today + 180d]
    for yr in (today.year, today.year + 1):
        try:
            cand = date(yr, mon, day)
        except ValueError:
            continue
        if today <= cand <= today + timedelta(days=210):
            return cand.isoformat()
    return None


def parse_time(time_str):
    """Normalize '08:30 AM' / '8:30AM' to '08:30' (24-hour)."""
    s = time_str.replace('&nbsp;', ' ').strip()
    m = re.match(r'(\d{1,2}):(\d{2})\s*([AaPp])', s)
    if not m:
        return None
    h, mn = int(m.group(1)), int(m.group(2))
    if m.group(3).upper() == 'P' and h < 12:
        h += 12
    if m.group(3).upper() == 'A' and h == 12:
        h = 0
    return f'{h:02d}:{mn:02d}'


def parse_listing(html, base_host='nycc.org', today=None):
    """Parse the rides table. Returns list of partial-record dicts (no Meet Up yet)."""
    html = _strip_wayback_chrome(html)
    rides = []
    for tr in re.finditer(r'<tr[^>]*>\s*<td[^>]*views-field[^>]*>.*?</tr>', html, re.S):
        block = tr.group(0)
        # Title + detail link
        title_a = re.search(r'views-field-title[^>]*>\s*<a\s+href="([^"]+)"[^>]*>(.*?)</a>',
                            block, re.S | re.I)
        if not title_a:
            continue
        href = _strip_wb_url_prefix(title_a.group(1))
        # After stripping, href may be:
        #   https://nycc.org/...  → use as-is
        #   /node/123             → prepend host
        #   nycc.org/node/123     → prepend scheme
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = f'https://{base_host}{href}'
        elif not href.startswith('http'):
            href = f'https://{href}' if '/' in href else f'https://{base_host}/{href}'
        title = _text(title_a.group(2))
        # Day/date
        day_date = re.search(r'views-field-phpcode-1[^>]*>(.*?)</td', block, re.S)
        # Time
        time_cell = re.search(r'views-field-nothing[^>]*?>(.*?)</td', block, re.S)
        # Leader
        leader = re.search(r'views-field-phpcode-2[^>]*>(.*?)</td', block, re.S)
        # Pace
        pace = re.search(r'views-field-nothing-1[^>]*>(.*?)</td', block, re.S)
        # Distance
        dist = re.search(r'views-field-field-ride-distance[^>]*>(.*?)</td', block, re.S)

        day_date_str = _text(day_date.group(1)) if day_date else ''
        time_str = _text(time_cell.group(1)) if time_cell else ''
        date_iso = parse_date(day_date_str, today=today)
        time_24 = parse_time(time_str)
        pace_str = _text(pace.group(1)) if pace else ''
        mph = None
        mph_m = re.search(r'/\s*(\d{1,2})', pace_str)
        if mph_m:
            mph = int(mph_m.group(1))

        rides.append({
            'title': title,
            'detail_url': href,
            'day_date_raw': day_date_str,
            'date': date_iso,
            'time': time_24,
            'leader': _text(leader.group(1)) if leader else '',
            'pace': pace_str,
            'mph': mph,
            'distance': _text(dist.group(1)) if dist else '',
        })
    return rides


def parse_meet_up(html):
    """Read the Meet Up location from a ride detail page.

    NYCC detail pages use a Drupal field-label / field-item pattern. Most labels
    are wrapped in <div class="field-label">Meet Up:</div> followed by
    <div class="field-items"><div class="field-item even">...</div></div>.
    """
    html = _strip_wayback_chrome(html)
    # Pattern 1: explicit "Meet Up" field label
    m = re.search(
        r'(?:field[_-]label[^>]*>\s*Meet[\s&nbsp;]*Up[^<]*</[^>]+>\s*'
        r'<[^>]*field[_-]items?[^>]*>\s*<[^>]*field[_-]item[^>]*>)(.*?)</',
        html, re.S | re.I,
    )
    if m:
        return _text(m.group(1))
    # Pattern 2: "Meet Up:" inline label in body
    m = re.search(r'Meet\s*Up[:\s]*</[^>]+>\s*<[^>]*>(.*?)</', html, re.S | re.I)
    if m:
        val = _text(m.group(1))
        if val and len(val) < 200:
            return val
    # Pattern 3: plain text "Meet Up: <value>"
    m = re.search(r'Meet\s*Up[:\s]+([^<\n]{4,200})', html, re.I)
    if m:
        return _text(m.group(1))
    return None


# ── Driver ────────────────────────────────────────────────────────────

def load_cache():
    if os.path.exists(NYCC_JSON_PATH):
        with open(NYCC_JSON_PATH) as f:
            return json.load(f)
    return {'fetched_at': None, 'fetch_source': None, 'rides': []}


def save_cache(cache, src):
    cache['fetched_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    cache['fetch_source'] = src
    with open(NYCC_JSON_PATH, 'w') as f:
        json.dump(cache, f, indent=2, sort_keys=True)
        f.write('\n')


def main(argv):
    wayback_only = '--wayback' in argv
    skip_detail = '--no-detail' in argv

    html, src = fetch_with_fallback(LISTING_URL, wayback_only=wayback_only)
    if not html:
        print(f'Listing fetch failed: {src}')
        cache = load_cache()
        cache.setdefault('rides', [])
        cache['last_error'] = src
        save_cache(cache, src or 'fail')
        return 1

    rides = parse_listing(html)
    print(f'Parsed {len(rides)} rides from listing ({src}).')

    # Forward-only filter
    today = date.today()
    rides = [r for r in rides if r.get('date') and r['date'] >= today.isoformat()]
    print(f'  {len(rides)} are in the forward window.')

    if not skip_detail:
        kept = []
        for r in rides:
            d_html, d_src = fetch_with_fallback(r['detail_url'], wayback_only=wayback_only)
            if not d_html:
                r['detail_fetch'] = d_src or 'fail'
                r['location'] = None
                r['kept'] = False
                r['filter_reason'] = 'detail_fetch_failed'
                kept.append(r)
                print(f'  ✗ detail: {r["title"][:50]} ({d_src})')
                time.sleep(WAIT_BETWEEN)
                continue
            meet_up = parse_meet_up(d_html)
            r['detail_fetch'] = d_src
            r['location'] = meet_up
            place = match_place(meet_up) if meet_up else None
            if place:
                r['place'] = place['name']
                r['place_category'] = place['category']
                r['kept'] = True
            else:
                r['kept'] = False
                r['filter_reason'] = 'no_cp_place_match'
            kept.append(r)
            mark = '✓' if r['kept'] else '·'
            print(f'  {mark} {r["title"][:48]:<48s} meet_up={meet_up or "(none)"}')
            time.sleep(WAIT_BETWEEN)
        rides = kept

    # Compute final ride list (the merge consumes `rides` directly; the merge
    # also re-validates the place match, so we include `kept: false` records for
    # diagnostic visibility but the merge will skip them).
    if not skip_detail:
        keepers = [r for r in rides if r.get('kept')]
    else:
        keepers = rides  # caller is on their own
    print(f'\nFinal: {len(keepers)} rides match a Central Park place.')

    cache = {
        'fetched_at': None,
        'fetch_source': src,
        'listing_url': LISTING_URL,
        'rides': keepers,
        'all_rides': rides,  # diagnostic — every row we parsed, kept or filtered
    }
    save_cache(cache, src)
    print(f'Wrote {NYCC_JSON_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
