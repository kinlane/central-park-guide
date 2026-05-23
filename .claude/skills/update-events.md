# Update Events from NYC Open Data, NYC Parks, Conservancy, centralpark.com, SummerStage, Naumburg, NYRR, NYCC, and curated charity walks / Public Theater / NYC Bird Alliance

Update Central Park Guide events by fetching event data from a layered set of sources, filtering against the Central Park places vocabulary, merging (with title cleanup and category mapping), and writing Jekyll collection files. All future events automatically display on the public site — no curation step.

## Source roster

Sources fall into three groups:

**Permits & official programming (machine-readable feeds):**
1. **NYC Open Data — Permitted Events** (`data.cityofnewyork.us`) — every permit issued at Central Park
2. **NYC Parks Department** (`nycgovparks.org/parks/central-park/events`) — official park-dept programming (Arsenal Gallery, NY Phil at the Great Lawn, It's My Park volunteer days)
3. **SummerStage** (`cityparksfoundation.org/wp-json/tribe/events/v1/events`) — the City Parks Foundation's outdoor concert series at Rumsey Playfield + Dana Discovery Center
4. **Central Park Conservancy** (`centralparknyc.org/activities.json`) — the Conservancy's own programs
5. **Naumburg Orchestral Concerts** (`naumburgconcerts.org/concerts/`) — historic free classical series at the Bandshell (since 1905)
6. **centralpark.com** — community events
7. **NYRR enrichment** (`nyrr.org/races/...`) — adds course-map/distance/landmark data to races already in NYC Open Data
8. **NYCC group rides** (`nycc.org/upcoming-rides`) — club cycling rides rolling out from the park

**Curated seed files (hand-maintained YAML; sources that can't be scraped):**
9. **`_data/charity-walks.yml`** — AIDS Walk NY etc.; affects-loop closures the permit feed misses
10. **`_data/publictheater-seasons.yml`** — Public Theater's Shakespeare in the Park (their site is WAF-blocked); maintained by hand each spring when the season is announced. Expands into one event per performance date.
11. **`_data/birding-walks.yml`** — NYC Bird Alliance recurring walks (their events page renders via JS so we can't scrape server-side). Expands by weekday + cadence within a season window.

## Quick start (NYC Open Data refresh)

For the most common case — pulling the latest NYC events:

```bash
# 1. Fetch all Central Park events from the API (paginated)
OFFSET=0
> /tmp/cp_events_pages.json
while true; do
  RESP=$(curl -s "https://data.cityofnewyork.us/resource/tvpp-9vvx.json?\$where=event_location%20like%20%27Central%20Park%25%27&\$limit=1000&\$offset=$OFFSET")
  COUNT=$(echo "$RESP" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")
  echo "$RESP" >> /tmp/cp_events_pages.json
  [ "$COUNT" -lt 1000 ] && break
  OFFSET=$((OFFSET + 1000))
done

# 2. Combine pages into one JSON array.
#    Each curl response is a JSON array but can span multiple lines, so parse
#    streaming with raw_decode rather than line-by-line.
python3 -c "
import json
text = open('/tmp/cp_events_pages.json').read()
decoder = json.JSONDecoder()
combined, i = [], 0
while i < len(text):
    while i < len(text) and text[i] in ' \t\r\n':
        i += 1
    if i >= len(text):
        break
    obj, i = decoder.raw_decode(text, i)
    combined.extend(obj)
with open('/tmp/central_park_events_latest.json', 'w') as f:
    json.dump(combined, f)
print(f'Total: {len(combined)}')
"

# 3. Refresh NYRR enrichment cache (course maps, race meta).
#    Discovers candidate races from /tmp/central_park_events_latest.json and
#    fetches each detail page (live → Wayback fallback). Persists to
#    _data/nyrr-races.json which is checked into git.
#    Note: nyrr.org sits behind Queue-It on race-day surges; if the live fetch
#    is queued and Wayback has no snapshot, the script logs the miss and moves
#    on. Re-run later when traffic clears.
python3 .claude/skills/scripts/fetch_nyrr_races.py

# 4. Refresh additional event caches (NYC Parks, SummerStage, Naumburg).
#    Each writes a JSON cache under _data/. All three are idempotent and the
#    merge tolerates a missing cache (it logs and continues).
#    Note: NYC Parks is fronted by CloudFront WAF; if it returns a 202
#    challenge response, wait an hour and re-run.
python3 .claude/skills/scripts/fetch_nycparks_events.py
python3 .claude/skills/scripts/fetch_summerstage_events.py
python3 .claude/skills/scripts/fetch_naumburg_concerts.py

# 5. Run the merge — picks up all caches plus the curated YAML files.
python3 .claude/skills/scripts/merge_nyc_events.py

# 6. Build to verify
bundle exec jekyll build
```

The merge script at `.claude/skills/scripts/merge_nyc_events.py` is self-contained and idempotent — running it again with the same data is a no-op.

## Data Sources

### Source 1: NYC Open Data (Permitted Events)

- **API endpoint:** `https://data.cityofnewyork.us/resource/tvpp-9vvx.json`
- **Dataset:** NYC Permitted Event Information (tvpp-9vvx)
- **Filter:** `event_location like 'Central Park%'`
- **Pagination:** Fetch in batches of 1000 using `$limit=1000&$offset=N`
- **Event ID prefix:** none (use raw `event_id` from API)

Each record has these fields:
- `event_id` (unique identifier)
- `event_name`
- `start_date_time` / `end_date_time` (ISO 8601)
- `event_agency`
- `event_type` (Special Event, Sport - Adult, Sport - Youth)
- `event_borough`
- `event_location` (prefixed with "Central Park: ")
- `street_closure_type`
- `community_board` / `police_precinct`

### Source 2: NYRR (New York Road Runners) race-detail enrichment

Enriches existing NYC Open Data race events with course-map, distance, hashtag, hero photo, and traversed-landmark data parsed from the NYRR race detail page. Does **not** create new events — only enhances ones that already exist from Source 1.

- **Listing URL:** `https://www.nyrr.org/run/race-calendar` (today the calendar itself is fronted by Queue-It; we discover candidates from the NYC Open Data feed instead)
- **Detail URL pattern:** `https://www.nyrr.org/races/{year}{slug}` or `/races/{year}/{slug}` or `/races/{slug}` — slug is the title with `[^A-Za-z0-9]` stripped, lowercased, year prefix removed
- **Queue-It caveat:** during high-traffic windows (race-day, registration), every NYRR path 302s to `virtualcorral.nyrr.org`. The fetch script detects this and falls back to the Wayback Machine via the CDX API. If neither works, it logs the miss in `_data/nyrr-races.json` and the merge proceeds without enrichment for that race. Re-run when the queue clears.
- **iCal endpoint:** `https://www.nyrr.org/api/feature/racedetail/ExportIcal?eventItemId={GUID}` (also queue-fronted)
- **Cache file:** `_data/nyrr-races.json` (checked into git) — keyed by `{year}{slug}`. Each entry stores the parsed fields plus `fetch_source` (`live` / `wayback` / `manual_seed`) and `fetched_at`.

Fields parsed from each detail page (when present):

| Field | Source on page | Used by merge |
|---|---|---|
| `title` | `og:title` | display only |
| `date` / `time` | `event_key_list__item` | reference |
| `location` | meta_list (Location) | filter signal — must reference Central Park |
| `distance` | meta_list (Distance) | `nyrr.distance` |
| `hashtag` | meta_list (Hashtag) | `nyrr.hashtag` |
| `description` | `.race_detail-desc--intro` block | tokenized for landmarks |
| `course_text` | "The Course" accordion | tokenized for landmarks |
| `course_map` | `prodsitecore.blob...race-course-maps/*.pdf` | `nyrr.course_map` (linked from event page) |
| `race_photo` | `prodsitecoreimage.../racepage/photos/*` | `nyrr.race_photo` |
| `race_logo` | `prodsitecoreimage.../race-logos/*` | `nyrr.race_logo` |
| `event_item_id` | iCal href GUID | `nyrr.event_item_id`, drives `nyrr.ical_url` |
| `sponsors` | `/logo/partners/*` filenames | `nyrr.sponsors` |
| `strava_club` | external link | `nyrr.strava_club` |
| `total_finishers` | post-race stat | `nyrr.total_finishers` |
| `boroughs` | regex over description+course | merged into the event's `boroughs:` array |

**Filter to Central Park:** keep records where `Location` contains "Central Park" OR description/course text mentions Central Park OR title is one of the multi-borough finishers (NYC Marathon, NYC Half). Brooklyn Half is **excluded** — it doesn't enter the park.

**Multi-location enrichment:** the parsed `description` and `course_text` are tokenized against `_data/central-park-places.yml` using the same `match_places()` longest-first algorithm the merge uses for permit locations. Any landmark named in the race narrative gets appended to the event's `places:` array (deduped against the primary location match). Boroughs touched by the route (`Manhattan`, `Brooklyn`, etc.) write to a `boroughs:` array on the event front matter.

**Match key from event side:** the merge derives a NYRR slug from the event's `name` + `date.year` and looks up `nyrr_cache[{year}{slug}]`, falling back to `{slug}` alone, then `{year-1}{slug}` (recurring annuals).

### Source 3: Central Park Conservancy (centralparknyc.org)

- **API endpoint:** `https://www.centralparknyc.org/activities.json`
- **Pagination:** 16 items per page, paginate with `?page=N` until no more results
- **Filter:** Only items where `type` contains "Event" (includes "Events", "Benefit Events", "Arts & Entertainment, Events", "Events, Activities")
- **Event ID prefix:** `cpc-` (e.g., `cpc-887607`) to avoid collisions with NYC Open Data IDs
- **Detail pages:** Each event has a detail URL; fetch it to extract `detail_page_data` including `location_detail`, `date_detail`, `time_detail`, `cost`, and `description_detail`

Each listing record has:
- `id` (numeric, prefix with `cpc-`)
- `title`
- `url` (detail page URL)
- `type` (event classification)
- `tags` (array of tag strings)
- `summary` / `description`
- `image` (object with `thumbnail`, `thumbnail_srcset`, `schema_image`)
- `start_date` / `event_instances`
- `detail_page_data` (enriched from fetching the detail URL):
  - `location_detail` — the venue/location string
  - `date_detail` — human-readable date
  - `time_detail` — time information
  - `cost` — admission cost (often "Free")
  - `description_detail` — longer description
  - `status` — whether concluded or upcoming

**Location filtering for Conservancy events:**
- Skip events where `location_detail` references places outside Central Park (e.g., "Mother AME Zion Church, Harlem", "Schomburg Center")
- Skip events with vague locations like "Central Park's north end" that don't match a specific place in the vocabulary
- Events must match a named place in `_data/central-park-places.yml` to be included

**The enriched Conservancy data is also cached to `_data/central-park-conservancy-events.json` for reference.**

### Source 4: centralpark.com (Community Events)

- **Listing URL:** `https://www.centralpark.com/search/event/upcoming-events/`
- **Platform:** Metro Publisher (no REST API; parse HTML listing pages or RSS/ICS feeds)
- **Alternative feeds:**
  - RSS: `https://www.centralpark.com/search/event/upcoming-events/index.rss`
  - ICS: `https://www.centralpark.com/search/event/upcoming-events/calendar.ics`
- **Pagination:** ~10 results per page, `#page=N` in URL (or paginate HTML)
- **Event ID prefix:** `cpcom-` followed by slugified title (e.g., `cpcom-bird-watching-with-birding-bob`)

Each event page/record has:
- `title`
- `url` (detail page on centralpark.com)
- `description` (full text)
- `location` (venue name, often with street reference)
- `schedule` (object with `days`, `times`, `duration`)
- `cost` / `admission` (string or object with tier pricing)
- `coordinates` (lat/lng when available)
- `meeting_points` (some events have different locations by day)

**Key characteristics of centralpark.com events:**
- Many are **recurring** (daily, weekly, seasonal) rather than one-off dates
- Include commercial tours, zoo programs, community fitness groups, and seasonal activities
- Use a `recurrence` front matter field to store the schedule pattern (e.g., "Saturdays, April through November")
- Events without a specific start date use `2026-04-15` as a placeholder
- The `event_type` is set to `"Community Event"` for all centralpark.com events

**Location matching notes:**
- Zoo events match to "Central Park Zoo" in the `buildings` vocabulary category
- "Central Park Boathouse" matches "Loeb Boathouse" via alternate names
- "Swedish Cottage" matches "Swedish Cottage Marionette Theatre"
- "Lawn Behind Met Museum" matches "Lawn Behind the Met Museum"
- "Central Park West & 72nd Street entrance" matches via alternate name

**The raw data is cached to `_data/centralpark-com-events.json` for reference.**

### Source 5: New York Cycle Club rides (nycc.org/upcoming-rides)

NYCC publishes its weekly group-ride calendar at `https://nycc.org/upcoming-rides`. Most rides start outside Central Park (Long Island, Jersey, etc.), but a meaningful share roll out from **Loeb Boathouse**, the **72nd Street Transverse**, or **Engineers' Gate (90th & 5th)** — and they briefly occupy East Drive on the way out. Useful in the cyclist and runner persona emails as a heads-up about peloton activity in the early-morning loop.

- **Listing URL:** `https://nycc.org/upcoming-rides`
- **Cloudflare caveat:** the live site sits behind Cloudflare's managed JS challenge — direct curl/WebFetch returns 403. WordPress feed endpoints (`/feed`, `/wp-json/wp/v2/posts`, `/upcoming-rides/feed`) are also blocked. Follow the same fallback chain we use for NYRR: try live first, then Wayback (`https://web.archive.org/web/{TIMESTAMP}/https://nycc.org/upcoming-rides`), then log the miss and skip. Re-run once a snapshot exists.
- **Wayback coverage gap (critical):** Wayback indexes the listing page (`/upcoming-rides`) but **NOT** the individual ride detail pages (`/node/{ID}`). Verified empirically via the CDX API: every detail-page node ID tested returned zero snapshots. Practical consequence — when the live site is Cloudflare-blocked, the fetch script can parse the listing rows (title, date, time, leader, pace, distance) but **cannot resolve the Meet Up location**, which is the field that determines whether a ride starts in Central Park. The listing HTML itself has no location column. Without a live fetch or a manual Meet Up source, the script will produce zero kept rides.
- **Snapshot discovery:** use the Wayback availability API: `https://archive.org/wayback/available?url=nycc.org/upcoming-rides`. For the freshest snapshot use the CDX API filtered to recent timestamps.
- **Real-world path to usable data:** to actually harvest NYCC rides, one of: (a) a headless-browser fetch that can solve the Cloudflare challenge (Playwright/Puppeteer — out of scope for this skill); (b) an iCal/RSS export negotiated with the NYCC webmaster; or (c) a hand-curated YAML of known-CP recurring rides (SIG/STS series, weekly Boathouse rolls) mirroring the `charity-walks.yml` pattern. Until one of those exists, the fetch script is a structural placeholder.
- **Cache file:** `_data/nycc-rides.json` (checked into git) — one record per ride occurrence. Keyed by `{date}-{slugified-name}-{slugified-leader}` since NYCC has no stable per-ride ID.
- **Event ID prefix:** `nycc-` (e.g., `nycc-2026-05-23-market-back-via-9w-cliu`) to avoid collisions with the other sources.

**Scrape pattern.** The page renders a Drupal/Views table where each ride row contains five fields in this order:

```
Ride Name | Day, Mon DD | HH:MM AM/PM | Leader | Pace/MPH | Distance
```

Example rows confirmed from the Feb 2026 snapshot:

| Name | When | Leader | Pace | Distance |
|---|---|---|---|---|
| Market & Back via 9W | Sun, Feb 15  08:30 AM | Chuxin Liu | B /16 | 40 Miles |
| Long Island North Shore | Sun, Feb 15  08:30 AM | Jan Laan | B /19 | 86 (or 60,70,50,25) Miles |
| Market with Walnut return | Sun, Feb 15  09:00 AM | Scott Weinstein | B /18 | 30 Miles |

**Pace classification:** ride pace is `{Letter} /{mph}` — `A`, `B`, `C`, plus `SIG` (Special Interest Group — training series) and `STS` (Saturday Training Series). Store the raw string in `pace:` and parse the integer into `mph:` for sortability.

**Central-Park filter (critical).** Most NYCC rides don't start in or pass through Central Park. The merge must apply a positive filter and reject everything else, because including the full club calendar would flood the events page:

1. Fetch each ride's detail page (link in the row's title `<a>`) to get the **Meet Up** location.
2. Keep the ride if the Meet Up location matches a place in `central-park-places.yml` via the standard `match_places()` algorithm. Known NYCC start spots that match: **Loeb Boathouse** ("Central Park Boathouse"), **Engineers' Gate** (90th St & 5th Ave — add to `gates:` if missing), **72nd Street Cross Drive**, **Merchants' Gate** / **Columbus Circle**, **Tavern on the Green**.
3. If detail-page fetch fails (Cloudflare blocks bulk requests), fall back to scanning the listing-page row text — but expect to miss most CP rides this way and log the gap.

**Output mapping.** Each kept ride becomes one event:

| Field | Source on NYCC page |
|---|---|
| `title` | Ride name |
| `date` | Parsed from the day-and-date string (resolve year against fetch date — ride listings are forward-looking) |
| `time` | Start time, 24-hour |
| `location` | Meet Up text from detail page |
| `event_type` | `"Group Ride"` |
| `event_borough` | `"Manhattan"` (always, since we filtered to CP starts) |
| `source` | `"nycc.org"` |
| `source_url` | Ride detail page URL |
| `description` | Auto-generated: `"NYCC {pace} group ride led by {leader}. {distance}, departing from {location}."` |
| `tags` | Always `["nycc", "cycling", "group-ride"]`. Add `"sig"` or `"sts"` when the pace string starts with those letters. Add `"affects-loop"` when start time falls between 5 AM and 9 AM (peak runner overlap on East Drive). |

**The raw scrape is cached to `_data/nycc-rides.json` for reference.** Each entry stores the parsed fields plus `fetch_source` (`live` / `wayback`) and `fetched_at`, mirroring the NYRR cache convention.

### Source 6: Curated charity walks (`_data/charity-walks.yml`)

Annual third-party charity walks/runs that use Central Park as a venue but are missed by Sources 1–5. The triggering miss was AIDS Walk New York (5/17/2026 — ~30K participants, opening at Naumburg Bandshell, route across East Drive and the Mall) — absent from `tvpp-9vvx` entirely, with no centralpark.com or Conservancy listing either, because the Parks Department permitting for large private venue bookings doesn't flow to NYC Open Data.

- **Source file:** `_data/charity-walks.yml` (checked into git, hand-edited)
- **Event ID prefix:** `charity-` (e.g., `charity-aids-walk-ny-2026-05-17`) to avoid collisions with the other four sources
- **Structure:** a top-level `walks:` list. Each entry is one annually recurring event, with a `dates:` map keyed by year. An entry expands to one event per year-with-a-non-null-date.
- **Skip rule:** entries where `dates[current_year]` is null OR missing are silently skipped — they're placeholders awaiting confirmation.

Fields on each entry (required unless noted):

| Field | Notes |
|---|---|
| `id` | Stable kebab-case identifier. Used in the event id (`charity-{id}-{date}`). |
| `title` | Display title. |
| `organizer` | Sponsoring nonprofit. Appears in event body. |
| `source_url` | Official event page. Written to `source_url:` on event front matter. |
| `recurrence` | Plain-English pattern for the maintainer's reference (e.g., "Third Sunday of May"). Not used by merge logic. |
| `dates` | Map of `"YYYY"` → ISO date string. Years with null values are skipped. |
| `start_time` / `end_time` | `HH:MM` (24-hour). |
| `opening_ceremony_time` | *Optional.* Some events open earlier than the walk start. |
| `location` | Plain place-name string; must match a place in `central-park-places.yml`. Run through `match_places()` like all other sources — multi-place matches become `places:` arrays. |
| `event_type` | Typically `"Charity Walk"` or `"Charity Run"`. |
| `event_borough` | Always `"Manhattan"` for in-park events. |
| `expected_attendance` | *Optional.* Integer. Used by persona-email logic to weight impact. |
| `affects_loop` | Boolean. If true, the merge adds the `affects-loop` tag (new), which the runner/cyclist persona-email templates must surface even when the event isn't a race. |
| `route_impact` | Plain text describing closures/crowding. Written into the event body. |
| `audience_relevance` | List of persona keys (`runners`, `cyclists`, `walkers`, `park-watcher`, etc.). The persona-email generator uses this to decide which weekly briefs include the event. |
| `description` | One-paragraph event summary. |
| `tags` | List of tag slugs. Always include `charity` and either `walk` or `race`. |

**Maintenance pattern:** once per year (Feb/March), walk through the file and fill in the new year under each entry's `dates:` map. The build should warn when an entry has no `dates` value for the current year — those are knowable gaps that need filling before walk season.

### Source 7: NYC Parks Department (`/parks/central-park/events`)

The official NYC Parks Department per-park events page. Sister feed to the NYC Open Data permit listing — captures **NYC Parks-programmed** events (e.g. Arsenal Gallery exhibits, NY Phil at the Great Lawn, "It's My Park" volunteer days) that the permits feed doesn't always surface.

- **URL pattern:** `https://www.nycgovparks.org/parks/central-park/events` and `/page/N` for additional pages (~7 pages typical)
- **Format:** hCalendar microformat — `<div class="vevent">` with `.summary` title link, `.dtstart`/`.dtend` (ISO timestamps in `title="..."` attribute), `.location`, plus a free-text Category and a "Free!" marker
- **Scraper:** [`.claude/skills/scripts/fetch_nycparks_events.py`](scripts/fetch_nycparks_events.py)
- **Cache file:** `_data/nycparks-events.json`
- **Event ID prefix:** `nycparks-`
- **WAF caveat:** the site is fronted by CloudFront and starts returning `202 challenge` responses after rapid requests. The script paginates with 0.3 s delays, but if you've just been probing the site, give it an hour before re-running. The merge tolerates a missing cache.
- **Location quirk:** every location ends with " (in Central Park)" — the scraper strips that suffix so `match_places()` sees the clean venue name. The Arsenal building has alternate names `Arsenal` and `Arsenal Gallery` in the places vocabulary to handle the recurring Sarah Yuster exhibit.

### Source 8: SummerStage (City Parks Foundation)

SummerStage is the City Parks Foundation's free outdoor concert series. **At Central Park** the program plays at **Rumsey Playfield** (mid-park, 72nd & 5th) and the **Charles A. Dana Discovery Center** (Harlem Meer) — but the program also runs in every other borough, so we filter aggressively.

- **API endpoint:** `https://cityparksfoundation.org/wp-json/tribe/events/v1/events` (The Events Calendar WordPress plugin's REST API — paginated `?per_page=N&page=K`)
- **Filter:** `categories=25` (the **SummerStage** taxonomy id; verified May 2026 — re-check if results look off). Then keep only events whose `title` + `description` matches the regex `rumsey|central park|dana discovery|harlem meer` (the venue field is just "Manhattan" so we can't filter on that).
- **Scraper:** [`.claude/skills/scripts/fetch_summerstage_events.py`](scripts/fetch_summerstage_events.py)
- **Cache file:** `_data/summerstage-events.json`
- **Event ID prefix:** `summerstage-`
- **Place hint:** `Rumsey Playfield` by default; switched to `Dana Discovery Center` when the description mentions Dana / Harlem Meer.

### Source 9: Naumburg Orchestral Concerts

Five free Tuesday-evening classical concerts at the Naumburg Bandshell each summer — the oldest free outdoor classical series in the US (founded 1905).

- **URL:** `https://naumburgconcerts.org/concerts/`
- **Platform:** Squarespace events module — events render inside `<article class="eventlist-event ...">` with `.eventlist-title-link`, `<time class="event-date" datetime="...">`, `<time class="event-time-localized">`.
- **Scraper:** [`.claude/skills/scripts/fetch_naumburg_concerts.py`](scripts/fetch_naumburg_concerts.py)
- **Cache file:** `_data/naumburg-events.json`
- **Event ID prefix:** `naumburg-`
- **Default times:** if the Squarespace markup omits a time, use historical convention `19:30` start, `21:00` end (90-min concerts at the Bandshell).
- **Place:** `Naumburg Bandshell` (in places vocab; aliased to `Bandshell Plaza`).

### Source 10: Public Theater seasons (`_data/publictheater-seasons.yml`)

Shakespeare in the Park at the Delacorte Theater. The Public Theater's site is fronted by a strict Cloudflare WAF that rejects automated requests, so we maintain a hand-curated YAML seed each spring when the season is announced. The merge **expands one season into one event per performance date**, skipping the configured dark days (Monday is the Delacorte convention).

- **Source file:** `_data/publictheater-seasons.yml` (hand-edited)
- **Event ID prefix:** `publictheater-`
- **Maintenance pattern:** open the Public Theater's Shakespeare in the Park page in a browser when the season is announced (typically March/April); copy the run dates into a new `- season:` entry. Fields: `production`, `author`, `director`, `first_preview`, `opening_night`, `closing_night`, `curtain`, `dark_days`, `url`, `notes`, `tags`.
- **Place:** `Delacorte Theater` (in places vocab).

### Source 11: NYC Bird Alliance walks (`_data/birding-walks.yml`)

NYC Bird Alliance (formerly NYC Audubon) leads recurring guided bird walks in Central Park. Their events page renders entirely client-side via JS, so server-side scraping doesn't work without a headless browser. We maintain a YAML seed and **expand each entry by `weekday` + `cadence` between `season_start` and `season_end`**.

- **Source file:** `_data/birding-walks.yml` (hand-edited)
- **Event ID prefix:** `birding-`
- **Cadence support:** `weekly`, `biweekly`, `monthly` (monthly snaps to the next matching weekday after ~28 days).
- **Maintenance pattern:** check their `local-trips-classes` page when each season's schedule is posted (early spring + late summer); add entries per walk leader/place/weekday. Fields: `name`, `leader`, `meet_location`, `place`, `season_start`, `season_end`, `weekday` (0=Mon, 6=Sun), `cadence`, `time`, `end_time`, `cost`, `url`, `tags`.
- **Place:** typically `The Ramble` or `North Woods`; whatever the walk's `place` field names must be in the places vocabulary.

## Steps

### 1. Fetch events from all sources

**NYC Open Data:** Use WebFetch to pull all Central Park events from the Socrata API. Paginate with `$offset` until fewer than 1000 results are returned.

```
https://data.cityofnewyork.us/resource/tvpp-9vvx.json?$where=event_location%20like%20%27Central%20Park%25%27&$limit=1000&$offset=0
```

**Conservancy:** Fetch `https://www.centralparknyc.org/activities.json?page=1` through all pages. Filter to event types only. Then fetch each event's detail URL to get enriched data.

**centralpark.com:** Fetch the listing pages at `https://www.centralpark.com/search/event/upcoming-events/` (paginate through all pages) or use the RSS feed. Then fetch each event's detail page for full data including schedule, cost, and location details.

**NYCC:** Fetch `https://nycc.org/upcoming-rides`. Expect a 403 Cloudflare challenge on direct fetch. Fall back to the latest Wayback snapshot via `https://archive.org/wayback/available?url=nycc.org/upcoming-rides`. Parse the ride table, then for each row resolve the ride's detail-page URL and fetch it to read the **Meet Up** location. Drop any ride whose Meet Up doesn't match a Central Park place. Cache the kept records to `_data/nycc-rides.json` with `fetch_source` set to `live` or `wayback`. If both fail, leave the cache as-is and log the gap.

**charity-walks.yml:** No fetch step — read the file directly. For each entry, look up `dates[current_year]`; if null/missing, skip. Otherwise emit one event record with `event_id = "charity-{id}-{date}"`, `event_type = entry.event_type` (default `"Charity Walk"`), `source = "charity-walks.yml"`, and `source_url = entry.source_url`. When `affects_loop: true`, append the `affects-loop` tag (Title Case: `Affects Loop`).

### 2. Load the places vocabulary

Read `_data/central-park-places.yml`. This YAML file has categories as top-level keys, each containing a list of places with `name`, `type`, `location`, `description`, and optional `alternate_names`.

Build a lookup of all place names and alternate names (lowercased) mapped to their canonical name and category. Sort tokens longest-first for greedy matching.

### 3. Clean event locations

**NYC Open Data:** Strip the `Central Park: ` prefix from `event_location`. If the location has multiple comma-separated parts, take the first two.

**Conservancy:** Use `detail_page_data.location_detail`. Strip "Central Park" suffixes. Match the location string against the places vocabulary.

### 4. Match events to places

For each event, scan its cleaned location for **all** place name tokens from the vocabulary (case-insensitive, longest-first to avoid shorter tokens stealing a longer span). The merge script's `match_places()` returns every distinct match in source order.

- The **first** match becomes the primary `place:` and `place_category:` (singular fields, always written — back-compat with everything that reads them).
- When more than one place is matched, the writer also emits `places:` and `place_categories:` arrays. Single-location events do NOT get these arrays (keeps diffs minimal and keeps "places" semantically meaning "this event spans multiple landmarks").
- Listing/admin pages normalize both shapes at runtime: `e.allPlaces = e.places && e.places.length ? e.places : (e.place ? [e.place] : [])`. The place dropdown counts each place per event; an event filtered by place matches if any of its places equals the selection.

If a location has zero matches, **skip the event** — it doesn't map to a known Central Park location. If it looks like a real Central Park sub-location, add it to `_data/central-park-places.yml` under the `event_venues` category before re-matching.

### 5. Categorize events (internal — folded into tags)

There is no `category:` field on event files. Categorization still happens internally inside `categorize()` to drive the category-based tag rollups in `get_tags()` (e.g., a `closures` category emits the `Closures` tag, `private-events` emits both `Private Events` and `Private Booking`). The internal slug is never written to disk — it only feeds the tag list.

**NYC Open Data (apply in this order — first match wins):**
1. `event_name` contains "maintenance" → `maintenance`
2. `event_name` contains "lawn closure" or "meadow closure" → `closures`
3. `event_name` contains SSS CPE/CPW, mini-camp, soccer training, sports training, socroc → `education`
4. `event_name` contains celebration/wedding/elopement/ceremony/birthday/baptism/memorial/bar mitzvah/reception, OR is exactly "party"/"picnic"/"miscellaneous" → `private-events`
5. `event_type` is "Sport - Adult" or "Sport - Youth" OR `event_name` contains softball/baseball/t-ball/kickball/soccer/tennis/pickleball/frisbee/volleyball/basketball/lacrosse/rugby/bowling/yacht/skating → `sports`
6. `event_name` contains concert/music/jazz/salsa/band/choir/festival/dance/theater/songwriters/dj/entertainment/opera/symphonic/marching/shakespeare/marionette/puppet → `concerts-performances`
7. `event_name` contains walk/run/race/5k/10k/15k/half/marathon/jog (word-boundary match; "half" catches NYC/Brooklyn/Women's Half) → `runs-races`
8. Default → `family-community`

**Why the order matters:** A "Soccer Training Mini-Camp" should be `education`, not `sports`. A "Birthday Party" hosted on a softball field should be `private-events`, not `sports`.

**Conservancy:**
- `type` contains "Arts & Entertainment" → `concerts-performances`
- `type` contains "Benefit" → `family-community`
- Default → `family-community`

**centralpark.com:**
- Title contains run/race/running/fitness/yoga/pickleball/tennis → `runs-races`
- Title contains shakespeare/theater/marionette/concert → `concerts-performances`
- Default → `family-community`

### 6. Assign tags

**Single-dimension filtering:** The site has one metadata system — `tags`. There is no separate `category` field. The internal category from step 5 is folded into the tag list alongside all keyword-derived tags.

**Storage form: Title Case.** Tags are stored on event files as human-readable Title Case strings (`Sports`, `Runs & Races`, `Concerts & Performances`, `T-Ball`, `LGBTQ`). The `TAG_DISPLAY` map in `merge_nyc_events.py` is the slug → display lookup. Internal slug form is only used for: (1) keyword matching inside `TAG_RULES`, (2) image asset filenames in `assets/images/tags/{slug}.png` (the merge script slugifies tags before lookup), (3) `category-badge--{slug}` CSS modifier classes generated client-side from the Title Case tag.

**NYC Open Data:** Build a tag list from event name, type, and category. The merge script's `TAG_RULES` constant is the source of truth — any change to the keyword list lives there. Subtype rules also emit their parent (e.g., a Shakespeare play tags as both `shakespeare` and `theater`; a salsa concert tags as both `salsa` and `music`). All slugs below get mapped to Title Case via `TAG_DISPLAY` before being written to disk:
- Sports: `sports`, `softball`, `baseball`, `t-ball`, `soccer`, `tennis`, `kickball`, `pickleball`, `frisbee`, `bowling`, `volleyball`, `basketball`, `lacrosse`, `rugby`, `football`, `cricket`, `model-yachting`, `skating`
- Walks/Races/Runs: `walk`, `hike`, `running`, `race`, `marathon`, `cycling`, `youth` (Sport - Youth events)
- Music subtypes (each also adds `music`): `jazz`, `salsa`, `folk`, `hip-hop`, `gospel`, `blues`, `world-music`, `latin-music`. Plus `dance`, `ballet` (also `dance`), `opera` (also `music`)
- Theater subtypes (each also adds `theater`): `shakespeare` (matches play titles like Julius Caesar, Macbeth, Hamlet, etc.), `puppet` (marionette/puppet). Plus `comedy`, `film`, `art`, `performance`
- Charity: `charity`, `gala`, `fundraiser` (e.g., Olmsted Luncheon)
- Family / education: `family`, `birthday`, `school-program`, `education`
- Private bookings: `wedding`, `ceremony`, `memorial`, `reception`, `celebration`, plus `private-booking` (auto-added when category = `private-events`)
- Outdoor / nature: `birds`, `nature`, `garden`, `picnic`, `fishing`, `boating`, `dogs`
- Wellness: `yoga`, `meditation`, `wellness`, `fitness`, `support-group` (resilience/grief/recovery groups)
- Holidays: specific tags `juneteenth`, `halloween`, `thanksgiving`, `easter`, `earth-day` each also emit umbrella `holiday`. Plus `spring`, `fall`
- Annual traditions: `annual-tradition` (Olmsted Luncheon, Open House NY, Pumpkin Flotilla, Holiday Lighting, Harvest Festival, Fall Foliage)
- Cultural communities: `cultural` (South Asian / Latino / AAPI / Black History / etc.), `lgbtq` (pride / queer)
- Gatherings: `social` (meetups / mixers / hangouts), `meeting`, `rally` (demonstrations / protests), `spiritual` (prayer / unity / vigil), `panel`, `talk`, `commemoration`
- Misc: `closure`, `lawn`, `chess`, `free`, `festival`, `parade`, `market`, `food`, `literature`, `media`, `history`, `adventure`
- **The category itself is also added as a tag** so events can be filtered by category-as-tag (e.g., `Sports`, `Runs & Races`, `Concerts & Performances`, `Family & Community`, `Education`, `Private Events`, `Closures`, `Maintenance`). These eight act as the "primary badge" on event cards (first match in that order wins) — they are the only tags rendered as a colored category badge; all others render as plain pills.

**Conservancy:** Start with `conservancy` tag, then add:
- Lowercased, hyphenated versions of the event's `tags` array (e.g., "Kids and Families" → `kids-and-families`)
- `free` if cost is "Free"

**centralpark.com:** Start with `centralpark-com` tag, then add:
- `free` if cost contains "Free" or title contains "Free"
- `zoo` if title or location mentions zoo
- `birds`, `running`, `wellness`, `nature`, `theater`, `skating` based on title keywords

### 7. Clean up titles

Raw event names from the API often contain noise that should be stripped before display. Apply these rules:

- Strip `, DBA Xxx` suffixes (e.g., `James Christie Soccer Training 11 LLC, DBA SocRoc` → `James Christie Soccer Training 11 LLC`)
- Strip trailing `LLC`, `Inc.`, `Corp.` (run twice in case of nested commas)
- Strip year-suffix codes like `Spring26 April` → `Spring April`
- Add space inside CamelCase like `CPSports` → `CP Sports`
- Apply smart title-case: keep known acronyms uppercase (`NYC`, `NYRR`, `CP`, `CPW`, `CPE`, `SSS`, `LLC`, `5K`, `10K`, `AME`, `LGBTQ`, `YMCA`, etc.); lowercase short connecting words (`a`, `an`, `and`, `the`, `of`, etc.) when not first word
- For alphanumeric tokens like `CPW96`, recognize the alpha prefix `CPW` and uppercase the whole token
- Collapse multiple spaces to one

Title cleanup applies to NYC Open Data events. For Conservancy and centralpark.com events, titles come pre-formatted from those sources.

### 8. Merge & deduplicate (preserve curation)

**Key insight:** NYC Open Data API returns multiple records per `event_id` for recurring events — one record per occurrence/date. The unique key for an event occurrence is `(event_id, date)`, not just `event_id`.

Each source uses its own ID namespace:
- NYC Open Data: raw numeric IDs (e.g., `922588`)
- Conservancy: `cpc-` prefix (e.g., `cpc-887607`)
- centralpark.com: `cpcom-` prefix (e.g., `cpcom-bird-watching-with-birding-bob`)

**Merge algorithm:**

1. Build an index: `existing_by_key = { (event_id, date): [list of files] }` from all `.md` files in `_events/`
2. For each API record:
   - Compute `(event_id, date)` key
   - If key matches existing files: keep the first file at its current path, write updated content. Delete duplicate files for the same key.
   - If key is new: create new file with slug `{slugified-cleaned-title}-{YYYY-MM-DD}.md` (with `-2`, `-3` suffixes for same-day collisions)
3. For files NOT matched by any API record: leave them alone (past events, manually-curated entries) but still apply title cleanup
4. **Never rename files** — always update in-place to keep URLs stable
5. **Never delete user-curated events** that originated from non-API sources (Conservancy `cpc-`, centralpark.com `cpcom-`)

The slug format is: `{slugified-event-name}-{YYYY-MM-DD}.md` with a numeric suffix for same-day duplicates (e.g., `-2`, `-3`).

**Public visibility:** All future events show on the public `/events/` page automatically. There is no `display` flag; past events drop off via the `event_date >= now` filter at build time. The `/admin/` page exists only for editing event metadata (title, location, category, etc.).

### 8. Assign images

**NYC Open Data:** Map images based on location keywords:
- Great Lawn → `/assets/images/gallery-1.avif`
- Bandshell → `/assets/images/event-2.avif`
- Bethesda → `/assets/images/plan-visit-hero.avif`
- Bow Bridge → `/assets/images/about-hero.avif`
- Reservoir → `/assets/images/events-hero.avif`
- Harlem/Dana → `/assets/images/gallery-6.avif`
- Cherry Hill → `/assets/images/gallery-7.avif`
- East Meadow → `/assets/images/park-1.avif`
- Cop Cot/Ladies' Pavilion → `/assets/images/gallery-7.avif`
- North Meadow → `/assets/images/park-3.avif`
- Heckscher → `/assets/images/park-2.avif`
- Belvedere → `/assets/images/plan-visit-hero.avif`
- Pilgrim/Cedar Hill → `/assets/images/homepage-park.avif`
- Dene → `/assets/images/gallery-4.avif`
- Fallback by category: runs→`event-1.avif`, concerts→`event-2.avif`, closures→`events-map.avif`, family→`event-3.avif`

**Conservancy:** Use the `image.schema_image` URL from the API if available (these are hosted on CloudFront). Fall back to local images by place category if no external image.

**centralpark.com:** Use local fallback images by place category:
- `event_venues` → `event-3.avif`
- `buildings` → `plan-visit-hero.avif`
- `natural_areas` → `gallery-7.avif`
- `water_bodies` → `gallery-6.avif`
- `meadows_and_lawns` → `gallery-1.avif`
- `recreation` → `park-2.avif`

### 9. Write event files to `_events/`

**Required fields:** every event MUST have a non-empty `description:` (one short sentence). The merge script generates one via `make_description(name, event_type, location)` for any event it writes. The orphan-cleanup pass (Step 10) also backfills missing descriptions on files that aren't in the current API response — so an event ending up without a `description:` should never happen, even for hand-curated files.

Each event becomes a Markdown file in `_events/` with this front matter:

```yaml
---
title: "Event Name"
date: YYYY-MM-DD
time: "HH:MM"
end_time: "HH:MM"
location: "Cleaned Location"
place: "Canonical Place Name"             # primary (first matched token)
place_category: "taxonomy_category"        # primary
places:                                    # OPTIONAL — only when 2+ places matched
  - "Canonical Place Name"
  - "Second Place"
place_categories:                          # OPTIONAL — parallel to `places`
  - "taxonomy_category"
  - "taxonomy_category"
boroughs:                                   # OPTIONAL — populated by NYRR enrichment for multi-borough races
  - "Manhattan"
  - "Brooklyn"
image: "/assets/images/..."
description: "Brief description"
event_id: "123456"
event_type: "Special Event|Sport - Adult|Sport - Youth|Conservancy Event|Community Event"
event_borough: "Manhattan"
source: "data.cityofnewyork.us|centralparknyc.org|centralpark.com"
source_url: "https://..."
cost: "Free"
recurrence: "Saturdays, April through November"
community_board: "64"
police_precinct: "22"
tags:                                       # Title Case strings (single metadata system)
  - "Sports"
  - "Softball"
  - "Youth"
nyrr:                                       # OPTIONAL — present when matched to a record in _data/nyrr-races.json
  event_item_id: "D7ADAFDE-..."
  distance: "10 Kilometers"
  hashtag: "#NYRRManhattan10K"
  course_map: "https://prodsitecore.blob.../race-course-maps/manhattan10k_map_011223.pdf"
  race_photo: "https://prodsitecoreimage.../racepage/photos/manhattan10k22.jpg"
  race_logo: "https://prodsitecoreimage.../race-logos/...png"
  ical_url: "https://www.nyrr.org/api/feature/racedetail/ExportIcal?eventItemId=..."
  strava_club: "https://www.strava.com/clubs/new-york-road-runners-108605"
  source_url: "https://www.nyrr.org/races/2023/nyrrmanhattan10k"
  total_finishers: 4873
  sponsors:
    - "tcs"
    - "new balance"
---

Event body content with details, about section, etc.
```

**Source-specific front matter:**

| Field | NYC Open Data | Conservancy | centralpark.com |
|---|---|---|---|
| `event_type` | "Special Event" / "Sport - Adult" / "Sport - Youth" | "Conservancy Event" | "Community Event" |
| `source` | "data.cityofnewyork.us" | "centralparknyc.org" | "centralpark.com" |
| `source_url` | — | detail page URL | detail page URL |
| `cost` | — | from detail data | from event data |
| `recurrence` | — | — | schedule pattern for recurring events |
| `community_board` | from API | — | — |
| `police_precinct` | from API | — | — |

### 10. Stale events

The merge intentionally **does NOT remove** events that are no longer in the API response, because:
- The user manually curates events via `/admin/`. Removing files would lose their curation.
- Past events naturally drop off the public site via the date filter (`event_date >= now`) on the events page and homepage.

However, you should still touch these orphaned files for two maintenance passes:

1. **Clean titles** — apply the rules from step 7.
2. **Backfill `description:`** — if an orphan file is missing the field or its value is empty, generate one with `make_description(title, event_type, location)` (reading those values from the file's existing front matter, defaulting `event_type` to `""` and `location` to `"Central Park"` if absent). This is what the merge script does in its orphan-cleanup pass; the rule exists so the schema invariant "every event has a non-empty description" never breaks even when files are added or hand-edited outside the merge.

If the user explicitly asks to "purge" or "reset" events, you can offer to delete files where:
- `event_id` does NOT have a `cpc-` or `cpcom-` prefix (so we don't touch Conservancy/centralpark.com)
- AND `event_id` is not in the current API response
- AND `date` is in the past

But default behavior is preservation.

### 11. Build and verify

Run `bundle exec jekyll build` in the project root. Verify:
- The build completes without errors
- The events listing JSON at `_site/events/index.html` contains the expected count
- All events have `place` and `placeCat` fields in the JSON
- Detail pages render at `/events/{slug}/`
- Conservancy events appear with their `conservancy` tag
- centralpark.com events appear with their `centralpark-com` tag

## Important notes

- The `_config.yml` has `future: true` so future-dated events are rendered
- The `Gemfile` includes `kramdown-parser-gfm` for Markdown processing
- The events listing page uses client-side JSON for filtering/pagination — all event data is embedded in a `<script type="application/json">` tag
- The places vocabulary in `_data/central-park-places.yml` is the single source of truth for valid Central Park locations
- If any source returns new locations not in the vocabulary, report them so they can be added
- Conservancy events without a specific date use `2026-06-01` as a placeholder
- centralpark.com recurring events without a specific date use `2026-04-15` as a placeholder
- Cached source data is stored in `_data/`:
  - `_data/central-park-conservancy-events.json` — raw Conservancy API data
  - `_data/centralpark-com-events.json` — raw centralpark.com crawl data
