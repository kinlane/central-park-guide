---
week_of: 2026-10-18
sent_date: 2026-10-18
covers: 2026-10-19 to 2026-10-25
format: combined
audience: park watchers
personas: [park-watcher]
subject: "Central Park Watcher's Digest, Oct 19–25: the marathon permit lands as a 24-day envelope, and the Heckscher call comes in"
---

*Friday's digest ran through the 23rd; the midweek will be familiar. Two findings
are new, and one long-running question is now answerable.*

The city's **TCS New York City Marathon permit went live this week** — the first
time the marathon has appeared in the permit feed at all, rather than only in our
curated seed. It is a **24-day envelope**: October 18 through November 10, all
day, across twenty-one locations.

And after holding it for two pulls, **the Heckscher question has an answer.**

## Weather this week

Seven sunny days, 59–66°, rain 0–12%, nights 44–51°. The best full week since
early October, and dry weather across a quiet calendar is when restoration gets
scheduled — watch for new lawn closures appearing next week.

## The marathon permit, and what a 24-day flag does to a newsletter

Permit `890891` covers West, East and Center Drive, Tavern on the Green, Bethesda
Terrace, Bow Bridge, Belvedere Castle, Dead Road, Mineral Springs, Frisbee Hill
and twelve more. It is correctly flagged as affecting the loop.

The consequence is the interesting part. **Loop-affecting events in our data went
from 5 to 29 this week, and 24 of those are this single permit** — one per day
from now to November 10. A digest reading the flag literally would tell runners
the loop is closed every day for three weeks, which is false. The loop is open
all of this week; what is going up is scaffolding.

This is the Global Citizen shape again — an administrative build-and-strike
envelope wearing the same flag as a three-hour race — and it is the fourth time
this autumn that correct tagging has produced a misleading newsletter if read
without judgement. I have written around it by hand. **The structural question is
whether an all-day multi-week permit should carry the same flag as a timed
closure**, and that is worth deciding before the Thanksgiving and holiday
permits land.

## Two marathon records now exist, and I left both

November 1 carries the permit *and* our curated entry:

| | Covers | Holds |
|---|---|---|
| Permit `890891` | Oct 18–Nov 10, all day, 21 places | the three-week infrastructure footprint |
| `charity-walks.yml` | Nov 1, 8 AM–5 PM, Ted Corbitt Loop | the race — gun time, 55,000 runners |

There is a mechanism to collapse them — `supersedes_permit_ids`, already used for
one permit — and I did not use it, because superseding would discard the
footprint, which is real information. They are complementary rather than
duplicated. Flagging it so the choice is yours rather than mine by default.

Separately: the NYRR enrichment failed this permit with a 302. **Not** the
platform migration I fixed on October 3 — the permit's title is *"2026 TCS NYC
Marathon - Manhattan - Central Park"*, and those administrative suffixes mangle
the derived slug. Harmless, since the curated entry already carries the real race
data and source URL, but worth knowing the slug derivation breaks on permit
titles that carry borough and park qualifiers.

## The Heckscher call: a two-stage relocation

Three weeks ago I reported Heckscher collapsing and said it was probably posting
lag. Two weeks ago I said the lag explanation was weakening and I would wait two
pulls. Both pulls are in.

| | Nov total events | North Meadow | Heckscher |
|---|---|---|---|
| Oct 11 | 244 | 78 | 3 |
| Oct 16 | 316 | 117 | 4 |
| Oct 18 | **341** | **117** | **4** |

November has grown by nearly a hundred events across three pulls. **Heckscher has
gained one permit in that entire time.** It is not filling. October says the same:
North Meadow 148, tennis 37, Heckscher 17.

So the answer is **a two-stage relocation, and it is now safe to say so.** The
Great Lawn's leagues moved to Heckscher in September, peaking at 111 permits a
week. Heckscher has since handed almost all of them to North Meadow, which now
carries the entire field calendar. Three venues, two moves, one autumn.

What I still cannot tell you is **why**, for either move. There is no closure or
maintenance permit for the Great Lawn, and none for Heckscher either.

## The Great Lawn, week eleven

Zero field permits. No closure permit anywhere in the record. Eleven consecutive
weeks.

## Bethesda Terrace, eighth extension

Now **November 18.** October 13, 25, 27, November 2, 4, 9, 11, 16, 18. Nine
readings, eight extensions, horizon still four weeks out and moving with the
calendar.

## Quick recap

- **The marathon permit is a 24-day envelope** across 21 locations. Loop-affecting events went 5 → 29; 24 are this one permit. The loop is open this week.
- **Fourth time this autumn correct tagging produced a misleading digest.** Worth deciding whether multi-week envelopes should carry the timed-closure flag before the holiday permits land.
- **Two marathon records stand for Nov 1**, deliberately — permit holds the footprint, curated holds the race.
- **The Heckscher question is answered: a two-stage relocation.** Great Lawn → Heckscher in September, Heckscher → North Meadow since. Still no permit explaining either move.
- **Great Lawn week eleven. Bethesda eighth extension, to November 18.**

Until next week,
Central Park Guide
