# Update Events from NYC Open Data, Central Park Conservancy & centralpark.com

Update Central Park Guide events by fetching permitted event data from three sources, filtering against the Central Park places vocabulary, merging (with title cleanup and category mapping), and writing Jekyll collection files. All future events automatically display on the public site — no curation step.

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

# 3. Run the merge
python3 .claude/skills/scripts/merge_nyc_events.py

# 4. Build to verify
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

### Source 2: Central Park Conservancy (centralparknyc.org)

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

### Source 3: centralpark.com (Community Events)

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

## Steps

### 1. Fetch events from all three sources

**NYC Open Data:** Use WebFetch to pull all Central Park events from the Socrata API. Paginate with `$offset` until fewer than 1000 results are returned.

```
https://data.cityofnewyork.us/resource/tvpp-9vvx.json?$where=event_location%20like%20%27Central%20Park%25%27&$limit=1000&$offset=0
```

**Conservancy:** Fetch `https://www.centralparknyc.org/activities.json?page=1` through all pages. Filter to event types only. Then fetch each event's detail URL to get enriched data.

**centralpark.com:** Fetch the listing pages at `https://www.centralpark.com/search/event/upcoming-events/` (paginate through all pages) or use the RSS feed. Then fetch each event's detail page for full data including schedule, cost, and location details.

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

### 5. Categorize events

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

**NYC Open Data:** Build a tag list from event name, type, and category:
- Sports: `sports`, `softball`, `baseball`, `t-ball`, `soccer`, `tennis`, `kickball`, `pickleball`, `frisbee`, `bowling`, `model-yachting`, `skating`
- Music & performance: `music`, `dance`, `salsa`, `theater`, `festival`
- Private bookings: `wedding`, `private-booking` (auto-added when category = `private-events`)
- Education: `school-program` (for SSS series, mini-camps, training)
- Annual traditions: `annual-tradition` (Olmsted Luncheon, Pumpkin Flotilla, Cherry Blossom, Fall Foliage, Juneteenth, Holiday Lighting, Open House, Harvest Festival)
- Misc: `closure`, `lawn`, `chess`, `wellness`, `dogs`, `running`, `free`

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
category: "sports|runs-races|concerts-performances|family-community|education|private-events|closures|maintenance"
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
tags:
  - tag1
  - tag2
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

However, you should still **clean titles** on these orphaned files (apply the title cleanup rules from step 7 even when not refreshing other fields).

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
