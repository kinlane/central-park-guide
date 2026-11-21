---
week_of: 2026-11-21
sent_date: 2026-11-21
covers: 2026-11-22 to 2026-11-28
format: combined
audience: park watchers
personas: [park-watcher]
subject: "Central Park Watcher's Digest, Nov 22–28: two Macy's parade bands in the permit list, and a race the Center Loop fix caught"
---

Hi,

Thin week in the record, but three things in it are worth your time — a race that only registers as a loop closure because of a fix we shipped a week ago, two marching bands hiding in the permit list, and a third late filing in a fortnight.

## The closures, stated plainly

Bethesda Terrace and Fountain is closed every day this week under **two separate permits with different titles at the same location** — 895600, titled only "Closed", and 987031, "Central Park Closure". The Swedish Cottage lawn, the East 96th Street playground lawn and the Harlem Meer picnic area are closed all week too, and East Meadow is closed weekends.

**The permit feed does not publish an end date for any of them.** The dataset lists a recurring permit's individual days roughly a month out from whenever you query it and then simply stops, with nothing marking the truncation — so the last day you can see is a property of the query, not of the permit. I cannot tell you when Bethesda reopens, and I would rather say that than infer it.

If you ever pass a posted notice at one of those spots, the sign will know more than the API does.

## The week itself

**Sun 22, 8–11 AM — Race to Deliver 4M.** Two records for one race, which is a data note worth your time: the curated NYRR seed (`charity-nyrr-…`, Ted Corbitt Loop, 8–10) and the city permit that has now actually been filed (890908, "102nd Street Cross Drive, 72nd Street Cross Drive, Center Loop", 8–11). Different `event_id`s, so our merge key does not collapse them and the race appears twice in the pipeline.

That permit is also a clean demonstration of last week's fix. It names two **cross** drives and the **Center Loop** — and cross drives correctly do not count as loop impact. `Center Loop` was missing from our vocabulary until November 14. **Without that one-line addition this race would have scored as no loop impact at all.** Six days from fix to a live catch.

**Yesterday, Sat 21 — the Central Park Turkey Trot**, permit 906222, 10–11 AM across Bandshell Plaza, Center Drive, Center Loop, East Drive and the cross drives. **It was not in the feed when I pulled on November 15**, which makes it the third event in two weeks filed inside its own week — after the Walk to End Alzheimer's and the Festival Dei Cinque Colori. A weekly pull cadence cannot see a permit filed four days out, which is worth knowing about everything I send you.

**Tue 24 and Wed 25 — two Macy's parade bands at the Bandshell.** Pearland High School (Texas) 9–10 AM Tuesday; the UConn band 10 AM–3 PM Wednesday. Both are marching in Thursday's 100th parade. These are the kind of permit that justifies the whole exercise: genuinely good public events that exist nowhere but the permit list.

**Thu 26 — Thanksgiving.** Nothing permitted inside the park. The parade owns Central Park West from 77th down. 50°, 72% rain, 21 mph wind; the balloon rule is 23 mph sustained / 34 gusting, so it will be a morning call.

**Field permits: 17**, nine at North Meadow, against a September peak of 223.

**The Great Lawn: still zero**, with the Nov 7 picnic the only booking since July.

## Quick recap

- **Bethesda is closed under two permits at once**, and the feed publishes no end date for it or the three lawns.
- **Race to Deliver is double-counted** — curated seed plus newly-filed permit, different IDs.
- **The Center Loop fix caught its first live race** six days after it shipped.
- **A third late filing in two weeks**: the Turkey Trot, filed inside its own week.

Watching,
Kin
