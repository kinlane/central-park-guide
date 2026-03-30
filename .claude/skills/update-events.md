# Update Events from NYC Open Data, Central Park Conservancy & centralpark.com

Update Central Park Guide events by fetching permitted event data from three sources, filtering against the Central Park places vocabulary, deduplicating, and writing Jekyll collection files.

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

For each event, check if its cleaned location contains any place name token (case-insensitive). If matched, record the canonical `place` name and `place_category`. If no match, **skip the event** — it doesn't map to a known Central Park location.

If an event location doesn't match and looks like it should (a real Central Park sub-location), consider adding it to `_data/central-park-places.yml` under the `event_venues` category before re-matching.

### 5. Categorize events

**NYC Open Data:**
- `event_type` is "Sport - Adult" or "Sport - Youth" → `runs-races`
- `event_name` contains lawn/meadow closure keywords → `closures`
- `event_name` contains music/concert/dance/band/festival keywords → `concerts-performances`
- `event_name` contains wedding/elopement/ceremony → `family-community`
- Default → `family-community`

**Conservancy:**
- `type` contains "Arts & Entertainment" → `concerts-performances`
- `type` contains "Benefit" → `family-community`
- Default → `family-community`

**centralpark.com:**
- Title contains run/race/running/fitness/yoga/pickleball/tennis → `runs-races`
- Title contains shakespeare/theater/marionette/concert → `concerts-performances`
- Default → `family-community`

### 6. Assign tags

**NYC Open Data:** Build a tag list from event name and type:
- Sports: `sports`, `softball`, `baseball`, `soccer`, `tennis`, `kickball`
- Music: `music`, `dance`, `festival`
- Weddings: `wedding`
- Closures: `closure`, `lawn`
- Community: `community`, `chess`, `wellness`, `dogs`

**Conservancy:** Start with `conservancy` tag, then add:
- Lowercased, hyphenated versions of the event's `tags` array (e.g., "Kids and Families" → `kids-and-families`)
- `free` if cost is "Free"

**centralpark.com:** Start with `centralpark-com` tag, then add:
- `free` if cost contains "Free" or title contains "Free"
- `zoo` if title or location mentions zoo
- `birds`, `running`, `wellness`, `nature`, `theater`, `skating` based on title keywords

### 7. Deduplicate

Use `event_id` as the unique key. Each source has its own prefix to avoid collisions:
- NYC Open Data: raw numeric IDs (e.g., `922588`)
- Conservancy: `cpc-` prefix (e.g., `cpc-887607`)
- centralpark.com: `cpcom-` prefix (e.g., `cpcom-bird-watching-with-birding-bob`)

If a file already exists for the same `event_id`, compare the existing front matter against the new data. Only overwrite if the data has changed (different date, time, location, or name). This prevents unnecessary git churn.

The slug format is: `{slugified-event-name}-{YYYY-MM-DD}.md` with a numeric suffix for same-day duplicates (e.g., `-2`, `-3`).

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
place: "Canonical Place Name"
place_category: "taxonomy_category"
category: "runs-races|concerts-performances|family-community|closures"
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

### 10. Remove stale events

After writing all current events, scan `_events/` for any `.md` files whose `event_id` is NOT in the current combined response from all three sources. Remove those files — they've been cancelled or are no longer in the datasets.

**Important:** Each source manages its own ID namespace. Only compare:
- Raw numeric IDs against NYC Open Data results
- `cpc-` prefixed IDs against Conservancy results
- `cpcom-` prefixed IDs against centralpark.com results

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
