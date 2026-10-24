---
week_of: 2026-10-23
sent_date: 2026-10-23
covers: 2026-10-24 to 2026-10-30
format: combined
audience: park watchers
personas: [park-watcher]
subject: "Central Park Watcher's Digest, Oct 24–30: marathon week lands five permits, and a typo'd one got flagged anyway"
---

Marathon week arrived in the permit feed all at once: **five separate permits**
beyond the 24-day envelope, including the blue-line painting and the opening
ceremony. One of them carries a typo in its title that defeats our name
detection entirely — **and it got flagged correctly anyway**, which is the most
useful thing in this week's data.

## Weather this week

Seven sunny or mostly sunny days, 58–69°, rain 0–4%, nights 43–53°. **Two
flawless weeks back to back**, which the park has not had since August. Marathon
weekend's own forecast is just outside this window but the run-up is dry, which
matters for a build-out carrying scaffolding across the west side.

## The typo that proves the rule

The permit feed carries **`RNYRR Kids Kickoff`** — a typo'd leading R on NYRR.
Our candidate detector requires the title to start with `NYRR`, so it misses it
completely. Under the old name-pattern approach that event would have been
invisible.

It is flagged. Correctly. **Because its permit names West Drive**, and the
location rule caught it without ever reading the title.

That is the third time this autumn the location rule has caught something a name
rule could not — after the Fifth Avenue Mile and the Pink Pony Walk. The pattern
is now unambiguous: **four of the loop fixes this autumn were name patterns and
each only ever caught races we already knew; the one that worked off location
keeps catching things nobody anticipated**, including a permit with a spelling
mistake in it. Worth remembering next time the instinct is to add another name.

## Marathon week, permit by permit

| When | What | Where | Flagged |
|---|---|---|---|
| Sun Oct 25, 8–12 | NYRR Kids Kickoff | West Drive | yes |
| Wed Oct 28, 9–10 | **Blue Line Painting Ceremony** | West Drive | yes |
| Fri Oct 30, 4–7 PM | Marathon Opening Ceremony | West Drive | yes |
| Sat Oct 31, 8–12 | Dash to the Finish Line 5K Finish | Grand Army Plaza | yes |
| Sun Nov 1, 8 AM–5 PM | **TCS New York City Marathon** | Ted Corbitt Loop | yes |

All five correctly flagged, plus the 24-day envelope underneath them. **West Drive
closes three separate times this week** — a satellite race, a one-hour ceremony
and an evening ceremony — which is a shape I have not seen before: the loop going
in pieces rather than all at once.

The blue-line painting is the one worth noting for its own sake. One hour, West
Drive, the course line laid down and the ceremony public. It is the sort of entry
that only exists in the permit record and nowhere in the park's own marketing.

## The NYRR fetcher now fails four times a week

Candidates went from one to four, and **all four failed with http_302**. This is
not the platform migration fixed on October 3 — it is slug derivation meeting
permit titles with administrative suffixes:

- `2026 TCS NYC Marathon - Manhattan - Central Park`
- `2026 TCS NYC Marathon - Opening Ceremony`
- `2026 TCS NYC Marathon Blue Line Painting Ceremony`
- `Abbott Dash to the Finish Line 5K- Finish`

None of those can map to a NYRR event URL, because none of them is an event name
— they are permit administrative labels. The enrichment is not needed; the
curated entries carry the real race data. But it will log four failures a week
until the marathon passes, and a persistent failure that is actually fine is
exactly the kind of noise that trains you to stop reading the log.

## The Great Lawn, week twelve

Zero field permits. No closure permit anywhere in the record. **Twelve consecutive
weeks.** North Meadow carries 75 of the week's 100 field permits; Heckscher has 9.

## Bethesda Terrace, ninth extension

Now **November 23.** The sequence: October 13, 25, 27, November 2, 4, 9, 11, 16,
18, 23. Ten readings, nine extensions, horizon still four weeks out. The closure
is now in its eighth week and has never once had a stated reason.

## Quick recap

- **A typo'd permit (`RNYRR Kids Kickoff`) got flagged correctly** because its location names West Drive. Third time this autumn location caught what names could not.
- **Five marathon-week permits landed**, all flagged, plus the 24-day envelope.
- **West Drive closes three times this week** in pieces — Sunday, Wednesday, Friday.
- **The blue line gets painted Wednesday 9–10 AM**, publicly, on West Drive.
- **The NYRR fetcher now fails four times weekly** on permit titles that are administrative labels, not event names. Harmless, and the kind of noise that erodes log-reading.
- **Great Lawn week twelve. Bethesda ninth extension, to November 23.**

Until next week,
Central Park Guide
