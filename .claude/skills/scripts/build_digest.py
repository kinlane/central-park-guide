#!/usr/bin/env python3
"""Assemble ONE combined event digest for a subscriber across all their personas.

The per-persona emails send N separate messages to a subscriber who picked N
personas. This builds the union instead: every event the subscriber would have
seen in any of their persona emails, deduped to one entry, annotated with which
of their personas asked for it, grouped by day.

The output is a structured brief — NOT the finished email. A human (or Claude)
writes the prose from it, following draft-persona-email.md's editorial rules.

Usage:
  python3 build_digest.py --personas runner,cyclist --start 2026-08-07 [--days 7]
  python3 build_digest.py --subscriber kinlane@gmail.com --start 2026-08-07
  python3 build_digest.py --all-subscribers --start 2026-08-07 --stats-only

Persona filters come from _data/personas.yml `email_filter:` blocks, which encode
the include-lists in .claude/skills/draft-persona-email.md.
"""
import argparse, os, re, sys, json, datetime, collections
import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..', '..', '..'))
EVENTS_DIR = os.path.join(REPO_ROOT, '_events')
PERSONAS_YML = os.path.join(REPO_ROOT, '_data', 'personas.yml')
ENV_FILE = os.path.normpath(os.path.join(REPO_ROOT, '..', '.env'))

# Tags that mark an event as a private booking — suppressed for every persona
# except walker and park-watcher (draft-persona-email.md "Soft-exclude rules").
PRIVATE_TAGS = {"Private Events", "Private Booking", "Wedding", "Ceremony",
                "Reception", "Birthday", "Celebration", "Memorial"}
PRIVATE_OK_PERSONAS = {"walker", "park-watcher"}

# Field-sport permits are rolled up rather than listed one by one.
ROLLUP_TAGS = {"Softball", "Baseball", "T-Ball", "Kickball", "Soccer", "Tennis",
               "Pickleball", "Volleyball", "Basketball"}
ROLLUP_OK_PERSONAS = {"sports-fan"}

# Populated by load_events(); reported so the leak stays visible rather than
# being silently filtered.
FOREIGN_PARK_SKIPS = []


def load_env():
    env = {}
    if not os.path.exists(ENV_FILE):
        return env
    for line in open(ENV_FILE):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def parse_front_matter(path):
    raw = open(path, encoding='utf-8').read()
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, re.DOTALL)
    if not m:
        return None, ""
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None, ""
    return fm, m.group(2).strip()


def load_personas():
    d = yaml.safe_load(open(PERSONAS_YML))
    out = {}
    for p in d.get('personas', []):
        ef = p.get('email_filter') or {}
        out[p['id']] = {
            'id': p['id'],
            'title': p.get('title', p['id']),
            'audience': ef.get('audience', p.get('title', p['id']).lower() + 's'),
            'include_tags': set(ef.get('include_tags') or p.get('tags') or []),
            'exclude_tags': set(ef.get('exclude_tags') or []),
            'hard_include_affects_loop': bool(ef.get('hard_include_affects_loop')),
            'has_email_filter': bool(ef),
        }
    return out


def load_events(start, end):
    events = []
    for fn in sorted(os.listdir(EVENTS_DIR)):
        if not fn.endswith('.md'):
            continue
        fm, body = parse_front_matter(os.path.join(EVENTS_DIR, fn))
        if not fm or not fm.get('date'):
            continue
        d = fm['date']
        if isinstance(d, str):
            try:
                d = datetime.date.fromisoformat(d[:10])
            except ValueError:
                continue
        elif isinstance(d, datetime.datetime):
            d = d.date()
        if not isinstance(d, datetime.date):
            continue
        if not (start <= d <= end):
            continue
        # Guard: a handful of orphan files carry a location naming a DIFFERENT
        # park (Astoria/Pelham Bay/Cunningham), whose lawn names collided with
        # Central Park's places vocabulary. Never let one reach a subscriber.
        loc = str(fm.get('location', ''))
        m2 = re.match(r"^([A-Z][A-Za-z.' ]+ Park):", loc)
        if m2 and 'Central Park' not in m2.group(1):
            FOREIGN_PARK_SKIPS.append((fn, loc))
            continue
        fm['_date'] = d
        fm['_file'] = fn
        fm['_slug'] = fn[:-3]
        fm['_tags'] = set(fm.get('tags') or [])
        events.append(fm)
    return events


def match_personas(ev, personas, selected):
    """Which of the subscriber's personas want this event, and why."""
    hits = {}
    tags = ev['_tags']
    affects = bool(ev.get('affects_loop')) or 'Affects Loop' in tags
    for pid in selected:
        p = personas.get(pid)
        if not p:
            continue
        reasons = []
        if affects and p['hard_include_affects_loop']:
            reasons.append('affects-loop')
        overlap = tags & p['include_tags']
        if overlap:
            reasons.append('tags:' + ','.join(sorted(overlap)))
        if not reasons:
            continue
        # Soft-excludes never override a hard affects-loop include.
        if 'affects-loop' not in reasons:
            if tags & p['exclude_tags']:
                continue
            if (tags & PRIVATE_TAGS) and pid not in PRIVATE_OK_PERSONAS:
                continue
        hits[pid] = reasons
    return hits, affects


def build(selected, start, days):
    end = start + datetime.timedelta(days=days - 1)
    personas = load_personas()
    unknown = [p for p in selected if p not in personas]
    events = load_events(start, end)

    kept, rolled, dropped = [], [], 0
    for ev in events:
        hits, affects = match_personas(ev, personas, selected)
        if not hits:
            dropped += 1
            continue
        ev['_personas'] = hits
        ev['_affects_loop'] = affects
        # Field-sport league permits go to a rollup unless something other than
        # sports-fan wants them, or they affect the loop.
        is_rollup = (ev['_tags'] & ROLLUP_TAGS) and not affects and \
            set(hits) <= ROLLUP_OK_PERSONAS
        (rolled if is_rollup else kept).append(ev)

    kept.sort(key=lambda e: (e['_date'], str(e.get('time') or '')))
    by_day = collections.OrderedDict()
    for i in range(days):
        d = start + datetime.timedelta(days=i)
        by_day[d] = {'events': [], 'rollup': []}
    for ev in kept:
        by_day[ev['_date']]['events'].append(ev)
    for ev in rolled:
        by_day[ev['_date']]['rollup'].append(ev)

    return {
        'start': start, 'end': end, 'days': days,
        'selected': selected, 'unknown_personas': unknown,
        'personas': personas, 'by_day': by_day,
        'kept': kept, 'rolled': rolled,
        'scanned': len(events), 'dropped': dropped,
    }


def fmt_time(ev):
    t, e = ev.get('time'), ev.get('end_time')
    if t and e:
        return f"{t}-{e}"
    return t or ""


# Permit titles that carry no information on their own. The permit feed uses
# these as placeholders; a human drafter drops them silently.
JUNK_TITLES = {"closed", "party", "picnic", "miscellaneous", "event", "tbd"}

# A title repeated on this many days in the window is "steady all week" and gets
# one collapsed line instead of one line per day (draft-persona-email.md,
# "Recurring weekly events").
RECURRING_THRESHOLD = 3


def collapse_and_rank(r):
    """Split the kept set into headline / day-by-day one-offs / all-week recurring.

    A naive union of 10 personas produced 73 rows for one week, but only 35
    distinct titles — the rest was the same recurring permit reprinted daily.
    """
    # Group case-insensitively — title cleanup is not stable across sources, so
    # "SummerStage through the Lens" and "Summerstage Through the Lens" are the
    # same recurring exhibit and must collapse to one line.
    by_title = collections.defaultdict(list)
    for ev in r['kept']:
        by_title[str(ev.get('title', '')).strip().lower()].append(ev)
    by_title = {evs[0].get('title', k): evs for k, evs in by_title.items()}

    oneoffs, recurring, junk = [], [], []
    for title, evs in by_title.items():
        if title.lower().strip() in JUNK_TITLES:
            junk.append((title, evs))
            continue
        if len(evs) >= RECURRING_THRESHOLD:
            recurring.append((title, evs))
        else:
            oneoffs.extend(evs)

    def score(ev):
        s = 0
        if ev['_affects_loop']:
            s += 100
        s += 10 * len(ev['_personas'])
        if ev.get('source_url'):
            s += 8          # came from a curated source, not a bare permit
        if ev.get('cost'):
            s += 2
        return s

    oneoffs.sort(key=lambda e: (-score(e), e['_date'], str(e.get('time') or '')))
    recurring.sort(key=lambda kv: -len(kv[1]))
    return {
        'oneoffs': oneoffs,
        'recurring': recurring,
        'junk': junk,
        'headline': [e for e in oneoffs if e['_affects_loop']] + \
                    [e for e in oneoffs if not e['_affects_loop']][:4],
        'score': score,
    }


def render_email_brief(r):
    """Email-ready brief: what leads, what's day-by-day, what's just background."""
    c = collapse_and_rank(r)
    score = c['score']
    L = []
    L.append(f"# Email brief — {r['start']:%a %b %-d} to {r['end']:%a %b %-d, %Y}")
    L.append(f"Personas: {', '.join(r['selected'])}")
    L.append(f"{r['scanned']} scanned -> {len(r['kept'])} relevant -> "
             f"{len(c['oneoffs'])} one-off + {len(c['recurring'])} recurring "
             f"+ {len(c['junk'])} junk-title suppressed")
    L.append("")

    L.append("## LEAD WITH THESE")
    for ev in c['headline']:
        star = " **AFFECTS LOOP**" if ev['_affects_loop'] else ""
        L.append(f"- {ev['_date']:%a %b %-d} {fmt_time(ev)} — {ev.get('title')}{star}")
        L.append(f"  @ {ev.get('place')} | wanted by {len(ev['_personas'])} of your "
                 f"personas: {','.join(sorted(ev['_personas']))}")
        if ev.get('source_url'):
            L.append(f"  {ev['source_url']}")
    L.append("")

    L.append("## DAY BY DAY (one-offs only, ranked within each day)")
    byday = collections.defaultdict(list)
    for ev in c['oneoffs']:
        byday[ev['_date']].append(ev)
    for i in range(r['days']):
        d = r['start'] + datetime.timedelta(days=i)
        evs = sorted(byday.get(d, []), key=lambda e: -score(e))
        if not evs:
            L.append(f"\n### {d:%a %b %-d} — nothing one-off")
            continue
        L.append(f"\n### {d:%a %b %-d}")
        for ev in evs:
            star = " [LOOP]" if ev['_affects_loop'] else ""
            L.append(f"- {fmt_time(ev):12} {ev.get('title')}{star}")
            L.append(f"    @ {ev.get('place')} | for: {','.join(sorted(ev['_personas']))}")
            if ev.get('description'):
                L.append(f"    {ev['description'][:170]}")
            if ev.get('source_url'):
                L.append(f"    {ev['source_url']}")
    L.append("")

    L.append("## STEADY ALL WEEK (collapse to one line each — do not reprint daily)")
    for title, evs in c['recurring']:
        days = sorted({e['_date'] for e in evs})
        who = sorted({p for e in evs for p in e['_personas']})
        span = f"{len(days)} days ({days[0]:%a %-d}-{days[-1]:%a %-d})"
        times = sorted({fmt_time(e) for e in evs if fmt_time(e)})
        L.append(f"- {title} — {span} @ {evs[0].get('place')} | for: {','.join(who)}")
        if times:
            L.append(f"    times: {'; '.join(times[:3])}")
    L.append("")

    if c['junk']:
        L.append("## SUPPRESSED (uninformative permit titles)")
        for title, evs in c['junk']:
            L.append(f"- \"{title}\" x{len(evs)} @ {evs[0].get('place')}")
        L.append("")

    if FOREIGN_PARK_SKIPS:
        L.append("## !! BLOCKED — events in ANOTHER park (data defect, fix upstream)")
        for fn, loc in FOREIGN_PARK_SKIPS:
            L.append(f"- {fn}  location: {loc}")
        L.append("")

    total_roll = len(r['rolled'])
    if total_roll:
        byplace = collections.Counter(e.get('place', '?') for e in r['rolled'])
        L.append(f"## SPORTS PERMIT ROLLUP ({total_roll} field permits, one line max)")
        L.append("  " + "; ".join(f"{v}x {k}" for k, v in byplace.most_common(6)))
    return "\n".join(L)


def render_brief(r):
    L = []
    L.append(f"# Combined digest — {r['start']:%a %b %-d} to {r['end']:%a %b %-d, %Y}")
    L.append("")
    L.append(f"Personas: {', '.join(r['selected'])}")
    if r['unknown_personas']:
        L.append(f"!! UNKNOWN personas (no definition, contributed nothing): {r['unknown_personas']}")
    no_filter = [p for p in r['selected']
                 if p in r['personas'] and not r['personas'][p]['has_email_filter']]
    if no_filter:
        L.append(f"!! personas with no email_filter block (fell back to site tags): {no_filter}")
    L.append(f"Events in window: {r['scanned']} scanned | {len(r['kept'])} kept "
             f"| {len(r['rolled'])} rolled up | {r['dropped']} not relevant")
    L.append("")

    # Which personas actually earned their place in this digest
    counts = collections.Counter()
    for ev in r['kept'] + r['rolled']:
        for pid in ev['_personas']:
            counts[pid] += 1
    L.append("## Per-persona contribution")
    for pid in r['selected']:
        n = counts.get(pid, 0)
        flag = "   <- contributed nothing" if n == 0 else ""
        L.append(f"- {pid}: {n}{flag}")
    L.append("")

    # Events wanted by only one persona are the ones a combined email risks
    # burying; events wanted by many are the shared spine.
    solo = [e for e in r['kept'] if len(e['_personas']) == 1]
    shared = [e for e in r['kept'] if len(e['_personas']) > 2]
    L.append(f"## Overlap: {len(shared)} events wanted by 3+ personas, "
             f"{len(solo)} by exactly one")
    L.append("")

    loop = [e for e in r['kept'] if e['_affects_loop']]
    L.append(f"## Hard-includes (affects_loop): {len(loop)}")
    for ev in loop:
        L.append(f"- {ev['_date']:%a %b %-d} {fmt_time(ev)} — {ev.get('title')} "
                 f"@ {ev.get('place')}")
    L.append("")

    L.append("## Day by day")
    for d, blk in r['by_day'].items():
        evs, roll = blk['events'], blk['rollup']
        if not evs and not roll:
            L.append(f"\n### {d:%a %b %-d} — nothing relevant")
            continue
        L.append(f"\n### {d:%a %b %-d} — {len(evs)} event(s)"
                 + (f" + {len(roll)} rolled up" if roll else ""))
        for ev in evs:
            who = ','.join(sorted(ev['_personas']))
            star = " [AFFECTS LOOP]" if ev['_affects_loop'] else ""
            L.append(f"- {fmt_time(ev):12} {ev.get('title')}{star}")
            L.append(f"  place: {ev.get('place')} | tags: {', '.join(sorted(ev['_tags']))}")
            L.append(f"  for: {who}")
            if ev.get('source_url'):
                L.append(f"  url: {ev['source_url']}")
            if ev.get('description'):
                L.append(f"  desc: {ev['description'][:200]}")
        if roll:
            byplace = collections.Counter(e.get('place', '?') for e in roll)
            L.append(f"  ROLLUP (sports permits): " +
                     "; ".join(f"{v}x {k}" for k, v in byplace.most_common()))
    return "\n".join(L)


def subscribers_from_s3():
    import boto3
    env = load_env()
    s3 = boto3.client("s3", aws_access_key_id=env["AWS_KEY"],
                      aws_secret_access_key=env["AWS_SECRET"], region_name="us-east-1")
    resp = s3.list_objects_v2(Bucket="centralpark-guide", Prefix="updates/")
    subs = []
    for obj in resp.get("Contents", []):
        if not obj["Key"].endswith(".yml"):
            continue
        rec = yaml.safe_load(s3.get_object(Bucket="centralpark-guide",
                                           Key=obj["Key"])["Body"].read().decode())
        if rec.get("verified"):
            subs.append(rec)
    return subs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--personas')
    ap.add_argument('--subscriber')
    ap.add_argument('--all-subscribers', action='store_true')
    ap.add_argument('--start', required=True)
    ap.add_argument('--days', type=int, default=7)
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--email-brief', action='store_true')
    ap.add_argument('--stats-only', action='store_true')
    a = ap.parse_args()

    start = datetime.date.fromisoformat(a.start)

    if a.all_subscribers:
        for sub in subscribers_from_s3():
            r = build(sub.get('personas', []), start, a.days)
            em = sub['email']
            masked = em.split('@')[0][:2] + '***@' + em.split('@')[-1]
            print(f"{masked:30} {len(sub.get('personas', [])):2} personas -> "
                  f"1 email, {len(r['kept'])} events "
                  f"(was {len(sub.get('personas', []))} emails)")
        return

    if a.subscriber:
        match = [s for s in subscribers_from_s3() if s['email'] == a.subscriber]
        if not match:
            sys.exit(f"No verified subscriber: {a.subscriber}")
        selected = match[0].get('personas', [])
    elif a.personas:
        selected = [p.strip() for p in a.personas.split(',') if p.strip()]
    else:
        sys.exit("Need --personas, --subscriber, or --all-subscribers")

    r = build(selected, start, a.days)
    if a.json:
        out = []
        for ev in r['kept']:
            out.append({
                'date': ev['_date'].isoformat(), 'time': ev.get('time'),
                'end_time': ev.get('end_time'), 'title': ev.get('title'),
                'place': ev.get('place'), 'tags': sorted(ev['_tags']),
                'personas': ev['_personas'], 'affects_loop': ev['_affects_loop'],
                'slug': ev['_slug'], 'source_url': ev.get('source_url'),
                'description': ev.get('description'),
            })
        print(json.dumps(out, indent=2))
    elif a.email_brief:
        print(render_email_brief(r))
    elif a.stats_only:
        print(f"{len(selected)} personas -> {len(r['kept'])} events "
              f"({len(r['rolled'])} rolled up, {r['dropped']} dropped)")
    else:
        print(render_brief(r))


if __name__ == '__main__':
    main()
