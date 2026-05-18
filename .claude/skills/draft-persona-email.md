# Draft a Persona-Specific Weekly Email

Drop a weekly edition for one of the ten Central Park personas, covering the seven days from the send date. Emails are hand-drafted (no generator script). This skill is the spec: file layout, subject-line rules, voice, weather inclusion, persona-interest alignment, and — most importantly — the event-filtering rules that determine what goes in and what stays out.

## When to invoke

- User asks for a "weekly email" for a specific persona, or asks to drop the full batch (one email per persona).
- Two cadences are in use:
  - **Friday-evening edition** — `week_of` = today (Friday); body covers Friday → next Thursday inclusive.
  - **Sunday-evening edition** — `week_of` = today (Sunday); body covers **Monday → next Sunday** (a "look-ahead" week excluding the send day). The send day's events are intentionally omitted because the reader is opening on Sunday night and acting from Monday onward.
- One email per persona per drop. They live in different folders by persona; don't conflate them.

## Read the persona's interests YAML first

Each persona file in `_personas/{persona}.md` has an `interests:` block with `wants:` and `does_not_want:` arrays. **Read it before drafting.** It is the editorial filter alongside the event-tag rules below.

The `does_not_want` list is the Central Park Guide brand hallmark — what we deliberately leave out is what makes each email feel curated rather than firehose. When you're tempted to include a small wedding ceremony in the cyclist email "because it's nice color," check `does_not_want` and remove it.

## File location

```
central-park-guide/email/{YYYY-MM-DD}/{persona}-emails/email.md
```

Where `{YYYY-MM-DD}` is the Friday drop date and `{persona}` is one of: `runner`, `cyclist`, `walker`, `family`, `music-fan`, `nature-lover`, `park-watcher`, `sports-fan`, `theater-fan`, `wellness-seeker`.

## Frontmatter

```yaml
---
week_of: YYYY-MM-DD          # the Friday this drops
sent_date: YYYY-MM-DD        # same as week_of for the regular Friday cadence
audience: runners            # plural noun for the persona (runners/cyclists/walkers/families/etc.)
subject: "Central Park <Topic>: <Day Mon DD> – <Day Mon DD>"
---
```

## Subject-line rules

The subject must echo the persona's interest area — never a generic "Week Ahead" / "This Week" / "Digest" — because all ten emails land in the same inbox. See [feedback memory](../../../.claude/projects/-Users-kinlane-GitHub-new-york/memory/feedback_persona_email_subjects.md).

Established phrasings:

| Persona | Subject prefix |
|---|---|
| runner | `Central Park Running Heads-Up:` |
| cyclist | `Central Park Cycling Heads-Up:` |
| walker | `Central Park Walking Plans:` |
| family | `Central Park Family Plans:` |
| music-fan | `Central Park Music & Performance:` |
| nature-lover | `Central Park Nature Notes:` |
| park-watcher | `Central Park Watcher's Digest:` |
| sports-fan | `Central Park Sports This Week:` |
| theater-fan | (lead with the headline production) |
| wellness-seeker | `Central Park Wellness Week:` |

## Priority: events first, weather second

**The Central Park Guide is an events email with weather context — not a weather email with event mentions.** This is the single most important editorial rule. If a reader skims the email and remembers only the weather, you've failed the brand. If they remember the events with weather as a useful overlay, you've succeeded.

Concretely:

- **The body must be event-led.** Day-by-day sections lead with what's happening on that day, not the temperature.
- **Weather is a two-sentence framing block**, not the email's spine. If your day-by-day reads like a forecast with events appended, rewrite it.
- **If a day has only weather and no events**, say so plainly ("no scheduled events, just heat — early mornings only") and move on. Don't pad.
- **A 30K-person charity walk shutting the loop is bigger news than a 93°F day.** Lead with the walk every time.
- **Hard-include events (`affects_loop: true`) take priority over weather framing for that day.** If the day has both AIDS Walk and a heat advisory, the AIDS Walk is the headline; the heat is a secondary consideration in the run-window recommendation.

## Voice & structure

- **Tone:** friendly, second-person ("Hey runners," / "Hi walkers,"), opinionated recommendations ("Sunday is the day to grab a long ride," "best walking week in a while").
- **Length:** 40–70 lines of body. Not exhaustive — curated.
- **Opening line:** one sentence framing the week. Lead with the week's biggest event(s), not the weather.
- **Weather section:** A `## Weather this week` H2 block sits between the opening and the day-by-day. Two sentences max — the conditions and one persona-specific recommendation that flows from them. (See "Weather forecast" below.) **Two sentences. Resist the temptation to expand.**
- **Body:** day-grouped H2 sections, **named for the event(s) on that day, not the weather**. Good: `## Sun May 17, 10 AM–12:30 PM — AIDS Walk NY shuts the south end`. Bad: `## Tue May 19 — 93°F, this is a hard day`. Each section is a tight paragraph plus optionally a bulleted action list.
- **Recap at the bottom:** `## Quick recap` — bold lead-lines, one short sentence each. The recap leads with events; weather appears only when it materially changes the day's plan.
- **Sign-off:** persona-flavored. Examples in the existing files: "Tailwinds," (cyclist), "Have a strong week," (runner), "Enjoy the late spring," (walker).

## Weather forecast (required)

Every email includes a `## Weather this week` block sourced from the National Weather Service for Central Park. Fetch fresh on each drop — don't reuse a prior week's text.

```bash
# 1. Get the gridpoint for Central Park (40.7829, -73.9654)
curl -s "https://api.weather.gov/points/40.7829,-73.9654" | \
  python3 -c "import json,sys;print(json.load(sys.stdin)['properties']['forecast'])"

# 2. Fetch the 7-day forecast (use the URL from step 1)
curl -s "<forecast-url>" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for p in d['properties']['periods'][:14]:
    print(f\"{p['name']:24s} | {p['temperature']}°{p['temperatureUnit']} | {p['shortForecast']} | wind {p['windSpeed']} {p['windDirection']}\")"
```

The Weather block in the email is **two sentences**, not a forecast table:

1. A sentence summarizing the arc of the week (e.g., "Hot through Tuesday, thunderstorms Wednesday evening, cool and showery the rest of the week").
2. A sentence with the persona-specific implication (e.g., for a runner: "Front-load long runs Sun–Mon mornings before the Tuesday peak; Wednesday onward, cool weather is welcome — Saturday looks wet.").

Tailor the second sentence to the persona's `wants` and `does_not_want`. The Theater Fan cares about outdoor-show rain; the Wellness Seeker cares about dawn windows for practice; the Park-Watcher gets pattern-level framing ("first heat wave of the season").

## Event-filtering rules (the actual editorial decision)

Read events from `_events/` for the Fri–Fri window. Filter to the persona-relevant set using these rules. **The `affects-loop` rule is the rule that exists because we missed AIDS Walk in the May 15 batch** — re-read it before every drop.

### Hard-include: events tagged `Affects Loop`

For these personas, EVERY event with `affects_loop: true` (tag: `Affects Loop`) in the week MUST appear in the body, even if it's not a race, even if the rest of the day looks calm, and even if the event organizer markets it as "off-loop":

- **runner**
- **cyclist**
- **walker**
- **sports-fan**
- **park-watcher**

A 30K-person charity walk staged at Naumburg Bandshell with crowds entering from all four park sides is an `affects-loop` event. So is a club bike ride rolling out from Engineers' Gate at 7 AM. The point of the tag is to override the editorial instinct to describe a Sunday as "clean for runners" when something the reader cares about is in fact happening on or near the loop.

**Specifically:** if a day has an `Affects Loop` event, that day's section CANNOT say "open road," "wide-open," "the loop is yours," "clean for running," or equivalent. Re-frame as: "the loop is unusable 9 AM – 12:30 PM because of X; run before 8 or after 1, or use the bridle path / Reservoir."

### Per-persona tag include-lists

For each persona, include events matching any of these tag groups. Tags are stored Title Case (e.g., `Affects Loop`, `Runs & Races`) on event files; use the slug form when filtering programmatically.

| Persona | Include events tagged… |
|---|---|
| runner | `Affects Loop`, `Runs & Races`, `Running`, `Race`, `Marathon`, `Walk` (large charity walks only), `Closures`, `Maintenance` (when on the loop) |
| cyclist | `Affects Loop`, `Cycling`, `NYCC`, `Group Ride`, `Race`, `Closures` (East/West Drive) |
| walker | `Affects Loop`, `Walk`, `Nature`, `Garden`, `Annual Tradition`, `Free`, `Concerts & Performances` (free), `Festival`, `Family & Community` (gentle), `Closures` (path-adjacent) |
| family | `Family`, `Family & Community`, `Kids and Families`, `Free`, `Festival`, `School Program`, `Picnic`, `Annual Tradition` |
| music-fan | `Music`, `Concerts & Performances`, `Jazz`, `Salsa`, `Folk`, `Latin Music`, `Gospel`, `Blues`, `Hip-Hop`, `Opera`, `Free` |
| nature-lover | `Birds`, `Nature`, `Garden`, `Boating`, `Fishing`, `Conservancy` (Conservancy events) |
| park-watcher | `Affects Loop`, anything with `affects_loop: true`, large `Annual Tradition`, `Closures`, `Maintenance`, `Charity`, `Race`, `Festival`, `Parade` |
| sports-fan | `Affects Loop`, `Sports`, `Softball`, `Baseball`, `Soccer`, `Tennis`, `Race`, `Cycling`, `Skating` |
| theater-fan | `Theater`, `Shakespeare`, `Puppet`, `Performance`, `Comedy`, `Film` |
| wellness-seeker | `Wellness`, `Yoga`, `Meditation`, `Fitness`, `Support Group`, `Free` (wellness-flavored), `Birds` (gentle), `Nature` |

### Soft-exclude rules

- **Private events** (`Private Events`, `Private Booking`, `Wedding`, `Celebration`, `Birthday`) — generally skip in all personas EXCEPT `walker` and `park-watcher`. The walker email can name scenic spots booked for ceremonies as a "wander these elsewhere this weekend" tip. The park-watcher digest can mention them in aggregate.
- **Sport - Adult / Sport - Youth permits** — skip individually for most personas. Sports-fan gets a roll-up ("12 softball games at North Meadow Saturday, normal busy day"). Runners only need to know if Great Lawn or North Meadow access affects their cool-down.
- **Maintenance** — skip unless on the loop, on a heavily-used path, or covers a major event venue.

### Recurring weekly events

Some events repeat every week (City Girls Who Walk, Bird Watching with Birding Bob, NYCC Sunday rides). Mention them in the persona's debut email of the month and again only when there's news. Don't reprint them every Friday — readers churn from clutter.

## Cross-persona consistency

When dropping the full Friday batch:

1. **Coordinate the framing of "shared" weeks.** If you call a stretch "the best weekday running week in a while," the walker email shouldn't independently call the same stretch crowded. Pick one truth.
2. **Don't reuse paragraphs verbatim across personas.** Each persona writes the same week from their own angle. A line about CRCA crit racing is "race traffic on East Drive" for cyclists, "share the road with the peloton" for runners, "fun to walk past at 7 AM" for walkers.
3. **The recap is persona-specific.** A walker doesn't need a runner's CRCA timing breakdown.

## Worked example: AIDS Walk gap (May 17, 2026)

The May 15 batch missed AIDS Walk NY entirely — it wasn't in any data source at the time and no one cross-checked external charity-walk calendars. Now that it lives in `_data/charity-walks.yml` with `affects_loop: true`, the rule above forces it into the runner, cyclist, walker, park-watcher, and sports-fan emails for the week containing 5/17.

What the May 15 runner email got wrong:

> Sun May 17 — Sacred Sites + Folkdancers, no path issues … Sundays are clean for runners this week.

What it should have said:

> Sun May 17 morning — AIDS Walk NY shuts the south end. 30K participants stage at Naumburg Bandshell, opening ceremony 9:15 AM, 6.2-mile walk through the park starting 10 AM. East Drive in the 60s–70s is unusable 9 AM – 12:30 PM. Run before 8 AM, after 1 PM, or take the bridle path / Reservoir.

## Pre-send checklist

Before saving an email, walk through this:

- [ ] I read the persona's `_personas/{persona}.md` `interests:` block, and the body reflects both the `wants` AND avoids the `does_not_want`.
- [ ] Subject line uses the persona's established prefix (table above).
- [ ] Body covers the 7 days from the send date inclusive (Fri→Thu or Sun→Sat depending on cadence).
- [ ] **For runner / cyclist / walker / sports-fan / park-watcher:** I queried `_events/` for `affects_loop: true` in the date range AND `_data/charity-walks.yml` for the date range, and every match appears in the body as a hard-include. If a day has one, the day's framing reflects that.
- [ ] **Event priority enforced:** when I skim the body, each day's section reads as an events post with weather context — not the other way around. Day H2 headings name events, not temperatures.
- [ ] **Weather this week** block is present, freshly fetched from NWS, two sentences, with a persona-specific implication.
- [ ] Recap section at bottom with bold lead-lines; recap leads with events, not weather.
- [ ] Sign-off matches the persona's voice.
- [ ] I didn't reuse a paragraph verbatim from another persona's email for the same week.
- [ ] Frontmatter `week_of` and `sent_date` are today's date.
