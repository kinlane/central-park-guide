---
week_of: 2026-10-09
sent_date: 2026-10-09
covers: 2026-10-10 to 2026-10-16
format: combined
audience: park watchers
personas: [park-watcher]
subject: "Central Park Watcher's Digest, Oct 10–16: a permit called 'Party' holds East Drive for twenty hours, twice, and our filter had deleted it"
---

The most consequential thing in this week's data is a permit titled **"Party."** It holds Cedar Hill, the Hans Christian Andersen Statue and **East Drive from midnight to 8 PM on both Wednesday and Thursday** — forty hours of road across two days, correctly flagged as affecting the loop.

Our own digest builder had suppressed it entirely, as an uninformative title. Both days read "nothing one-off." That is the third presentation failure in three weeks, and the first that deleted a closure rather than merely burying it.

## Weather this week

Saturday 70° and dry, Sunday 64° with periods of rain at 93%, Columbus Day 69° and 49%, Tuesday 73° and warmest, then 66°, 63°, and a showery 64° Friday. The triathlon's final day gets the rain.

## The filter deleted a road closure

Three weeks ago the builder collapsed the Global Citizen Festival into one line beside the birding walks. Two weeks ago it did the same to the Big Apple Triathlon and dropped it from the lead block. This week it went further: a list of uninformative permit titles — "closed", "party", "picnic", "miscellaneous", "event", "tbd" — matched this permit on its name and **removed it from the brief altogether**.

The detail that makes it worth your attention: the same code already scores loop-affecting events at **+100, the highest weight it assigns to anything.** The pipeline knows these events outrank everything else in the brief. The title filter simply ran first and got to veto it.

It is fixed — a junk title can no longer suppress an event that holds road — and the permit now leads this week's brief where it belongs. But the pattern across three weeks is the finding: **the tagging has been right every single time, and the presentation layer has lost the event three different ways.** Correct data is not the same as a correct newsletter.

## Wed Oct 14 – Thu Oct 15 — the closure itself

Midnight to 8 PM, both days, over Cedar Hill, the Hans Christian Andersen Statue and East Drive.

Two things to note. First, the permit is a **private booking** — it carries the private-events tags — and this is the largest piece of road a private event has held in this series. Second, it is the third multi-day drive hold in six weeks: Global Citizen's eleven days on the Great Lawn, the triathlon's four days on every drive, and now forty hours of East Drive. The preceding three weeks of September had none.

## The display was hiding the road too

Separately, and found by chasing the same permit: the event page's own location line was showing **"Cedar Hill, Hans Christian Anderson Statue"** and dropping East Drive, because the display form keeps only the first two parts of a permit's location. The triathlon's page read "Cherry Hill, Wagner Cove" for a permit covering every drive in the park.

Measured across the corpus: **6 of 1,102 events were displaying a location that omitted a drive or the loop.** Also fixed — the display still truncates ordinary events for readability, but no longer drops road. Four events still omit the 72nd Street Cross Drive, which is deliberately excluded as a cross drive that does not close the loop.

## North Meadow overtakes Heckscher

Field permits this week: **82 at North Meadow, 46 at Heckscher, 18 on the tennis courts.** North Meadow is now the park's busiest venue, which it has not been at any point in this series.

The full arc since early September: Heckscher went 24 → 111 → 46, North Meadow 5 → 83 → 82. Heckscher absorbed the Great Lawn's displaced leagues first and has now shed more than half of them, while North Meadow has held its gain. Worth watching whether Heckscher's drop is seasonal wind-down or a second relocation.

## The Great Lawn, week eight

Zero field permits. Six non-league bookings, one of them Saturday's public pilates class. **Still no closure or maintenance permit anywhere in the record.**

Eight weeks of the same absence. The lawn is open, used, and absent from the league calendar, and nothing in the permit system says why.

## Bethesda Terrace, fifth extension

Now running to **November 9**. The sequence: October 13, 25, 27, November 2, 4, 9. Six readings, five extensions, horizon still about four weeks out.

## Quick recap

- **A permit titled "Party" holds East Drive midnight–8 PM Wednesday and Thursday** — forty hours of road, a private booking, correctly flagged.
- **Our filter had deleted it** as an uninformative title, leaving both days blank. Third presentation failure in three weeks; the first to remove rather than bury. Fixed.
- **The tagging has been right every time.** The presentation layer has lost the event three different ways.
- **Event pages were hiding drives** in their location line — 6 of 1,102. Fixed.
- **North Meadow overtakes Heckscher** 82 to 46, a first in this series.
- **Great Lawn: week eight**, zero field permits, no closure permit. **Bethesda: fifth extension**, to November 9.

Until next week,
Central Park Guide
