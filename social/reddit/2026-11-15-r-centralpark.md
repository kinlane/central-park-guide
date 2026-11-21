---
sub: r/CentralPark
drafted: 2026-11-15
covers: 2026-11-15 to 2026-11-21
status: DO NOT POST AS WRITTEN — two claims in it are false (see retractions below)
link_included: false
retractions:
  - claim: "the loop is clear the whole week" (in the title and a body section)
    verdict: FALSE as of 2026-11-21
    why: >
      The Central Park Turkey Trot (permit 906222) was filed after the Nov 15
      pull and runs today, Sat Nov 21, 10-11am across Bandshell Plaza, Center
      Drive, Center Loop, East Drive and the cross drives. It was not in the
      data when the post was written, which is exactly the hazard the post
      itself describes two paragraphs earlier about the Festival Dei Cinque
      Colori. The claim was true against the data and is not true about the
      park.
  - claim: "seven permits ... all ending within a day of each other ... something is planned for the park around December 14"
    verdict: FALSE — artifact of the data source
    why: >
      The NYC permit dataset expands a recurring permit into one row per
      occurrence only ~31 days ahead of the query. Querying event_id=895600
      with no date filter returns exactly 31 rows, Nov 21 - Dec 21. Of 68
      permits in the Nov 21 pull dated after Dec 21, all 68 have exactly one
      row. The "shared end date" is the materialization boundary, and every
      reported move of it (Dec 6, 8, 13, 14, 20) is the pull date plus ~29
      days. These closures do not end in December; their end date is not
      visible in this dataset at all. The post asks readers to go look for
      posted notices about a December event there is no evidence for — that
      ask must not go out.
phase: 1 complete — see note
week: 5 (Phase 1's four weeks ended with the Nov 8 post)
note: >
  PHASE 1 IS OVER. The plan (.claude/skills/reddit-posting-plan.md) specifies
  four weekly posts to r/CentralPark and then a review before any sub is added.
  Weeks 1-4 are Oct 16, Oct 25, Oct 31 and Nov 8. This is week 5, drafted on
  request, and it continues the cadence past the point the plan said to stop
  and look. The review cannot be done from this repo: all four metrics blocks
  are empty, so the Phase 1 success bar — "any week with a substantive comment
  thread" — has no data behind it either way. Reddit is unreadable from this
  environment; those numbers have to be entered by hand.

  CORRECTION CARRIED: the Nov 8 draft said the Conservancy gala holds Rumsey
  "Fri 13 + Sat 14 ... both days", and the Nov 6 and Nov 8 emails said the
  permit had grown from one day to two to three. All of that was wrong. The
  permit has read Nov 13-21 — nine days — in every pull since Oct 31. What
  moved was the seven-day reporting window sliding across a fixed permit. If
  the Nov 8 post went up with the "two days" line in it, that line is wrong.
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

What's on in the park this week (Nov 15–21) — seven days without a drop of rain, the loop is clear the whole week, and a seventh closure permit joins the pile that all ends on the same day

# BODY

Weekly rundown from the NYC permit feed plus the Conservancy and Parks
calendars. This is an unusually good week and an unusually interesting one in
the permit record.

**The forecast, which is the headline this week**

Seven consecutive days with a **0% chance of rain** and highs going up every
single day:

Sun 50 → Mon 54 → Tue 58 → Wed 62 → Thu 64 → **Fri 65** → Sat 63

Normal for this stretch of November is about 52. Thursday and Friday are
roughly 13 degrees above that, with wind under 7 mph the whole way. If you have
been putting something off until the weather is right, it is right.

**And the loop is completely clear, all seven days**

No race, no walk, no closure on East, West or Center Drive at any point this
week. After the marathon envelope, the Nov 7 elephant run and yesterday's
Alzheimer's walk, this is the first clean week on the drives in a while.

Then it ends: **Race to Deliver 4M is next Sunday, Nov 22, roughly 8–10am on the
drives.** If you want an uninterrupted long run or ride, it is this week, not
next weekend.

**Today, Sun 15** — 50°F, mostly sunny

* **Festival Dei Cinque Colori**, Bandshell Plaza and Dead Road, 11am–2pm. Worth
  calling out *how* this one got here: it was **not in the permit feed when I
  pulled yesterday morning**. It was filed sometime in the last 24 hours, for
  today. So if you check the city calendar midweek and see nothing, that is not
  the same as nothing happening.
* **Great Central Park Hike**, 10am from the Dana Discovery Center — the
  Conservancy's full end-to-end walk.
* **World Day of Remembrance for Road Traffic Victims**, Dana Discovery Center
  Plaza, 12–2pm.
* **International Folkdancers**, King Jagiello Plaza, 11am–3pm. Open circle.
* Birding Bob at the Boathouse 7:30am. East Meadow closed.

**Mon 16 — a free high school jazz set, 10:30am**

**Carmel High School Jazz Band at the Bandshell, 10:30–11am.** Half an hour,
free, and nobody knows about these unless they read the permit list. There are
two or three a season. 54°F and sunny.

Birding Bob at Strawberry Fields, 8:30am. The East 106th St lawn maintenance
starts today and runs Mon–Thu.

**Tue 17 — 58°F and nothing booked**

Not a single public event anywhere in the park, no wind, and the warmest day so
far. Quietest day of the week by a wide margin.

**Wed 18 — the Conservancy gala, and nine days of permit for one evening**

The **Central Park Conservancy's Annual Gala ("Studio 72") is 7pm at Rumsey
Playfield.** Ticketed fundraiser for the organisation that actually maintains
the park — not a public event.

The permit is the interesting part. **It holds Rumsey Playfield and Bandshell
Plaza from Nov 13 to Nov 21, 9am to midnight, every day — nine days for one
evening's party.** That is the whole SummerStage footprint out for over a week,
and it is almost all load-in and load-out.

*A correction to last week's post, while I am here.* I wrote that this permit
ran "Fri 13 + Sat 14, both days," and in a couple of earlier posts I described
it as a permit that kept growing — one day, then two, then three. **That was
wrong.** It has been a nine-day permit since at least Oct 31 and never changed.
What changed was the seven-day window I write these posts from, sliding across
a fixed permit and showing me a different slice each week. I reported the slice
as the whole thing and then built a little theory on top of it. The permit feed
was not moving; I was.

**Thu 19 — Love at First Spin, 12–4pm**

Music discovery session at the Bandshell, noon to 4, on a 64°F afternoon.
Birding Bob at the Boathouse 8:30am.

**Fri 20 — 65°F, the warmest day**

Birding Bob at the **Conservatory Garden**, 8:30am — the best stop in his
rotation, on the best morning of the week. Iconic Views tour 2pm.

Three lawn closures begin today: Swedish Cottage, E 96th St playground, and
Harlem Meer picnic area.

**Sat 21 — busy, and the park is full of engagement photos**

33 permits, the fullest day of the week. **Falling for Nature Hike**, 1–2:30pm
from W 81st and CPW, free with the Urban Park Rangers. Great Central Park Hike
10am. Birding Bob at the Boathouse 7:30am.

Also **26 private bookings across the week** — celebrations, picnics, small
weddings and proposals — clustered at Bow Bridge, Cop Cot, Ladies' Pavilion,
Wagner Cove, Cherry Hill and Belvedere Castle Terrace. Mid-November weekend
afternoons at those six spots are booked solid. Not a closure, just a reason
you will be walking through somebody's photos.

**Now the permit thing: there are seven of them, and they all end at once**

I have been tracking a cluster of multi-week closures for a month. It keeps
getting bigger and the end date keeps moving, and **every one of them moves
together.**

Where it stands today:

* Bethesda Terrace and Fountain — "Closed" — Nov 15 → **Dec 14**
* Bethesda Terrace and Fountain — "Central Park Closure" — Nov 19 → **Dec 14**
* Swedish Cottage lawn — Nov 20 → **Dec 14**
* E 96th St playground lawn — Nov 20 → **Dec 14**
* **Harlem Meer picnic area — Nov 20 → Dec 14 (new this week)**
* E 106th St lawn maintenance — Nov 16 → **Dec 14**
* East Meadow — Nov 15 → **Dec 13** (weekends only, so Dec 13 is the last day
  its own schedule allows)

**Seven permits. Six locations. Two different titles on the same spot. All of
them ending within a day of each other.**

And the date has now moved four times, as a group: **Dec 6 → Dec 8 → Dec 13 →
Dec 14.** The East 106th maintenance briefly broke away to Dec 10 and has
rejoined. Harlem Meer was filed into the cluster this week, already carrying
the shared end date.

Separate permits, at separate locations, under different titles, extending in
lockstep four times running, is a scheduling decision. **Something is planned
for the park around December 14.** I still have no idea what, and I would
rather say that than guess again — I guessed wrong about the gala above.

If anyone has seen a physical notice posted at Bethesda, the Swedish Cottage,
Harlem Meer or the E 96th playground, I would genuinely like to know what it
says. That is the one source I cannot reach from a data feed.

**Odds and ends**

* **Great Lawn: still zero permits.** Seventeen weeks now, with one picnic on
  Nov 7 breaking the run. That booking proved it was never administratively
  closed, which is what I had been assuming — and nothing has been on it since.
* **55 field permits this week**, 28 at North Meadow. September's peak was 223.
