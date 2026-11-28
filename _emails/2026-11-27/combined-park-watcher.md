---
week_of: 2026-11-27
sent_date: 2026-11-27
covers: 2026-11-28 to 2026-12-04
format: combined
audience: park watchers
personas: [park-watcher]
subject: "Central Park Watcher's Digest, Nov 28–Dec 4: the parade grandstand permit is invisible to our own pipeline, and it runs to December 5"
---

Hi,

The parade moving to tomorrow turned up a defect in our own data, and it is the interesting item this week.

## A 31-day permit on the park's west edge that our site does not show

The parade postponement sent me looking for parade permits. There are two inside Central Park:

| Permit | What it holds | When |
|---|---|---|
| **963800** | Central Park West **sidewalks**, 65th St north through the 70s — grandstand seating | **Nov 4 → Dec 5, 5 PM** |
| **897230** | Merchants' Gate — bleacher back-of-house | Nov 27–30, 8 AM–11 PM daily |

897230 is in our data correctly, as four daily rows. **963800 is not in our data at all.** Zero event files, for a permit that has been occupying the park's entire western sidewalk for three weeks and runs another eight days.

Here is why, and it is a clean little bug. Most permits arrive as **one row per occurrence** — 897230 has four rows for its four days. But 963800 arrives as **a single row with a 31-day span**: `start_date_time 2026-11-04T08:00`, `end_date_time 2026-12-05T17:00`. Our merge writes one event file per row, so it wrote exactly one file, dated **November 4** — the start. The daily purge deletes files dated before today. On November 5 the purge took it, and the permit has been invisible ever since, while remaining fully in force.

So the rule is: **any permit filed as a single long-span row disappears from the site the day after it begins.** I checked the whole feed — 963800 is the only such permit active today, so the current blast radius is one. But it is the biggest thing on the park's edge this week, and it is exactly the class of permit most worth surfacing: long, static, and affecting a boundary rather than an event space.

The fix is to expand a single row whose `end_date` differs from its `start_date` into one file per day across the span, the same shape the per-occurrence permits already produce. I have not made that change — it alters how every long-span permit renders, and it should be your call.

## The horizon test, refined — and I nearly got it wrong again

Last week's conclusion was that the closure permits truncate at a ~31-day publishing horizon, so their end dates are unknowable. This week I ran that test and it told me the **East 106th Street lawn maintenance** had a real end date: 16 rows finishing **December 24**, three days inside the Dec 27 horizon.

That was wrong, and it is worth saying why. The series only runs **Monday to Thursday**. Its next scheduled occurrence after December 24 is **December 28** — past the horizon. Its last row sits at the edge like everything else.

The test I wrote down — "last row before the horizon means a real end date" — is unsafe for any series with a cadence. The correct test asks whether the next occurrence the series' **own pattern** predicts falls beyond the horizon:

| Permit | Cadence | Last row | Next expected | Verdict |
|---|---|---|---|---|
| 947652 E 106th maintenance | Mon–Thu | Dec 24 | Dec 28 | at horizon |
| 895600 Bethesda "Closed" | daily | Dec 27 | Dec 28 | at horizon |
| 884734 East Meadow | weekends | Dec 27 | Jan 2 | at horizon |

**So no closure has a knowable end date** — the same answer as last week, but now from a test that would actually detect one.

One thing that does have a real end date is 963800 above: because it is a single row carrying its own `end_date_time`, the December 5 date is genuine, not a horizon artifact. The dataset has two permit shapes, and only one of them gets truncated.

## One co-location worth noting, and not more than noting

**The "CPC Annual Holiday Lighting 2026" permit covers "Dana Discovery Center Lawn, Harlem Meer Picnic Area."** That is the same ground as the **"Lawn Closure – Harlem Meer"** series, which has been closed since November 20.

Same location, one a closure spanning the other's event date. Lawn protection ahead of a 30th-anniversary event is a plausible reading. It is also just two permits naming the same place, and the closure began two weeks before the event. I am recording the co-location and stopping there.

## The week

- **Sat 28, 8:30 AM — the parade.** CPW from W 77th to Columbus Circle, then Sixth Avenue. Over 1,000 extra NYPD officers. Nothing permitted inside the park; the drives are untouched. Balloons were deflated Wednesday, trucked to New Jersey and re-prepped in about 24 hours, with no public re-inflation. Macy's has not stated outright that they fly.
- **Sun 29, 9–11 AM — Colony HS Band and Choir**, Bandshell Plaza. The fourth visiting-band permit in three weeks.
- **Wed 2 – Thu 3 — Holiday Lighting**, Dana Discovery Center Lawn and Harlem Meer picnic area; the **30th Annual Holiday Lighting** itself is Thursday 5:30 PM.
- **Thu 3, 6–8 PM — opening reception, 44th Annual Wreath Interpretations** at the Arsenal; the show runs Friday 9–5.
- **Catholic League crèche display**, Grand Army Plaza sidewalks, Dec 2–4.
- **No affects_loop events anywhere in the window.**
- **Field permits: 3** for the week, from 17 last week and a September peak of 223.
- **The Great Lawn has its first permits since July** — four Little League softball bookings, all **April 2027**. Nothing before then, which is the first forward signal it is expected playable.
- **NYC Parks has recovered** from last week's hard 403 and returned 30 events against the 5 its cache was stuck on.
- **The rebuild job has now committed twice a day with a zero diff for 26 days.**

## Quick recap

- **Permit 963800** — parade grandstands on the CPW sidewalks to **Dec 5** — has **no event files**, because single-row long-span permits get one file on their start date and the purge then deletes it.
- **The refined horizon test** uses the next occurrence a series' own cadence predicts. All closures still fail it; none has a knowable end.
- **963800's Dec 5 end date is real** — single-row permits carry a true `end_date_time`.
- **Holiday Lighting and the Harlem Meer closure name the same ground.** Noted, not concluded.

Watching,
Kin
