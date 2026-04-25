"""
Merge latest NYC Open Data events into the central-park-guide _events/ directory.

- Cleans up event titles (removes LLC/DBA suffixes, normalizes case)
- Maps event types to site categories (sports, runs-races, etc.)
- Matches locations against the places vocabulary
- Adds new events; updates existing events with refreshed data
- Never deletes Conservancy (cpc-) or centralpark.com (cpcom-) events

Usage:
  1. Fetch latest events from NYC Open Data API to /tmp/central_park_events_latest.json:
       Loop offset = 0, 1000, 2000... until <1000 returned. Combine into JSON array.
       API: https://data.cityofnewyork.us/resource/tvpp-9vvx.json
       Filter: event_location like 'Central Park%'
  2. Run: python3 .claude/skills/scripts/merge_nyc_events.py
"""

import json
import yaml
import os
import re
from datetime import datetime
from collections import defaultdict

# Resolve paths relative to script location (../../.. is the repo root)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..', '..'))

LATEST_JSON = '/tmp/central_park_events_latest.json'
PLACES_PATH = os.path.join(REPO_ROOT, '_data', 'central-park-places.yml')
EVENTS_DIR = os.path.join(REPO_ROOT, '_events')

# ── Load places vocabulary ────────────────────────────────────────────
with open(PLACES_PATH) as f:
    places_data = yaml.safe_load(f)

place_lookup = {}
for category, items in places_data.items():
    if not isinstance(items, list):
        continue
    for item in items:
        key = item['name'].lower()
        entry = {'name': item['name'], 'category': category}
        place_lookup[key] = entry
        for alt in item.get('alternate_names', []):
            place_lookup[alt.lower()] = entry

search_tokens = sorted(place_lookup.keys(), key=len, reverse=True)


def match_place(location):
    loc_lower = location.lower()
    for token in search_tokens:
        if token in loc_lower:
            return place_lookup[token]
    return None


# ── Title cleanup ──────────────────────────────────────────────────────
KEEP_UPPER = {'NYC', 'NYRR', 'CP', 'CPW', 'CPE', 'CPN', 'CPS', 'LLC', 'DBA',
              'USA', 'EU', '4D', '5K', '10K', '15K', 'AME', 'DJ', 'LGBTQ',
              'NPR', 'PR', 'SSS', 'CPR', 'YMCA', 'NYU', 'CUNY', 'AIDS', 'IRC',
              'MGP', 'GSB', 'HS', 'MSA', 'CPC', 'TGI'}

def smart_title_case(text):
    """Title case but preserve known acronyms and short connecting words."""
    text = text.strip()
    if not text:
        return text
    # Lowercase connecting words
    small_words = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in',
                   'of', 'on', 'or', 'the', 'to', 'with', 'vs'}
    words = text.split()
    result = []
    for i, w in enumerate(words):
        clean = re.sub(r'[^\w]', '', w)
        # Get just the leading alphabetic part (handles "CPW96")
        alpha_prefix_match = re.match(r'^([A-Za-z]+)', clean)
        alpha_prefix = alpha_prefix_match.group(1).upper() if alpha_prefix_match else ''

        if clean.upper() in KEEP_UPPER:
            result.append(re.sub(r'\w+', clean.upper(), w))
        elif alpha_prefix in KEEP_UPPER and len(alpha_prefix) >= 2 and alpha_prefix != clean.upper():
            # E.g. "CPW96" -> alpha "CPW" is in KEEP_UPPER, so uppercase the whole word
            result.append(w.upper())
        elif i > 0 and clean.lower() in small_words:
            result.append(w.lower())
        else:
            if w and w[0].isalpha():
                result.append(w[0].upper() + w[1:].lower())
            else:
                result.append(w)
    return ' '.join(result)


def clean_title(name):
    """Clean up an event title from raw NYC data."""
    title = name.strip()

    # Strip "DBA Xxx" first (often comes after LLC) -- "...LLC, DBA SocRoc" -> "...LLC"
    title = re.sub(r',?\s+DBA\s+.*$', '', title, flags=re.IGNORECASE)

    # Now strip ", LLC" / " LLC" suffixes (run twice in case of nested commas)
    for _ in range(2):
        title = re.sub(r',?\s+LLC\.?\s*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r',?\s+Inc\.?\s*$', '', title, flags=re.IGNORECASE)
        title = re.sub(r',?\s+Corp\.?\s*$', '', title, flags=re.IGNORECASE)

    # Strip generic season-year codes like "Spring26 April" -> "Spring April"
    title = re.sub(r'\b(Spring|Summer|Fall|Winter)\d+\b', r'\1', title, flags=re.IGNORECASE)

    # Add space inside CamelCase like "CPSports" -> "CP Sports"
    title = re.sub(r'([A-Z]{2,})([A-Z][a-z])', r'\1 \2', title)

    # Strip leading/trailing punctuation residue
    title = re.sub(r'^[,\s\-]+|[,\s\-]+$', '', title)

    # Title case
    title = smart_title_case(title)

    # Collapse multiple spaces
    title = re.sub(r'\s+', ' ', title)

    return title


# ── Categorization ─────────────────────────────────────────────────────
SPORT_KEYWORDS = ['softball', 'baseball', 'kickball', 'soccer', 'tennis',
                  't-ball', 't ball', 'pickleball', 'volleyball', 'basketball',
                  'lacrosse', 'rugby', 'cricket', 'frisbee', 'ultimate',
                  'football', 'flag football']

def categorize(name, event_type):
    name_lower = name.lower()
    name_stripped = name_lower.strip()

    # Maintenance: explicit upkeep events
    if 'maintenance' in name_lower:
        return 'maintenance'

    # Closures: lawn/meadow closures
    if 'lawn closure' in name_lower or 'meadow closure' in name_lower:
        return 'closures'

    # Education: school programs, training, mini-camps
    edu_signals = ['sss cpe', 'sss cpw', 'mini-camp', 'mini camp',
                   'soc-roc', 'socroc', 'soccer training', 'sports training']
    if any(s in name_lower for s in edu_signals):
        return 'education'

    # Private events: ceremonies, parties, picnics, weddings
    private_signals = ['celebration', 'wedding', 'elopement', 'ceremony',
                       'birthday', 'micro wedding', 'baptism', 'memorial',
                       'bar mitzvah', 'bat mitzvah', 'reception']
    if any(s in name_lower for s in private_signals):
        return 'private-events'
    if name_stripped in ('party', 'picnic', 'miscellaneous'):
        return 'private-events'

    # Sports: leagues, training (after edu/private filter to catch sports private events first)
    if event_type in ('Sport - Adult', 'Sport - Youth'):
        return 'sports'
    if any(kw in name_lower for kw in SPORT_KEYWORDS):
        return 'sports'

    # Concerts & performances
    if any(w in name_lower for w in ['concert', 'music', 'jazz', 'salsa',
                                     'band', 'choir', 'festival', 'dance',
                                     'theater', 'theatre', 'songwriters',
                                     'tapes', 'dj', 'entertainment', 'opera',
                                     'symphonic', 'marching', 'shakespeare',
                                     'marionette', 'puppet']):
        return 'concerts-performances'

    # Runs & races
    if any(w in name_lower for w in ['5k', '10k', 'marathon', ' run ', 'race',
                                     'half marathon']):
        return 'runs-races'

    return 'family-community'


def get_tags(name, event_type, category=None):
    n = name.lower()
    tags = []
    if event_type == 'Sport - Adult': tags.append('sports')
    if event_type == 'Sport - Youth': tags.extend(['sports', 'youth'])
    # Sport types
    if 'softball' in n: tags.append('softball')
    if 'baseball' in n: tags.append('baseball')
    if 't-ball' in n or 't ball' in n: tags.append('t-ball')
    if 'soccer' in n: tags.append('soccer')
    if 'tennis' in n: tags.append('tennis')
    if 'kickball' in n: tags.append('kickball')
    if 'pickleball' in n: tags.append('pickleball')
    if 'frisbee' in n: tags.append('frisbee')
    if 'bowling' in n and 'lawn' not in n: tags.append('bowling')
    if 'model yacht' in n or 'yacht racing' in n: tags.append('model-yachting')
    if any(w in n for w in ['roller', 'skate circle', 'cpdsa', 'skating']): tags.append('skating')
    # Music & performance
    if any(w in n for w in ['music', 'concert', 'jazz', 'band', 'choir', 'symphonic']):
        tags.append('music')
    if 'salsa' in n: tags.append('salsa')
    if 'dance' in n: tags.append('dance')
    if any(w in n for w in ['shakespeare', 'julius caesar', 'midsummer', 'macbeth',
                            'hamlet', 'marionette', 'puppet', 'theater', 'theatre']):
        tags.append('theater')
    # Weddings & private
    if any(w in n for w in ['wedding', 'elopement', 'ceremony']): tags.append('wedding')
    if category == 'private-events': tags.append('private-booking')
    # School programs
    if any(s in n for s in ['sss cpe', 'sss cpw', 'mini-camp', 'mini camp',
                            'school', 'cpsports', 'soccer training']):
        tags.append('school-program')
    # Annual traditions
    annuals = ['frederick law olmsted', 'great pumpkin', 'harvest festival',
               'pumpkin flotilla', 'holiday lighting', 'open house',
               'juneteenth', 'cherry blossom', 'fall foliage']
    if any(s in n for s in annuals): tags.append('annual-tradition')
    # Misc
    if 'festival' in n: tags.append('festival')
    if 'lawn closure' in n or 'meadow closure' in n: tags.extend(['closure', 'lawn'])
    if 'free' in n: tags.append('free')
    if 'chess' in n: tags.append('chess')
    if 'yoga' in n: tags.append('wellness')
    if 'bark' in n or 'dog' in n: tags.append('dogs')
    if 'race' in n or 'marathon' in n or '5k' in n or '10k' in n: tags.append('running')
    if not tags: tags.append('community')
    return list(set(tags))


def clean_location(loc):
    parts = [p.strip() for p in loc.split(',')]
    cleaned = []
    for p in parts:
        p = re.sub(r'^Central Park:\s*', '', p.strip())
        if p:
            cleaned.append(p)
    return ', '.join(cleaned[:2])


def get_image(category, location):
    loc_lower = location.lower()
    if 'great lawn' in loc_lower: return '/assets/images/gallery-1.avif'
    if 'bandshell' in loc_lower: return '/assets/images/event-2.avif'
    if 'bethesda' in loc_lower: return '/assets/images/plan-visit-hero.avif'
    if 'bow bridge' in loc_lower: return '/assets/images/about-hero.avif'
    if 'reservoir' in loc_lower: return '/assets/images/events-hero.avif'
    if 'harlem' in loc_lower or 'dana' in loc_lower: return '/assets/images/gallery-6.avif'
    if 'cherry' in loc_lower: return '/assets/images/gallery-7.avif'
    if 'meadow' in loc_lower and 'sheep' not in loc_lower: return '/assets/images/park-1.avif'
    if 'sheep' in loc_lower: return '/assets/images/gallery-1.avif'
    if 'delacorte' in loc_lower: return '/assets/images/event-3.avif'
    if 'cop cot' in loc_lower or 'ladies' in loc_lower: return '/assets/images/gallery-7.avif'
    if 'north meadow' in loc_lower: return '/assets/images/park-3.avif'
    if 'heckscher' in loc_lower: return '/assets/images/park-2.avif'
    if 'belvedere' in loc_lower: return '/assets/images/plan-visit-hero.avif'
    if 'pilgrim' in loc_lower or 'cedar' in loc_lower: return '/assets/images/homepage-park.avif'
    if 'dene' in loc_lower: return '/assets/images/gallery-4.avif'
    images = {
        'sports': '/assets/images/event-1.avif',
        'runs-races': '/assets/images/event-1.avif',
        'concerts-performances': '/assets/images/event-2.avif',
        'closures': '/assets/images/events-map.avif',
        'family-community': '/assets/images/event-3.avif',
    }
    return images.get(category, '/assets/images/event-3.avif')


def make_description(name, event_type, location):
    if 'lawn closure' in name.lower() or 'meadow closure' in name.lower():
        return "Scheduled lawn closure at " + location + " for maintenance and restoration."
    if event_type == 'Sport - Adult':
        return name + " at " + location + ". Adult league permitted event in Central Park."
    if event_type == 'Sport - Youth':
        return name + " at " + location + ". Youth league permitted event in Central Park."
    if 'wedding' in name.lower() or 'elopement' in name.lower():
        return "Private ceremony at " + location + " in Central Park."
    return name + " at " + location + " in Central Park."


def yaml_safe(text):
    return text.replace('\\', '\\\\').replace('"', '\\"')


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text[:80].strip('-')


# ── Index existing events by (event_id + date) since events recur ──────
existing_by_key = {}  # (event_id, date) -> { 'path': ..., 'content': ... }
existing_event_ids = set()  # all event_ids seen in directory (for "left alone" detection)
for fname in sorted(os.listdir(EVENTS_DIR)):
    if not fname.endswith('.md'):
        continue
    filepath = os.path.join(EVENTS_DIR, fname)
    with open(filepath) as f:
        content = f.read()
    eid_match = re.search(r'^event_id:\s*"(.+?)"', content, re.MULTILINE)
    if not eid_match:
        continue
    eid = eid_match.group(1)
    existing_event_ids.add(eid)
    date_match = re.search(r'^date:\s*(\S+)', content, re.MULTILINE)
    date = date_match.group(1) if date_match else ''
    key = (eid, date)
    existing_by_key.setdefault(key, []).append({
        'path': filepath,
        'fname': fname,
        'content': content,
    })

dup_count = sum(1 for files in existing_by_key.values() if len(files) > 1)
total_files = sum(len(files) for files in existing_by_key.values())
print(f"Indexed {total_files} files across {len(existing_by_key)} unique (event_id, date) combos ({dup_count} duplicates)")


# ── Process latest events from API ────────────────────────────────────
with open(LATEST_JSON) as f:
    latest = json.load(f)

print(f"Loaded {len(latest)} latest events from API")

slug_counts = defaultdict(int)
created = 0
updated = 0
skipped_unmatched = 0
skipped_invalid = 0
unmatched_locs = set()
api_event_ids = set()
api_keys = set()

# Pre-allocate slug counts from existing files (so we don't collide)
for fname in os.listdir(EVENTS_DIR):
    if fname.endswith('.md'):
        # Strip the trailing -N suffix and -YYYY-MM-DD
        base = fname[:-3]  # remove .md
        m = re.match(r'^(.+?-\d{4}-\d{2}-\d{2})(?:-(\d+))?$', base)
        if m:
            slug_counts[m.group(1)] = max(slug_counts[m.group(1)], int(m.group(2)) if m.group(2) else 1)

for event in latest:
    eid = event.get('event_id', '')
    if not eid:
        skipped_invalid += 1
        continue

    api_event_ids.add(eid)
    # api_keys updated below once date_str is computed

    raw_name = event.get('event_name', 'Event')
    name = clean_title(raw_name)
    raw_location = event.get('event_location', '')
    location = clean_location(raw_location)
    event_type = event.get('event_type', '')

    try:
        start = datetime.fromisoformat(event['start_date_time'].replace('.000', ''))
        end = datetime.fromisoformat(event['end_date_time'].replace('.000', ''))
    except Exception:
        skipped_invalid += 1
        continue

    place = match_place(location)
    if not place:
        skipped_unmatched += 1
        unmatched_locs.add(location)
        continue

    category = categorize(name, event_type)
    tags = get_tags(name, event_type, category)
    image = get_image(category, location)
    description = make_description(name, event_type, location)
    date_str = start.strftime('%Y-%m-%d')
    time_str = start.strftime('%H:%M')
    end_time_str = end.strftime('%H:%M')
    cb = event.get('community_board', '').rstrip(', ')
    pp = event.get('police_precinct', '').rstrip(', ')

    key = (eid, date_str)
    api_keys.add(key)
    is_new = key not in existing_by_key

    lines = []
    lines.append('---')
    lines.append('title: "' + yaml_safe(name) + '"')
    lines.append('date: ' + date_str)
    lines.append('time: "' + time_str + '"')
    lines.append('end_time: "' + end_time_str + '"')
    lines.append('location: "' + yaml_safe(location) + '"')
    lines.append('place: "' + yaml_safe(place['name']) + '"')
    lines.append('place_category: "' + place['category'] + '"')
    lines.append('category: "' + category + '"')
    lines.append('image: "' + image + '"')
    lines.append('description: "' + yaml_safe(description) + '"')
    lines.append('event_id: "' + eid + '"')
    lines.append('event_type: "' + event_type + '"')
    lines.append('event_borough: "Manhattan"')
    lines.append('community_board: "' + cb + '"')
    lines.append('police_precinct: "' + pp + '"')
    lines.append('tags:')
    for tag in tags:
        lines.append('  - ' + tag)
    lines.append('---')
    lines.append('')
    lines.append(name + ' takes place at ' + location + ' in Central Park on ' + start.strftime('%A, %B %-d, %Y') + '.')
    lines.append('')
    lines.append('## Event Details')
    lines.append('')
    lines.append('- **Event:** ' + name)
    lines.append('- **Date:** ' + start.strftime('%A, %B %-d, %Y'))
    lines.append('- **Time:** ' + start.strftime('%-I:%M %p') + ' - ' + end.strftime('%-I:%M %p'))
    lines.append('- **Location:** ' + location + ', Central Park')
    lines.append('- **Place:** ' + place['name'])
    lines.append('- **Type:** ' + event_type)
    lines.append('- **Event ID:** ' + eid)
    lines.append('')

    if category == 'closures':
        lines.append('## What to Know')
        lines.append('')
        lines.append('This is a scheduled closure or restricted access event. Please plan alternative routes if you typically use this area of the park during the closure period.')
    elif 'Sport' in event_type or category == 'sports':
        lines.append('## About This Event')
        lines.append('')
        lines.append('This is a permitted ' + (event_type.lower() if event_type else 'sports') + ' event at ' + location + '. The area may have restricted access during the event period.')
    else:
        lines.append('## About This Event')
        lines.append('')
        lines.append(name + ' is a permitted event taking place at ' + location + ' in Central Park. Contact the event organizers for more details about attendance and participation.')
    lines.append('')

    new_content = '\n'.join(lines)

    if is_new:
        # Create new file with new slug
        base_slug = slugify(name) + '-' + date_str
        slug_counts[base_slug] += 1
        slug = base_slug if slug_counts[base_slug] == 1 else base_slug + '-' + str(slug_counts[base_slug])
        filepath = os.path.join(EVENTS_DIR, slug + '.md')
        with open(filepath, 'w') as f:
            f.write(new_content)
        created += 1
    else:
        # Update first file matching (event_id, date), delete any duplicates
        existing_files = existing_by_key[key]
        keeper = existing_files[0]
        if keeper['content'] != new_content:
            with open(keeper['path'], 'w') as f:
                f.write(new_content)
            updated += 1
        for dup in existing_files[1:]:
            try:
                os.remove(dup['path'])
            except FileNotFoundError:
                pass

# Clean titles in events left alone (file not matched by an API record)
title_only_cleaned = 0
left_alone_count = 0
for key, files in existing_by_key.items():
    if key in api_keys:
        continue
    left_alone_count += len(files)
    for info in files:
        content = info['content']
        title_match = re.search(r'^title:\s*"(.+?)"', content, re.MULTILINE)
        if not title_match:
            continue
        raw_title = title_match.group(1).replace('\\"', '"')
        cleaned = clean_title(raw_title)
        if cleaned != raw_title:
            new_content = re.sub(
                r'^title:\s*".*?"',
                'title: "' + yaml_safe(cleaned) + '"',
                content,
                count=1,
                flags=re.MULTILINE,
            )
            with open(info['path'], 'w') as f:
                f.write(new_content)
            title_only_cleaned += 1

print(f"\nMerge results:")
print(f"  Created (new events): {created}")
print(f"  Updated (existing events refreshed): {updated}")
print(f"  Total API events processed: {len(latest)}")
print(f"  Files not in API (titles cleaned): {title_only_cleaned} cleaned, {left_alone_count} files left alone")
print(f"  Skipped (location unmatched): {skipped_unmatched}")
print(f"  Skipped (invalid data): {skipped_invalid}")
if unmatched_locs:
    print(f"\n  Unmatched locations:")
    for loc in sorted(unmatched_locs):
        print(f"    {loc}")


# Final breakdown
from collections import Counter
cats = Counter()
total = 0
for fname in os.listdir(EVENTS_DIR):
    if not fname.endswith('.md'): continue
    total += 1
    with open(os.path.join(EVENTS_DIR, fname)) as f:
        for line in f:
            m = re.match(r'^category:\s*"(.+?)"', line)
            if m:
                cats[m.group(1)] += 1
                break

print(f"\nTotal events in _events/: {total}")
print(f"By category:")
for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {count}")
