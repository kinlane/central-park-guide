---
week_of: 2026-11-21
sent_date: 2026-11-21
covers: 2026-11-22 to 2026-11-28
format: combined
audience: park watchers
personas: [park-watcher]
subject: "Central Park Watcher's Digest, Nov 22–28: the December closure cluster was never real — it was the edge of the dataset"
---

Hi,

I have to retract the thing I have been writing to you about for a month, and the retraction is more interesting than the finding was.

## There is no December closure cluster

Since late October I have reported a group of long closures — both Bethesda permits, the Swedish Cottage lawn, the East 96th Street playground lawn, East Meadow, the East 106th Street maintenance, and lately Harlem Meer — that all appeared to end on the same day. I reported the shared date moving as a group, five times, and I told you that separate permits at separate locations extending in lockstep was a scheduling decision rather than a coincidence. In the Reddit draft I went further and asked readers to go look for posted notices.

**None of it was real.** Here is the test I should have run a month ago. Ask the API for a single permit with no date filter at all:

```
?event_id=895600            (Bethesda, "Closed")
-> exactly 31 rows, 2026-11-21 .. 2026-12-21
```

Same shape for 987031, 987042, 987054, 987060. And the clincher: of the **68 permits in this week's pull dated after December 21, every single one has exactly one row.** Inside the window, nine permits have more than five.

The dataset stores one row per occurrence and **only materializes a recurring permit about 31 days ahead of whenever you ask**. Nothing marks the truncation. So every long closure stops dead at the same place — not because they share an end date, but because that is where the data stops.

Which means every "move" I reported was the calendar advancing:

| Pull date | What I told you | Pull + ~29 |
|---|---|---|
| Nov 6 | "they all end Dec 6" | Dec 6 |
| Nov 8 | "they moved to Dec 8, together" | Dec 8 |
| Nov 14 | "moved again, Dec 13" | Dec 13 |
| Nov 15 | "Dec 14, and a seventh joined" | Dec 14 |
| Nov 21 | — | Dec 20 |

A perfect fit, every week. The East 106th maintenance "breaking away to December 10 and then rejoining" was its weekday-only pattern meeting that same edge. Harlem Meer "being filed into the cluster already carrying the shared end date" was just a new permit hitting the same wall.

**What is actually true:** Bethesda Terrace, the Swedish Cottage lawn, the E 96th playground lawn and Harlem Meer are closed, every day, with **no end date visible in this dataset at all.** I do not know when any of them reopens. That is a smaller and duller claim than the one I made, and it has the advantage of being supported.

The part I am least comfortable with is that this is the second time in eight days I have read a window edge as a fact. The first was the gala permit, where my own seven-day email window was the filter. I wrote myself a note afterwards to measure the full series outside the filter — and then checked outside *my* filter and never outside the *source's*. The filter I did not know about was the one that got me.

## The week itself

**Sun 22, 8–11 AM — Race to Deliver 4M.** Two records for one race, which is a data note worth your time: the curated NYRR seed (`charity-nyrr-…`, Ted Corbitt Loop, 8–10) and the city permit that has now actually been filed (890908, "102nd Street Cross Drive, 72nd Street Cross Drive, Center Loop", 8–11). Different `event_id`s, so our merge key does not collapse them and the race appears twice in the pipeline.

That permit is also a clean demonstration of last week's fix. It names two **cross** drives and the **Center Loop** — and cross drives correctly do not count as loop impact. `Center Loop` was missing from our vocabulary until November 14. **Without that one-line addition this race would have scored as no loop impact at all.** Six days from fix to a live catch.

**Yesterday, Sat 21 — the Central Park Turkey Trot**, permit 906222, 10–11 AM across Bandshell Plaza, Center Drive, Center Loop, East Drive and the cross drives. **It was not in the feed when I pulled on November 15**, which makes it the third event in two weeks filed inside its own week. It also falsifies the week-5 Reddit draft, which says the loop was clear all week. That draft is marked do-not-post.

**Tue 24 and Wed 25 — two Macy's parade bands at the Bandshell.** Pearland High School (Texas) 9–10 AM Tuesday; the UConn band 10 AM–3 PM Wednesday. Both are marching in Thursday's 100th parade. These are the kind of permit that justifies the whole exercise: genuinely good public events that exist nowhere but the permit list.

**Thu 26 — Thanksgiving.** Nothing permitted inside the park. The parade owns Central Park West from 77th down. 50°, 72% rain, 21 mph wind; the balloon rule is 23 mph sustained / 34 gusting, so it will be a morning call.

**Field permits: 17**, nine at North Meadow, against a September peak of 223.

**The Great Lawn: still zero**, with the Nov 7 picnic the only booking since July.

## Quick recap

- **The December cluster was the edge of a 31-day publishing window.** Not a schedule. Retracted in full.
- **The real end dates of the Bethesda and lawn closures are unknowable from this source.**
- **Race to Deliver is double-counted** — curated seed plus newly-filed permit, different IDs.
- **The Center Loop fix caught its first live race** six days after it shipped.
- **A third late filing in two weeks**: the Turkey Trot, filed inside its own week.

Watching, and testing the source first from now on,
Kin
