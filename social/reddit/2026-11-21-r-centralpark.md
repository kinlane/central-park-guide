---
sub: r/CentralPark
drafted: 2026-11-21
covers: 2026-11-22 to 2026-11-28
status: draft — not yet posted
link_included: false
phase: 1 complete (ended with the Nov 8 post); this is week 6
week: 6
note: >
  Supersedes the 2026-11-15 draft, which is marked DO NOT POST — it carried
  two false claims (the loop was not clear that week, and the December closure
  cluster is an artifact). This post retracts the closure cluster publicly,
  which is the right venue for it: the Nov 8 post that went up carried the
  cluster claim and asked readers to go hunt for posted notices.

  PHASE 1 REVIEW IS STILL OWED and still cannot be run from this repo — all
  five prior drafts have empty metrics blocks, so the success bar ("any week
  with a substantive comment thread") has no data behind it. Reddit is
  unreadable from the pipeline environment; those numbers are hand-entered.
# Metrics — fill in from Reddit; this environment cannot read reddit.com.
metrics:
  checked_on:
  upvotes:
  comments:
  substantive_thread:   # true/false — THE success bar for Phase 1
  mod_action:           # none / removed / flaired
  notes:
---

# TITLE

What's on in the park this week (Nov 22–28) — two Macy's parade bands rehearse free at the Bandshell, and I have to retract the December closure thing I posted about

# BODY

Weekly rundown from the NYC permit feed plus the Conservancy calendar. One
genuinely good find this week, and one correction I owe this sub.

**First, the correction, because I asked you all to go looking**

In an earlier post I wrote that a cluster of long park closures — both Bethesda
permits, the Swedish Cottage lawn, the E 96th playground lawn, East Meadow, the
E 106th maintenance — all ended on the same day in December, that the date kept
moving as a group, and that this looked like something being scheduled. I asked
whether anyone had seen a notice posted at those spots.

**Please don't bother. I was wrong, and it was my mistake, not the city's.**

The permit dataset stores one row per occurrence, and it only generates a
recurring permit's rows **about 31 days ahead of whenever you query it.** Ask it
for one permit with no date filter:

    ?event_id=895600        (Bethesda Terrace, titled just "Closed")
    -> exactly 31 rows, 2026-11-21 through 2026-12-21

Same for every other permit in my "cluster." And the clincher: of the 68 permits
in this week's pull dated after Dec 21, **every single one has exactly one row.**
Inside the window, nine permits have more than five.

So they don't share an end date. They share *the edge of the data.* And every
time I reported the date "moving," it was the calendar moving:

* pulled Nov 6 → "they all end Dec 6"
* pulled Nov 8 → "moved to Dec 8, together"
* pulled Nov 14 → "moved again, Dec 13"
* pulled Nov 21 → Dec 20

Always the pull date plus about 29 days. The one series I said "broke away and
rejoined" was a weekday-only permit hitting the same wall on a different day.

What's actually true is duller: **Bethesda Terrace, the Swedish Cottage lawn, the
E 96th playground lawn and Harlem Meer are closed every day, and this dataset
cannot tell you when they reopen.** That's it. If anyone does know when Bethesda
is due back, I'd still like to hear it — but from a notice or a person, not from
me reading tea leaves in a feed.

**Now the good part: two Macy's parade bands are rehearsing in the park, free**

* **Tue 24, 9–10am, Bandshell Plaza — Pearland High School band** (Pearland,
  Texas). Picked from 100+ applicants to march in Thursday's parade.
* **Wed 25, 10am–3pm, Bandshell Plaza — the UConn marching band.** Five hours.

Both are in the **100th** Macy's Thanksgiving Day Parade on Thursday, and both
have permits to rehearse at the Bandshell beforehand. There's no listing for
this anywhere — it's a line on a permit list. A full competition marching band
in the open air on a sunny 48° Tuesday morning, for nothing, is about the best
thing this feed turns up.

**Sun 22, 8–10am — Race to Deliver 4M**

33rd running, four miles on the drives, benefiting God's Love We Deliver. The
permit holds the 72nd and 102nd St cross drives and the Center Loop **until
11am**, so the drives are not yours until then. 62°F and rain likely, with heavy
rain overnight.

Also Sunday: **Seneca Village Tour, 2pm from Mariners' Gate (W 85th)** — the
Conservancy's walk on the community of African-American property owners that was
displaced to build the park. Runs again Saturday at 2. Easily the most
worthwhile hour in the park right now. **International Folkdancers** at King
Jagiello Plaza 11–3, open circle.

**Mon 23 — 65°F and not one event booked anywhere**

Showers clear, it hits 65, and the park has nothing permitted in it at all.
**It's the last mild day in the forecast** — Tuesday is 48, and it stays there.

**Thu 26 — Thanksgiving, and the park's whole west edge is the parade**

The 100th parade steps off at **W 77th and CPW at 8:30am** and runs south to
Columbus Circle. Nothing is permitted inside the park, but every west-side
entrance from 77th down is inside the route. East side or north end if you want
the park that morning.

Forecast is 50°F, 72% rain, **wind around 21 mph.** The balloons get grounded at
23 mph sustained or 34 gusting, so this is going to be a morning-of decision.
Not a prediction — just the number that decides it.

**The rest**

* **Fri 27:** nothing booked, 54°F, chance of light rain.
* **Sat 28:** Iconic Views tour 10am, Seneca Village 2pm, frisbee at North
  Meadow 9–5. East Meadow closed.
* **Field permits are down to 17** this week, nine at North Meadow. September
  peak was 223. Season's done.
* **Great Lawn: still zero permits**, with one picnic on Nov 7 the only booking
  since July.
