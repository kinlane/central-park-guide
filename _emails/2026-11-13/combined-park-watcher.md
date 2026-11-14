---
week_of: 2026-11-13
sent_date: 2026-11-13
covers: 2026-11-14 to 2026-11-20
format: combined
audience: park watchers
personas: [park-watcher]
subject: "Central Park Watcher's Digest, Nov 14–20: I had the gala permit wrong, and six closures now converge on December 13"
---

Hi,

Two things this week, and the first is a correction to something I told you twice.

## I was wrong about the gala permit, and wrong in an instructive way

Last Sunday I wrote that the CPC Annual Fall-Winter Gala permit "was a one-day permit when it first appeared on October 30, two days in Friday's pull, and is now three days." I presented that as the week's most interesting finding, and built a general claim on it: that permits expand after filing, and that you can only know a real footprint by pulling repeatedly and diffing.

**The permit never changed.** I went back through the repository history this morning. The gala permit has read **November 13 to November 21 — nine consecutive days — in every pull since at least October 30.** Here is what each commit's event files actually held:

| Pull | Gala permit span on file |
|---|---|
| Oct 31 | Nov 13–21 (9 days) |
| Nov 2 | Nov 13–21 (9 days) |
| Nov 6 | Nov 13–21 (9 days) |
| Nov 14 | Nov 14–21 (8 days — Nov 13 purged as past) |

What moved was **my seven-day window**, not the permit. The Nov 6 edition covered Nov 7–13 and caught exactly one gala day. The Nov 8 edition covered Nov 9–15 and caught three. I read the slice inside each window and reported it as the permit's full span, then narrated the difference between two slices as growth.

This is worth naming precisely because the general claim sounded right. Permits *do* change after filing — the marathon load-out envelope genuinely did. But the gala was my headline evidence, and the gala evidence was an artifact of my own reporting window. **A difference between two windows is not a change in the world.** I have changed how I read spans: the full permit series now gets measured before anything about it gets written, regardless of what the week's window shows.

## Six closures converge on December 13 — and one does not

The convergence I flagged as a guess two weeks ago and a pattern last week is now the clearest thing in the data. Every closure series currently on file, with its true full span:

| Series | Location | Span | Days |
|---|---|---|---|
| Closed (permit 895600) | Bethesda Fountain Terrace | Nov 14 → **Dec 13** | 30, consecutive |
| Central Park Closure (987031) | Bethesda Fountain Terrace | Nov 19 → **Dec 13** | 25, consecutive |
| Lawn Closure | Swedish Cottage Lawn | Nov 20 → **Dec 13** | 24 |
| Lawn Closure | E 96th St Playground Lawn | Nov 20 → **Dec 13** | 24 |
| East Meadow Closure | East Meadow Picnic Zone | Nov 14 → **Dec 13** | 10, **weekends only** |
| Lawn Maintenance | East 106th St Lawn | Nov 16 → **Dec 10** | 16, weekdays |

**Five of six share December 13 exactly.** That date has now moved twice while I have been watching it: it read December 6 in the Nov 6 pull, December 8 in the Nov 8 pull, and December 13 now — and each time, the whole group moved together in a single filing. That part is real and I have checked it against the history the same way I checked the gala.

Two new details this week:

- **East Meadow has joined the group**, and it is **weekends only** — Nov 14, 15, 21, 22, 28, 29, Dec 5, 6, 12, 13. Ten Saturdays and Sundays, ending on the shared date. A different shape from the rest, same terminus.
- **The East 106th Street lawn maintenance broke away.** It ends **December 10**, three days early, where last week it was in lockstep. First member of the group to diverge.

Six permits at five locations do not share an end date by coincidence, and they do not all move from December 6 to December 8 to December 13 together by coincidence either. Something is scheduled for mid-December. I still do not know what, and I am not going to guess at it again in print.

## A permit filed six days before the event

**Walk to End Alzheimer's - Manhattan**, permit 893015, **today 8 AM–1 PM**, across Bandshell Plaza, the Lower Loop, the Center Loop and Dead Road North.

**It was not in the city's feed when I pulled on November 8.** It appeared in this morning's pull. A large charity walk closing the lower loop for five hours was filed — or at least published — inside the six days before it happened, which means last Sunday's edition described today as a quiet Saturday in good faith and was wrong by the time anyone read it.

This is the second time in eight days that the loop has been the thing we got wrong, and the two causes are different and both worth separating:

1. **Nov 7, Saving the Elephants Run** — the permit was in the feed on time. Our tagging missed it, because `Upper Loop` is not in the code's list of loop place names.
2. **Nov 14, Walk to End Alzheimer's** — our tagging worked correctly. The permit simply was not there to tag.

Only the first is fixable by us. Today's permit also named **`Center Loop`**, which is likewise absent from the loop-names list — this walk was flagged only because it happened to also name `Lower Loop`. A permit naming Center Loop alone would go through unflagged, exactly as the Upper Loop one did. Both names are queued to be added.

## The rest of the week

- **Nothing one-off is booked Monday through Thursday** that touches your interests — the park is genuinely empty midweek.
- **St. Martin's Parade**, Saturday 3:15–5 PM at Summit Rock. A lantern procession, the only public gathering of real size this week besides the walk.
- **Field permits: 39**, 27 at North Meadow. Down from 56 last week — the seasonal taper.
- **The Great Lawn remains at zero.** I will keep saying so without reading anything into it; last week's picnic settled that one booking proves it was never administratively closed, and nothing more.
- **Coming Sunday, November 22: Race to Deliver 4M**, 8–10 AM on the drives — from our curated charity-walk data, not the city feed, which is why it is reliable this far out.

## Quick recap

- **The gala permit never grew.** Nine days, Nov 13–21, unchanged since October 30. My window moved and I reported it as the permit moving.
- **Six closure series, five ending December 13** — a date that has moved Dec 6 → Dec 8 → Dec 13 with the whole group each time.
- **East Meadow joined the group, weekends only.** The E 106th lawn maintenance left it, ending Dec 10.
- **Today's loop closure was filed within six days of the event** and missed last Sunday's edition entirely.
- **`Center Loop` is a second gap in our loop-name list**, alongside `Upper Loop`.

Watching,
Kin
