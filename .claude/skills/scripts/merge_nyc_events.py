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
NYRR_JSON_PATH = os.path.join(REPO_ROOT, '_data', 'nyrr-races.json')

BOROUGHS = ['Manhattan', 'Brooklyn', 'Queens', 'Bronx', 'Staten Island']

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


def match_places(location):
    """Return all distinct vocabulary places mentioned in the location string,
    ordered by their position in the source. Greedy longest-first to avoid
    shorter tokens overlapping a longer match."""
    loc = list(location.lower())
    matches = []  # (index, name, category)
    seen = set()
    for token in search_tokens:  # longest-first
        text = ''.join(loc)
        idx = text.find(token)
        if idx < 0:
            continue
        entry = place_lookup[token]
        if entry['name'] not in seen:
            matches.append((idx, entry['name'], entry['category']))
            seen.add(entry['name'])
        # Mask the matched span so shorter tokens can't overlap-claim it
        for i in range(idx, idx + len(token)):
            loc[i] = ' '
    matches.sort(key=lambda m: m[0])
    return [{'name': n, 'category': c} for _, n, c in matches]


def match_place(location):
    """Back-compat: first matched place, or None."""
    matches = match_places(location)
    return matches[0] if matches else None


# ── NYRR enrichment ────────────────────────────────────────────────────
def load_nyrr_cache():
    if not os.path.exists(NYRR_JSON_PATH):
        return {}
    with open(NYRR_JSON_PATH) as f:
        data = json.load(f)
    return data.get('races', {}) if isinstance(data, dict) else {}


nyrr_cache = load_nyrr_cache()


def derive_nyrr_slug(title):
    """NYRR slugs strip everything but lowercase alphanumerics; year prefix removed."""
    t = re.sub(r'^\s*20\d\d\s+', '', title or '')
    return re.sub(r'[^A-Za-z0-9]', '', t).lower()


def find_nyrr_record(title, year):
    """Look up a NYRR record by ({year}{slug}, then {slug} alone). Returns dict or None."""
    slug = derive_nyrr_slug(title)
    if not slug:
        return None
    candidates = [f'{year}{slug}'] if year else []
    candidates.append(slug)
    # Also try previous-year cache as a fallback for recurring annual races
    if year:
        candidates.append(f'{year - 1}{slug}')
    for k in candidates:
        rec = nyrr_cache.get(k)
        if rec and rec.get('parsed'):
            return rec
    return None


def enrich_places_from_nyrr(rec):
    """Tokenize NYRR description + course text against the places vocabulary.
    Returns ([{name,category}, ...], [borough, ...])."""
    blob = ' '.join(
        v for k, v in rec.items()
        if isinstance(v, str) and k in ('description', 'course_text', 'location')
    )
    landmarks = match_places(blob) if blob else []
    boroughs = []
    for b in (rec.get('boroughs') or []):
        if b in BOROUGHS and b not in boroughs:
            boroughs.append(b)
    # Also catch boroughs by direct text scan (in case rec.boroughs missed them)
    for b in BOROUGHS:
        if b not in boroughs and re.search(r'\b' + re.escape(b) + r'\b', blob, re.I):
            boroughs.append(b)
    return landmarks, boroughs


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

    # Runs / races / walks (BEFORE sports/concerts so "Band of Parents 4 Mile Run Walk"
    # doesn't fall into concerts-performances on "band")
    if re.search(r'\b(walk|run|race|5k|10k|15k|half|marathon|jog)\b', name_lower):
        # but skip if it's actually a training/lesson/class
        if not any(w in name_lower for w in ['training', 'lesson', 'class ', 'course']):
            return 'runs-races'

    # Education: school programs, training, mini-camps
    edu_signals = ['sss cpe', 'sss cpw', 'mini-camp', 'mini camp',
                   'soc-roc', 'socroc', 'soccer training', 'sports training',
                   'training', 'tutorial']
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

    # Sports: leagues (event_type) or sport keywords
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

    return 'family-community'


TAG_RULES = [
    # Sports
    (r'\bsoftball\b', 'softball'),
    (r'\bbaseball\b', 'baseball'),
    (r't[ -]?ball\b', 't-ball'),
    (r'\bsoccer\b', 'soccer'),
    (r'\btennis\b', 'tennis'),
    (r'\bkickball\b', 'kickball'),
    (r'\bpickleball\b', 'pickleball'),
    (r'\bbasketball\b', 'basketball'),
    (r'\bvolleyball\b', 'volleyball'),
    (r'\blacrosse\b', 'lacrosse'),
    (r'\brugby\b', 'rugby'),
    (r'\bfootball\b', 'football'),
    (r'\bcricket\b', 'cricket'),
    (r'\bfrisbee\b', 'frisbee'),
    (r'\bultimate\b', 'frisbee'),
    (r'\b(yacht\s*racing|model\s*yacht)\b', 'model-yachting'),
    (r'\b(skating|skate\s*circle|cpdsa|roller)\b', 'skating'),
    (r'\bbowling\b(?!.*\bgreen\b)', 'bowling'),
    # Walking / running / racing
    (r'\bwalk\b', 'walk'),
    (r'\bhike\b', 'hike'),
    (r'\brun\b(?!\w)', 'running'),
    (r'\brunning\b', 'running'),
    (r'\brace\b', 'race'),
    (r'\bmarathon\b', 'marathon'),
    (r'\b(5k|10k|15k|half\s*marathon)\b', 'race'),
    (r'\bjog(ger|ging)?\b', 'running'),
    # Music / performance
    (r'\bjazz\b', 'jazz'),
    (r'\bsalsa\b', 'salsa'),
    (r'\bdance\b', 'dance'),
    (r'\b(concert|symphonic|symphony|orchestra|philharmonic|band|choir|dj|songwriter|musical|blues|folk|bluegrass|country|rap|hip[\s-]?hop|gospel)\b', 'music'),
    (r'\b(opera|operatic)\b', 'opera'),
    (r'\b(theater|theatre|shakespeare|julius caesar|midsummer|macbeth|hamlet|romeo|king lear|othello|tempest|twelfth night|much ado|marionette|puppet|drama)\b', 'theater'),
    (r'\b(film|movie|cinema|screening)\b', 'film'),
    (r'\b(art|exhibit|gallery)\b', 'art'),
    (r'\bperformance\b', 'performance'),
    # Charity / fundraising
    (r'\b(charity|fundrais|gala|benefit|donation)\b', 'charity'),
    (r'\bluncheon\b', 'fundraiser'),
    # Family / kids
    (r'\b(kid|children|family|families)\b', 'family'),
    (r'\bbirthday\b', 'birthday'),
    (r'\b(school|hs\b|high school|middle school|elementary)\b', 'school-program'),
    (r'\b(camp|mini-?camp|workshop|class|lesson|training|tutorial)\b', 'education'),
    (r'\b(sss\s*cp|cpsports)\b', 'school-program'),
    # Private / ceremony
    (r'\bwedding\b', 'wedding'),
    (r'\belopement\b', 'wedding'),
    (r'\bceremony\b', 'ceremony'),
    (r'\b(memorial|funeral|tribute)\b', 'memorial'),
    (r'\bbar\s*mitzvah|bat\s*mitzvah\b', 'ceremony'),
    (r'\b(reception|engagement)\b', 'celebration'),
    (r'\b(party|celebration|reunion)\b', 'celebration'),
    (r'\bbaptism\b', 'ceremony'),
    # Outdoor / nature
    (r'\b(bird|birding|birds)\b', 'birds'),
    (r'\bnature\b', 'nature'),
    (r'\bgarden\b', 'garden'),
    (r'\b(picnic|cook[\s-]?out|bbq|barbecue|barbeque)\b', 'picnic'),
    (r'\b(fish|fishing)\b', 'fishing'),
    (r'\b(boat|boating|kayak|rowing|paddle)\b', 'boating'),
    # Wellness
    (r'\byoga\b', 'wellness'),
    (r'\b(meditat|mindful)\b', 'wellness'),
    (r'\bfitness\b', 'fitness'),
    (r'\b(zumba|aerobic|pilates)\b', 'fitness'),
    (r'\bstretch\b', 'wellness'),
    # Holidays
    (r'\b(holiday|christmas|hanukkah|kwanzaa|halloween|thanksgiving|easter|juneteenth)\b', 'holiday'),
    (r'\b(pumpkin|harvest)\b', 'fall'),
    (r'\b(cherry blossom|blossom)\b', 'spring'),
    # Pets
    (r'\bdog\b', 'dogs'),
    (r'\bbark\b', 'dogs'),
    # Annual traditions
    (r'\b(annual|tradition)\b', 'annual-tradition'),
    (r'\b(frederick law olmsted|olmsted)\b', 'annual-tradition'),
    (r'\b(open house ny|ohny)\b', 'annual-tradition'),
    (r'\b(great pumpkin|harvest festival|pumpkin flotilla|holiday lighting|fall foliage)\b', 'annual-tradition'),
    # Communities
    (r'\b(LGBTQ|pride|queer)\b', 'lgbtq'),
    # Free
    (r'\bfree\b', 'free'),
    # Closures / maintenance
    (r'\b(lawn closure|meadow closure)\b', 'closure'),
    (r'\bmaintenance\b', 'maintenance'),
    # Other
    (r'\b(chess|checkers)\b', 'chess'),
    (r'\b(festival|fair)\b', 'festival'),
    (r'\b(parade|march)\b', 'parade'),
    (r'\b(speech|talk|lecture|seminar|panel|forum)\b', 'talk'),
    (r'\b(book|reading|poetry|writer)\b', 'literature'),
    (r'\b(food\s*truck|culinary|cooking)\b', 'food'),
    (r'\b(market|farmers\s*market|farm\s*stand)\b', 'market'),
    (r'\b(bike|biking|cycling|cyclist)\b', 'cycling'),
    (r'\b(media|press|interview)\b', 'media'),
]

def get_tags(name, event_type, category=None):
    text = (name + ' ' + (event_type or '')).lower()
    tags = set()
    for pattern, tag in TAG_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            tags.add(tag)
    # Sport-type roll-up
    if event_type in ('Sport - Adult', 'Sport - Youth'):
        tags.add('sports')
        if event_type == 'Sport - Youth':
            tags.add('youth')
    if tags & {'softball','baseball','t-ball','soccer','tennis','kickball','pickleball','basketball','volleyball','lacrosse','rugby','football','cricket'}:
        tags.add('sports')
    # Category-based tags
    if category == 'private-events':
        tags.add('private-booking')
    if category == 'closures':
        tags.add('closure')
    if category == 'maintenance':
        tags.add('maintenance')
    if category == 'education':
        tags.add('education')
    # Fallback
    if not tags:
        tags.add('community')
    return sorted(tags)


def clean_location(loc):
    parts = [p.strip() for p in loc.split(',')]
    cleaned = []
    for p in parts:
        p = re.sub(r'^Central Park:\s*', '', p.strip())
        if p:
            cleaned.append(p)
    return ', '.join(cleaned[:2])


CAT_IMAGES_DIR = '/assets/images/categories'
TAG_IMAGES_DIR = '/assets/images/tags'

# Available tag images (kept in sync with assets/images/tags/)
HAVE_TAG_IMAGES = set()
HAVE_CAT_IMAGES = set()
_tag_path = os.path.join(REPO_ROOT, 'assets', 'images', 'tags')
_cat_path = os.path.join(REPO_ROOT, 'assets', 'images', 'categories')
if os.path.isdir(_tag_path):
    for _f in os.listdir(_tag_path):
        if _f.endswith('.png'):
            HAVE_TAG_IMAGES.add(_f[:-4])
if os.path.isdir(_cat_path):
    for _f in os.listdir(_cat_path):
        if _f.endswith('.png'):
            HAVE_CAT_IMAGES.add(_f[:-4])

# Tag priority — most specific first
TAG_PRIORITY = [
    'walk','race','running','marathon','cycling','skating','wellness','fitness',
    'softball','baseball','tennis','soccer','kickball','pickleball','frisbee','bowling','model-yachting',
    'jazz','salsa','dance','theater','opera','film','art','music',
    'birds','garden','fishing','boating','nature','picnic','dogs',
    'wedding','ceremony','birthday','celebration','charity','fundraiser',
    'school-program','education','family',
    'holiday','spring','fall','annual-tradition',
    'chess','festival','parade','market','food','literature','talk','media','free',
    'closure','lawn','maintenance',
]

def get_image(category, location, tags=None):
    """Pick the most specific tag-based image, falling back to the category image."""
    if tags:
        for t in TAG_PRIORITY:
            if t in tags and t in HAVE_TAG_IMAGES:
                return f"{TAG_IMAGES_DIR}/{t}.png"
    if category in HAVE_CAT_IMAGES:
        return f"{CAT_IMAGES_DIR}/{category}.png"
    return '/assets/images/event-3.avif'


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

    all_places = match_places(location)
    if not all_places:
        skipped_unmatched += 1
        unmatched_locs.add(location)
        continue
    place = all_places[0]

    # NYRR enrichment: dedupe-merge landmarks discovered in the race detail
    # description/course text, and collect boroughs touched by the route.
    nyrr_rec = find_nyrr_record(name, start.year)
    nyrr_boroughs = []
    if nyrr_rec:
        extra_places, nyrr_boroughs = enrich_places_from_nyrr(nyrr_rec)
        existing_names = {p['name'] for p in all_places}
        for p in extra_places:
            if p['name'] not in existing_names:
                all_places.append(p)
                existing_names.add(p['name'])

    category = categorize(name, event_type)
    tags = get_tags(name, event_type, category)
    image = get_image(category, location, tags)
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
    if len(all_places) > 1:
        lines.append('places:')
        for p in all_places:
            lines.append('  - "' + yaml_safe(p['name']) + '"')
        lines.append('place_categories:')
        for p in all_places:
            lines.append('  - "' + p['category'] + '"')
    if nyrr_boroughs:
        lines.append('boroughs:')
        for b in nyrr_boroughs:
            lines.append('  - "' + b + '"')
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
    if nyrr_rec:
        lines.append('nyrr:')
        for fld in ('event_item_id', 'distance', 'hashtag',
                    'course_map', 'race_photo', 'race_logo',
                    'ical_url', 'strava_club', 'source_url'):
            val = nyrr_rec.get(fld)
            if val:
                lines.append('  ' + fld + ': "' + yaml_safe(str(val)) + '"')
        if nyrr_rec.get('total_finishers'):
            lines.append('  total_finishers: ' + str(nyrr_rec['total_finishers']))
        if nyrr_rec.get('sponsors'):
            lines.append('  sponsors:')
            for s in nyrr_rec['sponsors']:
                lines.append('    - "' + yaml_safe(s) + '"')
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
