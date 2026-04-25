#!/usr/bin/env python3
"""
Fetch NYRR race detail pages and persist a structured cache to _data/nyrr-races.json.

The cache is checked into git so the merge step can run offline. Re-running this
script refreshes records (use --force to refetch already-cached entries).

Pipeline:
  1. Read /tmp/central_park_events_latest.json (produced by the NYC Open Data
     fetch step in update-events.md) to discover candidate NYRR races.
  2. For each candidate, derive 1-3 NYRR URL slug guesses, try them live, then
     fall back to the Wayback Machine if Queue-It is up.
  3. Parse each detail page; keep records whose Location field references
     Central Park, OR whose course narrative mentions Central Park landmarks.
     Multi-borough races (NYC Marathon, NYC Half, Brooklyn Half) are kept and
     tagged with their start/finish boroughs.
  4. Write/refresh _data/nyrr-races.json keyed by NYRR slug.

Usage:
  python3 .claude/skills/scripts/fetch_nyrr_races.py            # incremental
  python3 .claude/skills/scripts/fetch_nyrr_races.py --force    # refetch all
  python3 .claude/skills/scripts/fetch_nyrr_races.py --wayback  # Wayback only
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
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
EVENTS_LATEST = '/tmp/central_park_events_latest.json'
NYRR_JSON_PATH = os.path.join(REPO_ROOT, '_data', 'nyrr-races.json')

UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) '
      'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15')
QUEUE_HOST = 'virtualcorral.nyrr.org'
WAIT_BETWEEN = 2.0  # seconds between detail fetches

# Title patterns that signal "this is a NYRR-managed race worth attempting to enrich".
# Match is case-insensitive. We're permissive on purpose — false candidates just
# fail to fetch and get logged.
NYRR_TITLE_PATTERNS = [
    r'^\s*(?:20\d\d\s+)?NYRR\b',
    r'\bNew York Road Runners\b',
    r'\bRBC\b.*\bBrooklyn\s+Half\b',
    r'\bAirbnb\b.*\bBrooklyn\s+Half\b',
    r'\bUnited Airlines\b.*\bNYC\s+Half\b',
    r'\bTCS\b.*\bMarathon\b',
    r'\bMini\s+10K\b',
    r"\bWomen'?s\s+Half\b",
    r"\bMen'?s\s+Half\b",
    r'\bAchilles\b.*\b(Hope|Possibility|Mile|5K|10K|Run|Walk)\b',
    r'\bFront Runners\b',
    r'\bJoe Kleinerman\b',
    r'\bTed Corbitt\b',
    r'\bBronx\s+10\s+Mile\b',
    r'\bQueens\s+10K\b',
    r'\bStaten Island\s+Half\b',
    r'\bMidnight Run\b',
    r'\bJingle Bell Jog\b',
    r'\bDash to the Finish Line\b',
    r'\bFifth Avenue Mile\b',
    r'\bEmpire State Building Run-?Up\b',
    r'\bRun for the Wild\b',
    r'\bNew York Mini\b',
    r'\bSpring Jamboree\b',
    r'\bManhattan\s+10K\b',
    r'\bManhattan\s+7\s+Mile\b',
    r'\bHealthy Kidney\b',
]

BOROUGHS = ['Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island']


def is_nyrr_candidate(title):
    return any(re.search(p, title, re.I) for p in NYRR_TITLE_PATTERNS)


def derive_slug(title):
    """NYRR slugs strip everything but lowercase alphanumerics."""
    t = re.sub(r'^\s*20\d\d\s+', '', title)
    return re.sub(r'[^A-Za-z0-9]', '', t).lower()


def url_candidates(title, year):
    slug = derive_slug(title)
    if not slug:
        return []
    out = []
    if year:
        out.append(f'https://www.nyrr.org/races/{year}{slug}')
        out.append(f'https://www.nyrr.org/races/{year}/{slug}')
    out.append(f'https://www.nyrr.org/races/{slug}')
    return out


def _read_response(resp):
    data = resp.read()
    if resp.headers.get('Content-Encoding') == 'gzip':
        data = gzip.decompress(data)
    return data.decode('utf-8', errors='replace')


def fetch_url(url, timeout=15):
    """Returns (html, 'live') or (None, reason)."""
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': UA, 'Accept-Encoding': 'gzip', 'Accept': 'text/html'},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            final = r.geturl() or url
            if QUEUE_HOST in final:
                return None, 'queueit'
            html = _read_response(r)
            # Check for soft-redirect-via-meta to queue
            if 'queueit' in html.lower()[:2048]:
                return None, 'queueit'
            return html, 'live'
    except urllib.error.HTTPError as e:
        loc = e.headers.get('Location', '') if hasattr(e, 'headers') and e.headers else ''
        if QUEUE_HOST in loc:
            return None, 'queueit'
        return None, f'http_{e.code}'
    except Exception as e:
        return None, f'err_{type(e).__name__}'


def fetch_with_wayback(url, timeout=20):
    html, src = fetch_url(url, timeout)
    if html:
        return html, 'live'
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
        if len(rows) < 2:
            return None, src or 'no_wayback'
        ts = rows[-1][1]  # most recent
        wb_url = f'https://web.archive.org/web/{ts}/{url}'
        html, _ = fetch_url(wb_url, timeout)
        return (html, 'wayback') if html else (None, 'wayback_fail')
    except Exception as e:
        return None, f'wayback_err_{type(e).__name__}'


# ── Parser ────────────────────────────────────────────────────────────

def _strip_wayback_chrome(html):
    return re.sub(
        r'<!-- BEGIN WAYBACK TOOLBAR INSERT -->.*?<!-- END WAYBACK TOOLBAR INSERT -->',
        '', html, flags=re.S,
    )


def _strip_wb_url_prefix(url):
    return re.sub(r'^https?://web\.archive\.org/web/\d+(?:im_)?/', '', url)


def _text_of(html_fragment):
    text = re.sub(r'<[^>]+>', ' ', html_fragment)
    text = re.sub(r'&nbsp;|&#160;', ' ', text)
    text = re.sub(r'&rsquo;', "'", text)
    text = re.sub(r'&mdash;', '—', text)
    return re.sub(r'\s+', ' ', text).strip()


def parse_race_detail(html):
    html = _strip_wayback_chrome(html)
    rec = {}

    m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    if m:
        rec['title'] = re.sub(r'\s+', ' ', m.group(1)).strip()

    # meta_list: race_detail-meta_list__key + __value sibling pattern
    for blk in re.finditer(
        r'<li[^>]*class="[^"]*race_detail-meta_list__item[^"]*"[^>]*>(.*?)</li>',
        html, re.S | re.I,
    ):
        body = blk.group(1)
        k = re.search(r'race_detail-meta_list__key[^>]*>(.*?)</', body, re.S)
        v = re.search(r'race_detail-meta_list__value[^>]*>(.*?)</div', body, re.S)
        if k and v:
            kk = _text_of(k.group(1)).lower().replace(' ', '_').rstrip(':')
            vv = _text_of(v.group(1))
            if kk and vv:
                rec[kk] = vv

    # event_key_list (newer markup variant)
    for blk in re.finditer(
        r'<(?:li|div)[^>]*class="[^"]*event_key_list__item[^"]*"[^>]*>(.*?)</(?:li|div)>',
        html, re.S | re.I,
    ):
        text = re.sub(r'<[^>]+>', '\n', blk.group(1))
        parts = [p.strip() for p in text.split('\n') if p.strip()]
        if len(parts) >= 2:
            kk = parts[0].lower().replace(' ', '_').rstrip(':')
            vv = ' '.join(parts[1:])[:300]
            rec.setdefault(kk, vv)

    # Hero / About description block
    desc_match = re.search(
        r'<(?:div|section)[^>]*class="[^"]*race_detail-desc[^"]*"[^>]*>(.*?)</(?:div|section)>\s*</(?:div|section)>',
        html, re.S | re.I,
    )
    if desc_match:
        rec['description'] = _text_of(desc_match.group(1))[:3000]

    # The Course accordion item
    course_match = re.search(
        r'race_detail-accordion__item__header[^>]*>\s*<[^>]+>\s*[^<]*Course[^<]*</[^>]+>'
        r'.*?race_detail-accordion__item__detail[^>]*>(.*?)</(?:div|section)>\s*</(?:div|section)>',
        html, re.S | re.I,
    )
    if course_match:
        rec['course_text'] = _text_of(course_match.group(1))[:3000]

    # Course map PDF
    m = re.search(r'(https?://[^"\s]*?race-course-maps[^"\s]+\.pdf)', html, re.I)
    if m:
        rec['course_map'] = _strip_wb_url_prefix(m.group(1))

    # Race photo (largest = un-cropped)
    m = re.search(
        r'(https?://prodsitecoreimage\.nyrr\.org/[^"\s]*?racepage/photos/[^"?\s]+)',
        html, re.I,
    )
    if m:
        rec['race_photo'] = _strip_wb_url_prefix(m.group(1).split('?')[0])

    # Race logo
    m = re.search(
        r'(https?://prodsitecoreimage\.nyrr\.org/[^"\s]*?race-logos?/[^"?\s]+)',
        html, re.I,
    )
    if m:
        rec['race_logo'] = _strip_wb_url_prefix(m.group(1).split('?')[0])

    # eventItemId GUID from iCal export
    m = re.search(r'eventItemId=\{?([0-9A-Fa-f\-]{36})\}?', html)
    if m:
        rec['event_item_id'] = m.group(1).upper()

    # Sponsors
    sponsors = []
    for fname in re.findall(r'/logo/partners/([a-zA-Z0-9_\-]+)\.[a-zA-Z]+', html):
        # Drop trailing version/digit suffixes, hyphenate
        clean = re.sub(r'(?:[_\-]?\d+){1,3}$', '', fname)
        clean = re.sub(r'[_\-]+', ' ', clean).strip()
        clean = re.sub(r'\b(final|new|fc|primary|logo|cmyk|pms|blk|wt|color|colored|black|white|v\d?)\b', '',
                       clean, flags=re.I).strip()
        clean = re.sub(r'\s+', ' ', clean)
        if clean and clean.lower() not in {s.lower() for s in sponsors}:
            sponsors.append(clean)
    if sponsors:
        rec['sponsors'] = sponsors[:6]

    # Strava club
    m = re.search(r'(https://www\.strava\.com/clubs/[a-z0-9\-]+)', html)
    if m:
        rec['strava_club'] = m.group(1)

    # Total finishers (when race is complete)
    m = re.search(r'([\d,]+)\s+Total\s+Finishers', html, re.I)
    if m:
        rec['total_finishers'] = int(m.group(1).replace(',', ''))

    # Borough mentions in the description+course text
    text_for_boroughs = ' '.join(
        v for k, v in rec.items()
        if isinstance(v, str) and k in ('description', 'course_text', 'location')
    )
    boroughs_seen = []
    for b in BOROUGHS:
        if re.search(r'\b' + re.escape(b) + r'\b', text_for_boroughs, re.I):
            boroughs_seen.append(b)
    if boroughs_seen:
        rec['boroughs'] = boroughs_seen

    # ical_url (canonical)
    if rec.get('event_item_id'):
        rec['ical_url'] = (
            'https://www.nyrr.org/api/feature/racedetail/ExportIcal?eventItemId='
            + rec['event_item_id']
        )

    return rec


def looks_like_central_park(rec):
    """Decide whether to keep a parsed record."""
    loc = (rec.get('location') or '').lower()
    if 'central park' in loc:
        return True
    blob = ' '.join(
        v for k, v in rec.items()
        if isinstance(v, str) and k in ('description', 'course_text')
    ).lower()
    if 'central park' in blob:
        return True
    # Multi-borough races that *finish in Central Park*. Brooklyn Half is
    # explicitly NOT here — it finishes at Coney Island, never enters the park.
    title = (rec.get('title') or '').lower()
    if any(s in title for s in (
        'tcs new york city marathon', 'new york city marathon',
        'united airlines nyc half', 'nyc half',
    )):
        return True
    return False


# ── Driver ────────────────────────────────────────────────────────────

def discover_candidates():
    """Read /tmp/central_park_events_latest.json and find unique NYRR title+year."""
    if not os.path.exists(EVENTS_LATEST):
        print(f'No {EVENTS_LATEST}; run the NYC Open Data fetch first.')
        return []
    with open(EVENTS_LATEST) as f:
        latest = json.load(f)
    seen = {}
    for e in latest:
        name = e.get('event_name') or ''
        if not is_nyrr_candidate(name):
            continue
        try:
            year = datetime.fromisoformat(e['start_date_time'].replace('.000', '')).year
        except Exception:
            continue
        slug = derive_slug(name)
        key = f'{year}{slug}'
        if key in seen:
            continue
        seen[key] = {'title': name, 'year': year, 'slug': slug}
    return list(seen.values())


def load_cache():
    if os.path.exists(NYRR_JSON_PATH):
        with open(NYRR_JSON_PATH) as f:
            return json.load(f)
    return {'fetched_at': None, 'races': {}}


def save_cache(cache):
    cache['fetched_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    with open(NYRR_JSON_PATH, 'w') as f:
        json.dump(cache, f, indent=2, sort_keys=True)
        f.write('\n')


def main(argv):
    force = '--force' in argv
    wayback_only = '--wayback' in argv

    candidates = discover_candidates()
    print(f'Found {len(candidates)} NYRR candidate races in NYC Open Data feed.')
    if not candidates:
        return 0

    cache = load_cache()
    races = cache.setdefault('races', {})

    stats = {'cached': 0, 'live': 0, 'wayback': 0, 'failed': 0, 'filtered_out': 0}

    for c in candidates:
        key = f'{c["year"]}{c["slug"]}'
        existing = races.get(key, {})
        if existing.get('parsed') and not force:
            stats['cached'] += 1
            continue

        urls = url_candidates(c['title'], c['year'])
        html, src = None, None
        if not wayback_only:
            for u in urls:
                html, src = fetch_url(u, timeout=15)
                if html:
                    chosen = u
                    break
                time.sleep(0.5)
        if not html:
            for u in urls:
                html, src = fetch_with_wayback(u, timeout=25)
                if html:
                    chosen = u
                    break
                time.sleep(0.5)

        if not html:
            races[key] = {
                'candidate_title': c['title'],
                'year': c['year'],
                'slug': c['slug'],
                'urls_tried': urls,
                'last_error': src or 'unknown',
                'parsed': False,
                'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            }
            stats['failed'] += 1
            print(f'  ✗ {c["title"]:<60s} {src}')
            time.sleep(WAIT_BETWEEN)
            continue

        rec = parse_race_detail(html)
        if not looks_like_central_park(rec):
            stats['filtered_out'] += 1
            races[key] = {
                'candidate_title': c['title'],
                'year': c['year'],
                'slug': c['slug'],
                'parsed': False,
                'reason': 'not_central_park',
                'fetched_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            }
            print(f'  • skip non-CP: {rec.get("title", c["title"])[:60]}')
            time.sleep(WAIT_BETWEEN)
            continue

        rec['source_url'] = chosen
        rec['fetch_source'] = src
        rec['fetched_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        rec['candidate_title'] = c['title']
        rec['year'] = c['year']
        rec['slug'] = c['slug']
        rec['parsed'] = True
        races[key] = rec
        stats[src] = stats.get(src, 0) + 1
        print(f'  ✓ {src:<8s} {rec.get("title", "?")[:60]}')
        time.sleep(WAIT_BETWEEN)

    save_cache(cache)
    print()
    print('Stats:', stats)
    print(f'Cache: {NYRR_JSON_PATH} ({len(races)} entries)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
