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
CHARITY_WALKS_PATH = os.path.join(REPO_ROOT, '_data', 'charity-walks.yml')
NYCC_CACHE_PATH = os.path.join(REPO_ROOT, '_data', 'nycc-rides.json')
NYCPARKS_CACHE_PATH = os.path.join(REPO_ROOT, '_data', 'nycparks-events.json')
SUMMERSTAGE_CACHE_PATH = os.path.join(REPO_ROOT, '_data', 'summerstage-events.json')
NAUMBURG_CACHE_PATH = os.path.join(REPO_ROOT, '_data', 'naumburg-events.json')
PUBLICTHEATER_SEASONS_PATH = os.path.join(REPO_ROOT, '_data', 'publictheater-seasons.yml')
BIRDING_WALKS_PATH = os.path.join(REPO_ROOT, '_data', 'birding-walks.yml')

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

    # All-numeric titles (e.g. "500247") are permit/order numbers, not event names.
    # These almost always correspond to private bookings at scenic spots (Ladies'
    # Pavilion, Cherry Hill, Cop Cot, Wagner Cove) where the permittee left the
    # "event name" field blank and the system substituted a reference number.
    # Substitute a meaningful title and let categorize() route them to private-events.
    if re.fullmatch(r'\d+', title):
        return 'Private Booking'

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
                       'bar mitzvah', 'bat mitzvah', 'reception',
                       'private booking']
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
    # Cycling
    (r'\b(bike|biking|cycling|cyclist|bicycle)\b', 'cycling'),
    # Music / performance — specific subtypes emit BOTH the subtype and 'music'
    (r'\bjazz\b', 'jazz'),
    (r'\bjazz\b', 'music'),
    (r'\bsalsa\b', 'salsa'),
    (r'\bsalsa\b', 'music'),
    (r'\b(folk|folkdance|folkdancers)\b', 'folk'),
    (r'\b(folk|folkdance|folkdancers)\b', 'music'),
    (r'\b(hip[\s-]?hop|rap)\b', 'hip-hop'),
    (r'\b(hip[\s-]?hop|rap)\b', 'music'),
    (r'\bgospel\b', 'gospel'),
    (r'\bgospel\b', 'music'),
    (r'\bblues\b', 'blues'),
    (r'\bblues\b', 'music'),
    (r'\b(world\s*music|south\s*asian|afrobeat|afro[\s-]?cuban)\b', 'world-music'),
    (r'\b(world\s*music|afrobeat|afro[\s-]?cuban)\b', 'music'),
    (r'\b(latin\s*music|cumbia|merengue|bachata)\b', 'latin-music'),
    (r'\b(latin\s*music|cumbia|merengue|bachata)\b', 'music'),
    (r'\bdance\b', 'dance'),
    (r'\bballet\b', 'ballet'),
    (r'\bballet\b', 'dance'),
    (r'\b(concert|symphonic|symphony|orchestra|philharmonic|band|choir|dj|songwriter|musical|bluegrass|country)\b', 'music'),
    (r'\b(opera|operatic)\b', 'opera'),
    (r'\b(opera|operatic)\b', 'music'),
    # Theater — Shakespeare titles emit BOTH 'shakespeare' and 'theater'
    (r'\bshakespeare\b', 'shakespeare'),
    (r'\b(julius caesar|midsummer|macbeth|hamlet|romeo|king lear|othello|tempest|twelfth night|much ado)\b', 'shakespeare'),
    (r'\b(shakespeare|julius caesar|midsummer|macbeth|hamlet|romeo|king lear|othello|tempest|twelfth night|much ado)\b', 'theater'),
    (r'\b(theater|theatre|drama)\b', 'theater'),
    (r'\b(marionette|puppet)\b', 'puppet'),
    (r'\b(marionette|puppet)\b', 'theater'),
    (r'\b(comedy|stand[\s-]?up|improv)\b', 'comedy'),
    (r'\b(film|movie|cinema|screening)\b', 'film'),
    (r'\b(art|exhibit|gallery)\b', 'art'),
    (r'\bperformance\b', 'performance'),
    # Charity / fundraising
    (r'\b(charity|fundrais|gala|benefit|donation)\b', 'charity'),
    (r'\bgala\b', 'gala'),
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
    (r'\breception\b', 'reception'),
    (r'\bengagement\b', 'celebration'),
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
    (r'\byoga\b', 'yoga'),
    (r'\byoga\b', 'wellness'),
    (r'\b(meditat|mindful)\b', 'meditation'),
    (r'\b(meditat|mindful)\b', 'wellness'),
    (r'\bfitness\b', 'fitness'),
    (r'\b(zumba|aerobic|pilates)\b', 'fitness'),
    (r'\bstretch\b', 'wellness'),
    (r'\b(support\s*group|resilience|grief|recovery)\b', 'support-group'),
    # Holidays — emit specific holiday tag AND umbrella holiday tag
    (r'\bjuneteenth\b', 'juneteenth'),
    (r'\bhalloween\b', 'halloween'),
    (r'\bthanksgiving\b', 'thanksgiving'),
    (r'\beaster\b', 'easter'),
    (r'\b(earth\s*day)\b', 'earth-day'),
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
    # Cultural communities
    (r'\b(LGBTQ|pride|queer)\b', 'lgbtq'),
    (r'\b(south\s*asian|latino|latina|latine|latinx|aapi|asian\s*american|black\s*history|hispanic|caribbean|african|chinese|korean|japanese|indian)\b', 'cultural'),
    # Free
    (r'\bfree\b', 'free'),
    # Closures / maintenance
    (r'\b(lawn closure|meadow closure)\b', 'closure'),
    (r'\bmaintenance\b', 'maintenance'),
    # Gatherings
    (r'\b(meet[\s-]?up|meetup|social|mixer|hangout|gathering)\b', 'social'),
    (r'\bmeeting\b', 'meeting'),
    (r'\b(rally|demonstration|protest|march\s*for)\b', 'rally'),
    (r'\b(spiritual|prayer|unity|vigil|faith)\b', 'spiritual'),
    (r'\bcommemoration\b', 'commemoration'),
    # Other
    (r'\b(chess|checkers)\b', 'chess'),
    (r'\b(festival|fair)\b', 'festival'),
    (r'\bparade\b', 'parade'),
    (r'\b(speech|talk|lecture|seminar|forum|keynote)\b', 'talk'),
    (r'\bpanel\b', 'panel'),
    (r'\b(book|reading|poetry|writer|literary|author)\b', 'literature'),
    (r'\b(food\s*truck|culinary|cooking|tasting)\b', 'food'),
    (r'\b(market|farmers\s*market|farm\s*stand)\b', 'market'),
    (r'\b(media|press|interview)\b', 'media'),
    (r'\b(history|historic|heritage)\b', 'history'),
    (r'\b(adventure|exploration|expedition)\b', 'adventure'),
]

# Slug → Title Case display value. The site stores tags in this human-readable
# Title Case form (single metadata system, no separate `category` field).
TAG_DISPLAY = {
    'annual-tradition': 'Annual Tradition', 'baseball': 'Baseball', 'birds': 'Birds',
    'birthday': 'Birthday', 'bowling': 'Bowling', 'celebration': 'Celebration',
    'ceremony': 'Ceremony', 'chess': 'Chess', 'closures': 'Closures',
    'concerts-performances': 'Concerts & Performances', 'cultural': 'Cultural',
    'dance': 'Dance', 'earth-day': 'Earth Day', 'education': 'Education',
    'family': 'Family', 'family-community': 'Family & Community',
    'festival': 'Festival', 'film': 'Film', 'folk': 'Folk', 'free': 'Free',
    'fundraiser': 'Fundraiser', 'holiday': 'Holiday', 'jazz': 'Jazz',
    'juneteenth': 'Juneteenth', 'kickball': 'Kickball', 'maintenance': 'Maintenance',
    'media': 'Media', 'meeting': 'Meeting', 'memorial': 'Memorial',
    'model-yachting': 'Model Yachting', 'music': 'Music', 'panel': 'Panel',
    'performance': 'Performance', 'picnic': 'Picnic', 'private-booking': 'Private Booking',
    'private-events': 'Private Events', 'race': 'Race', 'rally': 'Rally',
    'reception': 'Reception', 'running': 'Running', 'runs-races': 'Runs & Races',
    'salsa': 'Salsa', 'school-program': 'School Program', 'shakespeare': 'Shakespeare',
    'skating': 'Skating', 'soccer': 'Soccer', 'social': 'Social', 'softball': 'Softball',
    'spiritual': 'Spiritual', 'sports': 'Sports', 'support-group': 'Support Group',
    't-ball': 'T-Ball', 'talk': 'Talk', 'tennis': 'Tennis', 'theater': 'Theater',
    'walk': 'Walk', 'wedding': 'Wedding', 'wellness': 'Wellness',
    'world-music': 'World Music', 'yoga': 'Yoga', 'youth': 'Youth',
    'hike': 'Hike', 'marathon': 'Marathon', 'cycling': 'Cycling',
    'pickleball': 'Pickleball', 'volleyball': 'Volleyball', 'basketball': 'Basketball',
    'lacrosse': 'Lacrosse', 'rugby': 'Rugby', 'football': 'Football', 'cricket': 'Cricket',
    'frisbee': 'Frisbee', 'hip-hop': 'Hip-Hop', 'gospel': 'Gospel', 'blues': 'Blues',
    'latin-music': 'Latin Music', 'ballet': 'Ballet', 'opera': 'Opera',
    'puppet': 'Puppet', 'comedy': 'Comedy', 'art': 'Art', 'charity': 'Charity',
    'gala': 'Gala', 'meditation': 'Meditation', 'fitness': 'Fitness',
    'nature': 'Nature', 'garden': 'Garden', 'fishing': 'Fishing', 'boating': 'Boating',
    'dogs': 'Dogs', 'halloween': 'Halloween', 'thanksgiving': 'Thanksgiving',
    'easter': 'Easter', 'spring': 'Spring', 'fall': 'Fall', 'lgbtq': 'LGBTQ',
    'literature': 'Literature', 'food': 'Food', 'market': 'Market', 'parade': 'Parade',
    'commemoration': 'Commemoration', 'history': 'History', 'adventure': 'Adventure',
    'community': 'Community',
    # Source 5/6 additions:
    'affects-loop': 'Affects Loop',     # event impinges on the runner/cyclist loop
    'group-ride': 'Group Ride',         # NYCC and similar club rides
    'nycc': 'NYCC',                     # source tag for New York Cycle Club
    'sig': 'SIG',                       # NYCC Special Interest Group training rides
    'sts': 'STS',                       # NYCC Saturday Training Series
}


# Event-name patterns for events that historically occupy the runner/cyclist loop.
# Hits add both `race` (so runner/cyclist tag-includes catch them) and `affects-loop`
# (the brand hard-include rule). These are events the permit feed lists with vague
# tags like "Family & Community" but that materially close drives — the AIDS-Walk-gap
# pattern. Keep this list small and specific; broad patterns over-tag.
LOOP_IMPACT_NAME_PATTERNS = [
    r'\bcorporate\s+challenge\b',                  # J.P. Morgan Corporate Challenge — Wed evening 3.5mi loop race
    r'\baids\s+walk\b',                            # AIDS Walk NY — also in charity-walks.yml; defense in depth
    r'\bachilles\s+hope\s+and\s+possibility\b',    # NYRR Achilles Hope & Possibility
    r'\bnyc\s+marathon\b',
    r"\bnyc\s+half\b",
    r"\bwomen'?s\s+half\b",
    r'\bmini\s+10k\b',
    r'\bmidnight\s+run\b',
    r'\bjoe\s+kleinerman\b',                       # NYRR Joe Kleinerman 10K (typical CP loop race)
    r'\bted\s+corbitt\b',                          # NYRR Ted Corbitt 15K
    r'\bmanhattan\s+10k\b',
    r'\bhealthy\s+kidney\b',                       # NYRR Healthy Kidney 10K
]


def detects_loop_impact(name):
    """Return True if the event name matches a known loop-occupying event pattern.
    Used to override the affects-loop tag when the permit feed under-tags."""
    text = (name or '').lower()
    return any(re.search(p, text, re.IGNORECASE) for p in LOOP_IMPACT_NAME_PATTERNS)


def get_tags(name, event_type, category=None):
    """Return a sorted list of Title Case tag values.

    `category` is an internal slug (still used for category-based tag emission
    and for the closure/maintenance/education roll-up rules); it is not written
    to the event file as a separate field — it's folded into tags.
    """
    text = (name + ' ' + (event_type or '')).lower()
    slugs = set()
    for pattern, tag in TAG_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            slugs.add(tag)
    # Known loop-occupying events the permit feed under-tags (Corporate Challenge etc.)
    if detects_loop_impact(name):
        slugs.add('affects-loop')
        slugs.add('race')
    # Sport-type roll-up
    if event_type in ('Sport - Adult', 'Sport - Youth'):
        slugs.add('sports')
        if event_type == 'Sport - Youth':
            slugs.add('youth')
    if slugs & {'softball','baseball','t-ball','soccer','tennis','kickball','pickleball','basketball','volleyball','lacrosse','rugby','football','cricket'}:
        slugs.add('sports')
    # Category-based tags
    if category == 'private-events':
        slugs.add('private-booking')
    if category == 'closures':
        slugs.add('closures')
    if category == 'maintenance':
        slugs.add('maintenance')
    if category == 'education':
        slugs.add('education')
    # Always include the category itself as a tag (single-dimension filtering)
    if category:
        slugs.add(category)
    # Consolidate singular `closure` into plural `closures`
    if 'closure' in slugs:
        slugs.discard('closure')
        slugs.add('closures')
    # Fallback
    if not slugs:
        slugs.add('community')
    return sorted({TAG_DISPLAY.get(s, s.replace('-', ' ').title()) for s in slugs})


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
    'walk','race','running','marathon','cycling','skating','yoga','meditation','wellness','fitness',
    'softball','baseball','tennis','soccer','kickball','pickleball','frisbee','bowling','model-yachting',
    'jazz','salsa','folk','hip-hop','gospel','blues','world-music','latin-music',
    'shakespeare','puppet','comedy','ballet','dance','theater','opera','film','art','music',
    'birds','garden','fishing','boating','nature','picnic','dogs',
    'wedding','ceremony','memorial','reception','birthday','celebration','gala','charity','fundraiser',
    'school-program','education','family',
    'juneteenth','halloween','thanksgiving','easter','earth-day','holiday','spring','fall','annual-tradition',
    'cultural','lgbtq','support-group','spiritual',
    'chess','festival','parade','market','food','literature','talk','panel','meeting','social','rally','media','free',
    'commemoration','history','adventure',
    'closure','lawn','maintenance',
]

def get_image(category, location, tags=None):
    """Pick the most specific tag-based image, falling back to the category image.

    `tags` are Title Case display values (e.g., "Runs & Races"). Image asset
    filenames stay kebab-case (`runs-races.png`), so we slugify each tag back
    to its asset filename before matching.
    """
    if tags:
        tag_slugs = {slugify(t) for t in tags}
        for slug in TAG_PRIORITY:
            if slug in tag_slugs and slug in HAVE_TAG_IMAGES:
                return f"{TAG_IMAGES_DIR}/{slug}.png"
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

TODAY = datetime.now().strftime('%Y-%m-%d')

# Remove past event files left over from previous runs
_purged_past = 0
for (eid, date), files in list(existing_by_key.items()):
    if date and date < TODAY:
        for info in files:
            os.remove(info['path'])
            _purged_past += 1
        del existing_by_key[(eid, date)]
if _purged_past:
    print(f"Purged {_purged_past} past event files (date < {TODAY})")


# ── Process latest events from API ────────────────────────────────────
with open(LATEST_JSON) as f:
    latest = json.load(f)

print(f"Loaded {len(latest)} latest events from API")

slug_counts = defaultdict(int)
created = 0
updated = 0
skipped_unmatched = 0
skipped_invalid = 0
skipped_past = 0
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
    if date_str < TODAY:
        skipped_past += 1
        continue
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
    lines.append('image: "' + image + '"')
    lines.append('description: "' + yaml_safe(description) + '"')
    lines.append('event_id: "' + eid + '"')
    lines.append('event_type: "' + event_type + '"')
    lines.append('event_borough: "Manhattan"')
    lines.append('community_board: "' + cb + '"')
    lines.append('police_precinct: "' + pp + '"')
    if 'Affects Loop' in tags:
        lines.append('affects_loop: true')
    lines.append('tags:')
    for tag in tags:
        lines.append('  - "' + yaml_safe(tag) + '"')
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

# ── Source 6: Curated charity walks (charity-walks.yml) ───────────────
charity_created = 0
charity_updated = 0
charity_skipped_no_date = 0
charity_skipped_unmatched = 0
current_year = datetime.now().year
if os.path.exists(CHARITY_WALKS_PATH):
    with open(CHARITY_WALKS_PATH) as f:
        cw_data = yaml.safe_load(f) or {}
    walks = cw_data.get('walks') or []
    for entry in walks:
        wid = entry.get('id')
        if not wid:
            continue
        date_str = (entry.get('dates') or {}).get(str(current_year))
        if not date_str:
            charity_skipped_no_date += 1
            continue
        if date_str < TODAY:
            continue
        eid = f'charity-{wid}-{date_str}'
        api_event_ids.add(eid)
        name = entry.get('title') or wid
        location = entry.get('location') or ''
        all_places = match_places(location)
        if not all_places:
            charity_skipped_unmatched += 1
            unmatched_locs.add(location)
            continue
        place = all_places[0]
        time_str = entry.get('start_time') or '09:00'
        end_time_str = entry.get('end_time') or '12:00'
        event_type = entry.get('event_type') or 'Charity Walk'
        event_borough = entry.get('event_borough') or 'Manhattan'
        source_url = entry.get('source_url') or ''
        description = (entry.get('description') or '').strip().replace('\n', ' ')
        description = re.sub(r'\s+', ' ', description)
        if not description:
            description = make_description(name, event_type, location)

        # Build tag set: get_tags() handles 'walk'/'run' patterns from the title.
        # Then merge in author-supplied tags and the affects-loop flag.
        cat = 'runs-races'
        tag_slugs = set()
        for t in get_tags(name, event_type, cat):
            # get_tags returns Title Case; convert back to slug for dedupe
            tag_slugs.add(slugify(t))
        for t in (entry.get('tags') or []):
            tag_slugs.add(t)
        if entry.get('affects_loop'):
            tag_slugs.add('affects-loop')
        tag_list = sorted({
            TAG_DISPLAY.get(s, s.replace('-', ' ').title())
            for s in tag_slugs
        })
        image = get_image(cat, location, tag_list)

        key = (eid, date_str)
        api_keys.add(key)
        is_new = key not in existing_by_key

        date_dt = datetime.strptime(date_str, '%Y-%m-%d')
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
        lines.append('image: "' + image + '"')
        lines.append('description: "' + yaml_safe(description) + '"')
        lines.append('event_id: "' + eid + '"')
        lines.append('event_type: "' + event_type + '"')
        lines.append('event_borough: "' + event_borough + '"')
        lines.append('source: "charity-walks.yml"')
        if source_url:
            lines.append('source_url: "' + yaml_safe(source_url) + '"')
        if entry.get('organizer'):
            lines.append('organizer: "' + yaml_safe(entry['organizer']) + '"')
        if entry.get('expected_attendance'):
            lines.append('expected_attendance: ' + str(entry['expected_attendance']))
        if entry.get('affects_loop'):
            lines.append('affects_loop: true')
        lines.append('tags:')
        for tag in tag_list:
            lines.append('  - "' + yaml_safe(tag) + '"')
        lines.append('---')
        lines.append('')
        lines.append(description)
        lines.append('')
        lines.append('## Event Details')
        lines.append('')
        lines.append('- **Event:** ' + name)
        lines.append('- **Date:** ' + date_dt.strftime('%A, %B %-d, %Y'))
        if entry.get('opening_ceremony_time'):
            lines.append('- **Opening Ceremony:** ' + entry['opening_ceremony_time'])
        lines.append('- **Time:** ' + time_str + ' – ' + end_time_str)
        lines.append('- **Location:** ' + location + ', Central Park')
        if entry.get('organizer'):
            lines.append('- **Organizer:** ' + entry['organizer'])
        if source_url:
            lines.append('- **Official site:** ' + source_url)
        lines.append('')
        if entry.get('route_impact'):
            ri = re.sub(r'\s+', ' ', entry['route_impact'].strip())
            lines.append('## Route Impact')
            lines.append('')
            lines.append(ri)
            lines.append('')

        new_content = '\n'.join(lines)

        if is_new:
            base_slug = slugify(name) + '-' + date_str
            slug_counts[base_slug] += 1
            slug = base_slug if slug_counts[base_slug] == 1 else base_slug + '-' + str(slug_counts[base_slug])
            filepath = os.path.join(EVENTS_DIR, slug + '.md')
            with open(filepath, 'w') as f:
                f.write(new_content)
            charity_created += 1
        else:
            existing_files = existing_by_key[key]
            keeper = existing_files[0]
            if keeper['content'] != new_content:
                with open(keeper['path'], 'w') as f:
                    f.write(new_content)
                charity_updated += 1
            for dup in existing_files[1:]:
                try:
                    os.remove(dup['path'])
                except FileNotFoundError:
                    pass


# ── Source 5: NYCC group rides (nycc-rides.json cache) ────────────────
# Read-only consumer of the cache produced by a separate fetch step.
# If the cache is absent, log and continue — the fetch lives behind Cloudflare
# and may not have a fresh snapshot every run.
nycc_created = 0
nycc_updated = 0
nycc_skipped_unmatched = 0
nycc_cache_present = os.path.exists(NYCC_CACHE_PATH)
if nycc_cache_present:
    with open(NYCC_CACHE_PATH) as f:
        nycc_data = json.load(f) or {}
    rides = nycc_data.get('rides') or []
    for rec in rides:
        date_str = rec.get('date')
        if not date_str or date_str < TODAY:
            continue
        name = rec.get('title') or 'NYCC Group Ride'
        leader = rec.get('leader') or ''
        eid = f"nycc-{date_str}-{slugify(name)}-{slugify(leader)}"
        api_event_ids.add(eid)
        location = rec.get('location') or ''
        all_places = match_places(location)
        if not all_places:
            nycc_skipped_unmatched += 1
            unmatched_locs.add(location)
            continue
        place = all_places[0]
        time_str = rec.get('time') or '08:00'
        end_time_str = rec.get('end_time') or ''  # NYCC rarely publishes
        pace = rec.get('pace') or ''
        mph = rec.get('mph')
        distance = rec.get('distance') or ''
        source_url = rec.get('source_url') or 'https://nycc.org/upcoming-rides'
        description = rec.get('description') or (
            f"NYCC {pace} group ride led by {leader}. {distance}, departing from {location}." if leader
            else f"NYCC {pace} group ride. {distance}, departing from {location}."
        )
        description = re.sub(r'\s+', ' ', description).strip()

        # Tag set: every NYCC ride gets nycc/cycling/group-ride. SIG/STS based
        # on pace string. Affects-loop on 5–9 AM start times.
        tag_slugs = {'nycc', 'cycling', 'group-ride'}
        if pace.upper().startswith('SIG'):
            tag_slugs.add('sig')
        if pace.upper().startswith('STS'):
            tag_slugs.add('sts')
        try:
            hh = int(time_str.split(':')[0])
            if 5 <= hh <= 8:
                tag_slugs.add('affects-loop')
        except Exception:
            pass
        tag_list = sorted({
            TAG_DISPLAY.get(s, s.replace('-', ' ').title())
            for s in tag_slugs
        })
        cat = 'runs-races'  # closest existing category; "Group Ride" event_type carries the distinction
        image = get_image(cat, location, tag_list)
        event_type = 'Group Ride'

        key = (eid, date_str)
        api_keys.add(key)
        is_new = key not in existing_by_key

        date_dt = datetime.strptime(date_str, '%Y-%m-%d')
        lines = []
        lines.append('---')
        lines.append('title: "' + yaml_safe(name) + '"')
        lines.append('date: ' + date_str)
        lines.append('time: "' + time_str + '"')
        if end_time_str:
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
        lines.append('image: "' + image + '"')
        lines.append('description: "' + yaml_safe(description) + '"')
        lines.append('event_id: "' + eid + '"')
        lines.append('event_type: "' + event_type + '"')
        lines.append('event_borough: "Manhattan"')
        lines.append('source: "nycc.org"')
        lines.append('source_url: "' + yaml_safe(source_url) + '"')
        if leader:
            lines.append('leader: "' + yaml_safe(leader) + '"')
        if pace:
            lines.append('pace: "' + yaml_safe(pace) + '"')
        if mph:
            lines.append('mph: ' + str(mph))
        if distance:
            lines.append('distance: "' + yaml_safe(distance) + '"')
        if 'affects-loop' in tag_slugs:
            lines.append('affects_loop: true')
        lines.append('tags:')
        for tag in tag_list:
            lines.append('  - "' + yaml_safe(tag) + '"')
        lines.append('---')
        lines.append('')
        lines.append(description)
        lines.append('')
        lines.append('## Ride Details')
        lines.append('')
        lines.append('- **Date:** ' + date_dt.strftime('%A, %B %-d, %Y'))
        lines.append('- **Start time:** ' + time_str)
        lines.append('- **Meet-up:** ' + location + ', Central Park')
        if leader:
            lines.append('- **Leader:** ' + leader)
        if pace:
            lines.append('- **Pace:** ' + pace)
        if distance:
            lines.append('- **Distance:** ' + distance)
        lines.append('')

        new_content = '\n'.join(lines)

        if is_new:
            base_slug = slugify(name) + '-' + date_str
            slug_counts[base_slug] += 1
            slug = base_slug if slug_counts[base_slug] == 1 else base_slug + '-' + str(slug_counts[base_slug])
            filepath = os.path.join(EVENTS_DIR, slug + '.md')
            with open(filepath, 'w') as f:
                f.write(new_content)
            nycc_created += 1
        else:
            existing_files = existing_by_key[key]
            keeper = existing_files[0]
            if keeper['content'] != new_content:
                with open(keeper['path'], 'w') as f:
                    f.write(new_content)
                nycc_updated += 1
            for dup in existing_files[1:]:
                try:
                    os.remove(dup['path'])
                except FileNotFoundError:
                    pass


# ── Helper for the new (NYC Parks / SummerStage / Naumburg) sources ───
def _write_event_md(eid, name, date_str, time_str, end_time_str, location,
                    description, event_type, source, source_url, image,
                    extra_fm=None, tag_slugs=None, body_extra=None):
    """Render a Markdown event file using the existing places-vocabulary +
    tagging conventions. Returns ('created'|'updated'|'unchanged', filepath).
    `extra_fm` is an ordered list of (key, value) tuples appended to the
    front matter. `tag_slugs` is a set of slug-form tags; falls back to
    get_tags() if None. `body_extra` is a list of extra markdown lines
    appended after the standard body."""
    if date_str < TODAY:
        return ('past', None)
    api_event_ids.add(eid)
    all_places = match_places(location)
    if not all_places:
        unmatched_locs.add(location)
        return ('unmatched', None)
    place = all_places[0]
    cat = categorize(name, event_type)
    if tag_slugs is None:
        tag_slugs = set()
        for t in get_tags(name, event_type, cat):
            tag_slugs.add(slugify(t))
    tag_list = sorted({
        TAG_DISPLAY.get(s, s.replace('-', ' ').title())
        for s in tag_slugs
    })
    if not image:
        image = get_image(cat, location, tag_list)
    if not description:
        description = make_description(name, event_type, location)
    description = re.sub(r'\s+', ' ', description).strip()

    key = (eid, date_str)
    api_keys.add(key)
    is_new = key not in existing_by_key
    date_dt = datetime.strptime(date_str, '%Y-%m-%d')

    lines = ['---', f'title: "{yaml_safe(name)}"', f'date: {date_str}',
             f'time: "{time_str}"']
    if end_time_str:
        lines.append(f'end_time: "{end_time_str}"')
    lines.append(f'location: "{yaml_safe(location)}"')
    lines.append(f'place: "{yaml_safe(place["name"])}"')
    lines.append(f'place_category: "{place["category"]}"')
    if len(all_places) > 1:
        lines.append('places:')
        for p in all_places:
            lines.append(f'  - "{yaml_safe(p["name"])}"')
        lines.append('place_categories:')
        for p in all_places:
            lines.append(f'  - "{p["category"]}"')
    lines.append(f'image: "{image}"')
    lines.append(f'description: "{yaml_safe(description)}"')
    lines.append(f'event_id: "{eid}"')
    lines.append(f'event_type: "{event_type}"')
    lines.append('event_borough: "Manhattan"')
    lines.append(f'source: "{source}"')
    if source_url:
        lines.append(f'source_url: "{yaml_safe(source_url)}"')
    for k, v in (extra_fm or []):
        if v is None or v == '':
            continue
        if isinstance(v, bool):
            lines.append(f'{k}: {"true" if v else "false"}')
        elif isinstance(v, (int, float)):
            lines.append(f'{k}: {v}')
        else:
            lines.append(f'{k}: "{yaml_safe(str(v))}"')
    lines.append('tags:')
    for tag in tag_list:
        lines.append(f'  - "{yaml_safe(tag)}"')
    lines.append('---')
    lines.append('')
    lines.append(description)
    lines.append('')
    lines.append('## Event Details')
    lines.append('')
    lines.append(f'- **Event:** {name}')
    lines.append(f'- **Date:** {date_dt.strftime("%A, %B %-d, %Y")}')
    lines.append(f'- **Time:** {time_str}' + (f' – {end_time_str}' if end_time_str else ''))
    lines.append(f'- **Location:** {location}, Central Park')
    if source_url:
        lines.append(f'- **Official site:** {source_url}')
    if body_extra:
        lines.append('')
        lines.extend(body_extra)
    lines.append('')

    new_content = '\n'.join(lines)
    if is_new:
        base_slug = slugify(name) + '-' + date_str
        slug_counts[base_slug] += 1
        slug = base_slug if slug_counts[base_slug] == 1 else f'{base_slug}-{slug_counts[base_slug]}'
        filepath = os.path.join(EVENTS_DIR, slug + '.md')
        with open(filepath, 'w') as f:
            f.write(new_content)
        return ('created', filepath)
    existing_files = existing_by_key[key]
    keeper = existing_files[0]
    status = 'unchanged'
    if keeper['content'] != new_content:
        with open(keeper['path'], 'w') as f:
            f.write(new_content)
        status = 'updated'
    for dup in existing_files[1:]:
        try:
            os.remove(dup['path'])
        except FileNotFoundError:
            pass
    return (status, keeper['path'])


# ── Source 7: NYC Parks Department (nycparks-events.json) ─────────────
nycparks_created = nycparks_updated = nycparks_skipped = 0
if os.path.exists(NYCPARKS_CACHE_PATH):
    with open(NYCPARKS_CACHE_PATH) as f:
        nycparks_data = json.load(f)
    for rec in nycparks_data.get('events', []):
        start_iso = rec.get('start_date') or ''
        end_iso = rec.get('end_date') or ''
        if 'T' not in start_iso:
            nycparks_skipped += 1
            continue
        date_str, time_part = start_iso.split('T', 1)
        time_str = time_part[:5]
        end_time_str = end_iso.split('T', 1)[1][:5] if 'T' in end_iso else ''
        category = rec.get('category', '') or ''
        free = rec.get('free')
        tag_slugs = set()
        if free:
            tag_slugs.add('free')
        # Light category → tag mapping
        for piece in [s.strip().lower() for s in category.split(',') if s.strip()]:
            if piece in ('art', 'concerts', 'concert', 'music', 'film', 'theater',
                         'volunteer', 'nature', 'fitness', 'family', 'history',
                         'science', 'birds'):
                tag_slugs.add(piece if piece != 'concert' else 'music')
        # Always carry the NYC Parks origin tag
        tag_slugs.add('nyc-parks')
        result, _ = _write_event_md(
            eid=rec['id'],
            name=rec['title'],
            date_str=date_str,
            time_str=time_str,
            end_time_str=end_time_str,
            location=rec.get('location') or 'Central Park',
            description=f"{rec['title']} at {rec.get('location','Central Park')}. NYC Parks Department event{(' — '+category) if category else ''}.",
            event_type='NYC Parks Event',
            source='nycgovparks.org',
            source_url=rec.get('url'),
            image=None,
            tag_slugs=tag_slugs,
        )
        if result == 'created': nycparks_created += 1
        elif result == 'updated': nycparks_updated += 1
        elif result == 'unmatched': nycparks_skipped += 1


# ── Source 8: SummerStage (summerstage-events.json) ───────────────────
summerstage_created = summerstage_updated = summerstage_skipped = 0
if os.path.exists(SUMMERSTAGE_CACHE_PATH):
    with open(SUMMERSTAGE_CACHE_PATH) as f:
        ss_data = json.load(f)
    for rec in ss_data.get('events', []):
        start = (rec.get('start_date') or '').replace('T', ' ')
        if ' ' not in start:
            summerstage_skipped += 1
            continue
        date_str, time_part = start.split(' ', 1)
        time_str = time_part[:5]
        end_time_str = ''
        if rec.get('end_date'):
            end_part = rec['end_date'].replace('T', ' ').split(' ', 1)
            if len(end_part) == 2:
                end_time_str = end_part[1][:5]
        tag_slugs = set(rec.get('tags') or [])
        tag_slugs.add('summerstage')
        tag_slugs.add('music')
        tag_slugs.add('concerts-performances')
        if rec.get('cost') == '' or 'free' in (rec.get('cost') or '').lower():
            tag_slugs.add('free')
        location = rec.get('place_hint') or 'Rumsey Playfield'
        result, _ = _write_event_md(
            eid=rec['id'],
            name=rec['title'],
            date_str=date_str,
            time_str=time_str,
            end_time_str=end_time_str,
            location=location,
            description=(rec.get('description') or '')[:500],
            event_type='SummerStage Concert',
            source='cityparksfoundation.org',
            source_url=rec.get('url'),
            image=rec.get('image'),
            tag_slugs=tag_slugs,
            extra_fm=[('cost', rec.get('cost', ''))] if rec.get('cost') else None,
        )
        if result == 'created': summerstage_created += 1
        elif result == 'updated': summerstage_updated += 1
        elif result == 'unmatched': summerstage_skipped += 1


# ── Source 9: Naumburg Orchestral Concerts (naumburg-events.json) ─────
naumburg_created = naumburg_updated = naumburg_skipped = 0
if os.path.exists(NAUMBURG_CACHE_PATH):
    with open(NAUMBURG_CACHE_PATH) as f:
        nb_data = json.load(f)
    for rec in nb_data.get('events', []):
        date_str = rec.get('date')
        if not date_str:
            naumburg_skipped += 1
            continue
        # Parse "7:30 PM" -> "19:30"
        time_display = (rec.get('time_display') or '').strip()
        time_str = '19:30'  # historical default
        end_time_str = '21:00'
        if time_display:
            try:
                t = datetime.strptime(time_display.replace(' ', ' ').strip(), '%I:%M %p')
                time_str = t.strftime('%H:%M')
                end_time_str = (t.replace(hour=(t.hour+2) % 24)).strftime('%H:%M')
            except Exception:
                pass
        tag_slugs = {'music', 'concerts-performances', 'free', 'annual-tradition',
                     'classical', 'orchestra', 'naumburg'}
        result, _ = _write_event_md(
            eid=rec['id'],
            name=rec['title'],
            date_str=date_str,
            time_str=time_str,
            end_time_str=end_time_str,
            location='Naumburg Bandshell',
            description=f"{rec['title']} — free Naumburg Orchestral Concert at the Naumburg Bandshell. Part of the annual summer series (since 1905).",
            event_type='Naumburg Concert',
            source='naumburgconcerts.org',
            source_url=rec.get('url'),
            image=rec.get('image'),
            tag_slugs=tag_slugs,
        )
        if result == 'created': naumburg_created += 1
        elif result == 'updated': naumburg_updated += 1
        elif result == 'unmatched': naumburg_skipped += 1


# ── Source 10: Public Theater seasons (publictheater-seasons.yml) ─────
# Expand each season into one event per performance date, skipping dark days.
publictheater_created = publictheater_updated = publictheater_skipped = 0
publictheater_seasons_loaded = 0
DARK_WEEKDAYS = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                 'friday': 4, 'saturday': 5, 'sunday': 6}
if os.path.exists(PUBLICTHEATER_SEASONS_PATH):
    with open(PUBLICTHEATER_SEASONS_PATH) as f:
        pt_data = yaml.safe_load(f) or {}
    from datetime import timedelta
    for season in (pt_data.get('seasons') or []):
        publictheater_seasons_loaded += 1
        first = season.get('first_preview')
        last = season.get('closing_night')
        if not first or not last:
            continue
        if isinstance(first, str): first = datetime.strptime(first, '%Y-%m-%d').date()
        if isinstance(last, str): last = datetime.strptime(last, '%Y-%m-%d').date()
        dark = {DARK_WEEKDAYS[d.lower()] for d in (season.get('dark_days') or [])}
        production = season.get('production') or 'Shakespeare in the Park'
        author = season.get('author') or 'William Shakespeare'
        director = season.get('director') or ''
        curtain = season.get('curtain') or '20:00'
        tag_slugs = {'shakespeare', 'theater', 'free', 'annual-tradition',
                     'concerts-performances'}
        for t in (season.get('tags') or []):
            tag_slugs.add(slugify(t) if not t[0].islower() else t)
        d = first
        while d <= last:
            if d.weekday() in dark:
                d += timedelta(days=1)
                continue
            date_str = d.strftime('%Y-%m-%d')
            eid = f"publictheater-{slugify(production)}-{date_str}"
            desc = (f"{production} by {author}" + (f", directed by {director}" if director else "") +
                    f", at the Delacorte Theater. Free Public Theater production; "
                    f"tickets via TodayTix lottery and the day-of standby line.")
            result, _ = _write_event_md(
                eid=eid,
                name=production,
                date_str=date_str,
                time_str=curtain,
                end_time_str='',
                location='Delacorte Theater',
                description=desc,
                event_type='Theater Production',
                source='publictheater.org',
                source_url=season.get('url'),
                image=None,
                tag_slugs=tag_slugs,
            )
            if result == 'created': publictheater_created += 1
            elif result == 'updated': publictheater_updated += 1
            elif result == 'unmatched': publictheater_skipped += 1
            d += timedelta(days=1)


# ── Source 11: NYC Bird Alliance recurring walks (birding-walks.yml) ──
# Each entry expands by weekday + cadence between season_start and season_end.
birding_created = birding_updated = birding_skipped = 0
birding_walks_loaded = 0
if os.path.exists(BIRDING_WALKS_PATH):
    with open(BIRDING_WALKS_PATH) as f:
        bw_data = yaml.safe_load(f) or {}
    from datetime import timedelta
    for walk in (bw_data.get('walks') or []):
        birding_walks_loaded += 1
        start = walk.get('season_start')
        end = walk.get('season_end')
        if not start or not end:
            continue
        if isinstance(start, str): start = datetime.strptime(start, '%Y-%m-%d').date()
        if isinstance(end, str): end = datetime.strptime(end, '%Y-%m-%d').date()
        weekday = walk.get('weekday')
        cadence = (walk.get('cadence') or 'weekly').lower()
        name = walk.get('name') or 'Bird Walk'
        leader = walk.get('leader') or 'NYC Bird Alliance staff'
        location = walk.get('place') or 'The Ramble'
        meet = walk.get('meet_location') or location
        time_str = walk.get('time') or '08:00'
        end_time_str = walk.get('end_time') or ''
        cost = walk.get('cost') or ''
        tag_slugs = {'birds', 'nature', 'nyc-bird-alliance'}
        if 'free' in (cost or '').lower():
            tag_slugs.add('free')
        for t in (walk.get('tags') or []):
            tag_slugs.add(slugify(t) if not t[0].islower() else t)
        # Iterate dates
        step = 7 if cadence == 'weekly' else (14 if cadence == 'biweekly' else None)
        d = start
        # advance to the next matching weekday
        if weekday is not None:
            while d <= end and d.weekday() != int(weekday):
                d += timedelta(days=1)
        while d <= end:
            date_str = d.strftime('%Y-%m-%d')
            eid = f"birding-{slugify(name)}-{date_str}"
            desc = (f"{name} led by {leader}. Meet at {meet}. "
                    f"Hosted by NYC Bird Alliance.")
            result, _ = _write_event_md(
                eid=eid,
                name=name,
                date_str=date_str,
                time_str=time_str,
                end_time_str=end_time_str,
                location=location,
                description=desc,
                event_type='Bird Walk',
                source='nycbirdalliance.org',
                source_url=walk.get('url'),
                image=None,
                tag_slugs=tag_slugs,
                extra_fm=[('leader', leader), ('cost', cost)],
            )
            if result == 'created': birding_created += 1
            elif result == 'updated': birding_updated += 1
            elif result == 'unmatched': birding_skipped += 1
            if cadence == 'monthly':
                # advance ~30 days then snap to weekday
                d += timedelta(days=28)
                while d.weekday() != int(weekday) and d <= end:
                    d += timedelta(days=1)
            elif step:
                d += timedelta(days=step)
            else:
                break


# Clean titles + backfill missing descriptions in events left alone
# (file not matched by an API record).
title_only_cleaned = 0
description_backfilled = 0
left_alone_count = 0
for key, files in existing_by_key.items():
    if key in api_keys:
        continue
    left_alone_count += len(files)
    for info in files:
        content = info['content']
        changed = False

        title_match = re.search(r'^title:\s*"(.+?)"', content, re.MULTILINE)
        if title_match:
            raw_title = title_match.group(1).replace('\\"', '"')
            cleaned = clean_title(raw_title)
            if cleaned != raw_title:
                content = re.sub(
                    r'^title:\s*".*?"',
                    'title: "' + yaml_safe(cleaned) + '"',
                    content,
                    count=1,
                    flags=re.MULTILINE,
                )
                title_only_cleaned += 1
                changed = True
        else:
            cleaned = None

        # Backfill description if absent or empty.
        # Source priority: existing front matter location/title/event_type.
        desc_match = re.search(r'^description:\s*"(.*?)"\s*$', content, re.MULTILINE)
        if not desc_match or not desc_match.group(1).strip():
            current_title = (cleaned
                             or (title_match.group(1).replace('\\"', '"') if title_match else 'Event'))
            loc_match = re.search(r'^location:\s*"(.*?)"', content, re.MULTILINE)
            et_match = re.search(r'^event_type:\s*"(.*?)"', content, re.MULTILINE)
            location_str = loc_match.group(1) if loc_match else 'Central Park'
            event_type_str = et_match.group(1) if et_match else ''
            new_desc = make_description(current_title, event_type_str, location_str)
            new_desc_line = 'description: "' + yaml_safe(new_desc) + '"'
            if desc_match:
                content = re.sub(
                    r'^description:\s*".*?"\s*$',
                    new_desc_line,
                    content,
                    count=1,
                    flags=re.MULTILINE,
                )
            else:
                # Insert after location (or before category) inside front matter.
                if loc_match:
                    insert_at = content.find('\n', loc_match.end()) + 1
                    content = content[:insert_at] + new_desc_line + '\n' + content[insert_at:]
                else:
                    # Last resort: insert just before the closing `---`
                    content = re.sub(
                        r'(\n---\s*\n)',
                        '\n' + new_desc_line + r'\1',
                        content,
                        count=1,
                    )
            description_backfilled += 1
            changed = True

        if changed:
            with open(info['path'], 'w') as f:
                f.write(content)

print(f"\nMerge results:")
print(f"  Created (new events): {created}")
print(f"  Updated (existing events refreshed): {updated}")
print(f"  Total API events processed: {len(latest)}")
print(f"  Files not in API: {title_only_cleaned} titles cleaned, {description_backfilled} descriptions backfilled, {left_alone_count} files visited")
print(f"  Skipped (location unmatched): {skipped_unmatched}")
print(f"  Skipped (invalid data): {skipped_invalid}")
print(f"  Skipped (past date): {skipped_past}")
print(f"\nCharity walks (charity-walks.yml):")
print(f"  Created: {charity_created}, Updated: {charity_updated}")
print(f"  Skipped (no date for {current_year}): {charity_skipped_no_date}")
print(f"  Skipped (location unmatched): {charity_skipped_unmatched}")
print(f"\nNYCC group rides (nycc-rides.json):")
if not nycc_cache_present:
    print(f"  Cache missing at {NYCC_CACHE_PATH} — run the fetch step before merging.")
else:
    print(f"  Created: {nycc_created}, Updated: {nycc_updated}")
    print(f"  Skipped (location unmatched): {nycc_skipped_unmatched}")

print(f"\nNYC Parks Dept (nycparks-events.json):")
if os.path.exists(NYCPARKS_CACHE_PATH):
    print(f"  Created: {nycparks_created}, Updated: {nycparks_updated}, Skipped: {nycparks_skipped}")
else:
    print(f"  Cache missing — run fetch_nycparks_events.py before merging.")

print(f"\nSummerStage (summerstage-events.json):")
if os.path.exists(SUMMERSTAGE_CACHE_PATH):
    print(f"  Created: {summerstage_created}, Updated: {summerstage_updated}, Skipped: {summerstage_skipped}")
else:
    print(f"  Cache missing — run fetch_summerstage_events.py before merging.")

print(f"\nNaumburg Concerts (naumburg-events.json):")
if os.path.exists(NAUMBURG_CACHE_PATH):
    print(f"  Created: {naumburg_created}, Updated: {naumburg_updated}, Skipped: {naumburg_skipped}")
else:
    print(f"  Cache missing — run fetch_naumburg_concerts.py before merging.")

print(f"\nPublic Theater (publictheater-seasons.yml):")
if publictheater_seasons_loaded == 0:
    print(f"  No seasons configured. Edit publictheater-seasons.yml when the next season is announced.")
else:
    print(f"  Seasons: {publictheater_seasons_loaded}, Created: {publictheater_created}, Updated: {publictheater_updated}")

print(f"\nNYC Bird Alliance walks (birding-walks.yml):")
if birding_walks_loaded == 0:
    print(f"  No walks configured. Edit birding-walks.yml when the season schedule is published.")
else:
    print(f"  Walks: {birding_walks_loaded}, Created: {birding_created}, Updated: {birding_updated}")
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
