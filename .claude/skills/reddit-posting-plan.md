# Reddit posting plan — Central Park Guide

A phased plan for posting persona content to Reddit alongside the weekly email.
**Phase 1 is approved and ready. Everything after Phase 1 is gated on a human
reading that subreddit's rules first.**

## What I could not verify, and why it matters

I could not read a single subreddit's rules from the pipeline environment.
Every route is blocked:

| Attempt | Result |
|---|---|
| `curl reddit.com/r/CentralPark/about.json` (browser UA) | HTTP 403 |
| WebFetch `www.reddit.com` | blocked by the harness |
| WebFetch `old.reddit.com` | blocked by the harness |
| Redlib / applefritter mirrors | DNS failure / HTTP 502 |
| Web search for the sub's rules | returned only generic Reddit-wide advice |

So **the subreddit names, sizes and fits below are from model knowledge with a
May 2026 cutoff, not from live data.** Sub names in the NYC space churn, and
rules change whenever a mod team decides they do. Treat this document as a
ranked list of candidates, never as a cleared list.

That is not purely a limitation. Subreddit rules have to be read at posting time
anyway — a rule verified six weeks ago is not a rule — so rule-reading belongs
to the human step regardless of what automation could manage.

## The constraint that shapes the whole plan

Reddit's norm is roughly **90/10**: nine parts genuine participation to one part
your own content. Most NYC subs are stricter than that, and r/nyc and r/AskNYC
are among the strictest.

A weekly post per persona is ten posts a week across heavily overlapping
audiences. That is the exact shape Reddit's spam heuristics are built to catch,
and the penalty is not a removed post — it is **centralpark.guide getting
sitewide-filtered**, after which the domain stops working in ordinary comments
too. That would cost more than the posting earns.

**So the plan is not "the email, syndicated." It is a small number of posts that
are worth reading on their own.**

## The asset that makes this work: loop closures

The most Reddit-native thing this project owns is not the digest. It is the
closure calendar.

> East Drive is held midnight to 8 PM Wednesday and Thursday, under a permit
> titled only "Party."

Nobody else aggregates that. It sits in the NYC permit feed under uninformative
titles, the city does not surface it, and it took three pipeline fixes this
month to stop our own tooling from hiding it. A runner or cyclist reading that
post is better off for it, which is the only durable test of whether a post
belongs on Reddit.

Three or four closure posts a month will outperform forty digest posts, and
cannot be read as spam.

## FINDING 2026-10-16: it was filtered with no link in it

The week-1 post was **caught by filters on the first attempt** and went up on a
repost. That is worth more than a clean post would have been, because of what it
rules out.

**The post contained no link at all.** No URL to centralpark.guide, no
newsletter mention, nothing promotional. So whatever caught it, it was **not a
self-promotion filter.** The plan's whole opening argument — go link-free to stay
clear of promo rules — was correct as far as it went, and irrelevant to what
actually happened.

What is left as the likely cause, in rough order:

1. **Account standing in the sub.** Reddit's own spam filter and most
   AutoModerator configs hold a first post from an account with no comment
   history in that subreddit. This is the single most common explanation and it
   fits perfectly: our account had never participated there.
2. **Account age or karma thresholds** set by the mod team.
3. A keyword or formatting rule we cannot see.

I cannot diagnose it further from here — Reddit is unreadable from this
environment, so I cannot tell whether the first post was removed by
AutoModerator, held in the mod queue, or shadow-filtered sitewide. **The only way
to know is to ask the mods**, and that is now the highest-value next action.

### What this changes

The plan treated "read the rules" as the gate for every new sub. That is
necessary but not sufficient. **Standing is the real gate, and it applies even to
our own natural hub.**

So the revised sequence for any sub, r/CentralPark included:

1. **Comment first, post second.** Participate in a few existing threads before
   posting anything. This is what the plan already said about r/AskNYC — it turns
   out to be the general rule, not a special case for the strict subs.
2. **Message the mods once**, introducing the weekly roundup and asking whether
   they want it. A mod who knows what you are doing can whitelist the account,
   and that one message is worth more than any amount of careful formatting.
3. Only then post on a cadence.

### Immediate housekeeping

Two near-identical posts now exist, minutes apart. If the first is only *held*
rather than removed, a mod may approve it later and leave a duplicate — which is
itself a spam signal. **Delete the first attempt, or ask a mod to clear it.**

And note for the month-end review: week 1 is a post that needed two attempts.
That is the honest baseline, not a clean start.

## Phase 1 — r/CentralPark (DECIDED 2026-10-10)

Our own natural hub. On-topic by definition, small enough that volume is not a
nuisance, and no self-promotion tension because park content *is* the subject.

**First post: Friday 2026-10-16.** Then weekly for a month — Oct 16, Oct 23,
Oct 30, Nov 6 — and review before anything else is added.

- **Cadence:** one post, Friday, alongside the email drop.
- **Content:** the week's genuinely notable items — closures, a named race, a
  one-off like City of Forest Day or the film festival. Not the full digest.
- **Format:** write the post in the comment box as a post, with the link at the
  bottom if at all. A post that only makes sense if you click out is the kind
  Reddit punishes.
- **What to record each week** (so the month-end review has something to read):
  upvotes, comment count, whether any comment asked a follow-up question, and
  whether the post was removed or flaired by a mod.
- **Decide the success bar now, before the data exists.** A sub this size will
  not produce big numbers. Suggested bar: *any week with a substantive comment
  thread* counts as working. Upvote count alone does not.

### Posting log

| Week | Date | Post | Metrics |
|---|---|---|---|
| 1 of 4 | 2026-10-16 | [Week 1](https://www.reddit.com/r/CentralPark/comments/1x7uzrb/whats_on_in_the_park_this_week_oct_1723_and/) — **filtered on first attempt**, live on repost | pending — see `social/reddit/2026-10-16-r-centralpark.md` |
| 2 of 4 | 2026-10-23 | — | — |
| 3 of 4 | 2026-10-30 | — | — |
| 4 of 4 | 2026-11-06 | — | — |

Drafts and their metrics live in `social/reddit/<date>-r-<sub>.md`. **Reddit cannot
be read from the pipeline environment** (403 unauthenticated, WebFetch blocked on
both reddit.com and old.reddit.com), so every metric in those files is entered by
hand. An empty metrics block at month-end is a missing data point, not a zero.

### Week-one checklist

Before the Oct 16 post, run the rules checklist at the bottom of this file
against r/CentralPark. It is our own natural home, but nobody has read its
rules yet — see the verification gap above.

## Phase 2 — the two subs that actually want the data

Only after Phase 1 has run four weeks.

| Sub | Persona | Why | Gate |
|---|---|---|---|
| r/RunNYC | runner | Closure alerts are a service here. Marathon season is live. | **Verify the sub exists and read its rules.** Name unconfirmed. |
| r/NYCbike | cyclist | Drive closures matter more to cyclists than anyone. | **Verify the sub exists and read its rules.** Name unconfirmed. |

Post **closure alerts only** here — not the digest, not every week. Only when
there is a real closure, which the pipeline already flags as `affects_loop`.

## Phase 3 — niche subs, one at a time

Add at most one per month, each after reading its rules.

| Sub | Persona | Notes |
|---|---|---|
| r/birding, r/whatsthisbird | nature-lover | Most engaged niche on the list. Image-led, not link-led. |
| r/urbanplanning | park-watcher | The permit-data findings are genuine content here. Post the finding, not the newsletter. |
| r/Broadway, r/theatre | theater-fan | Delacorte / Shakespeare only. Dark most of the year. |
| r/Parenting, r/UpperWestSide, r/UpperEastSide | family | Neighborhood subs beat the big parenting subs. |
| r/running, r/AdvancedRunning, r/Marathon_Training | runner | Large and general; only for genuinely notable race news. |

## Phase 3.5 — measure r/AskNYC before engaging it (DECIDED 2026-10-10)

Before posting or answering anything in r/AskNYC, measure whether our data
actually answers what people ask there. This is demand measurement for the
dataset, not promotion, and it runs independently of the posting phases.

### The question

Of the questions asked in r/AskNYC, what share could be answered from the
event data we already hold?

### Method

1. Pull questions over a fixed window — a month is enough, and it must be a
   calendar window chosen in advance, not "until the number looks good."
2. Classify every question into exactly one bucket:
   - **answerable** — our event data answers it as it stands
   - **park-adjacent** — about Central Park, but needs something we do not hold
   - **unrelated** — neither
3. For each *answerable* question, record **which field answered it**: closure,
   event schedule, venue, recurring programme, seasonal timing.
4. Report the rate and the field breakdown.

### Set the bar before measuring

r/AskNYC is a whole-city sub, so most of its traffic will be apartments,
restaurants and transit. **Expect a low single-digit percentage.** That is not a
failure — the useful finding is the *field breakdown*, because if the answerable
questions cluster in one field (closures, most likely), that tells us what the
dataset is actually for, which is worth more than the headline rate.

Agreeing the bar now is the point. A rate judged after the fact is a rate judged
to taste.

### Prerequisite: Reddit API credentials

**This cannot be run until credentials exist.** Unauthenticated Reddit access
was removed in 2023 and the pipeline environment confirms it — the JSON API
returns 403 even with a browser user agent.

The supported route is a registered OAuth app:

1. Register a **script** app at `reddit.com/prefs/apps`.
2. Put `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` in the repo `.env`, next to
   `FASTMAIL_CENTRAL_PARK_GUIDE_KEY` and the AWS keys.
3. Authenticate for an app-only token and read `/r/AskNYC/new`.

Pushshift is not an option — it was restricted to moderators in 2023.

Nothing about this step should be attempted by scraping. A scraper would be
blocked, and getting blocked on reads is the same ban surface that would take
the posting plan down with it.

## Phase 4 — the general NYC subs (hardest, last)

r/nyc, r/Manhattan, r/AskNYC.

**r/AskNYC should be answered, not posted to.** Someone asks where to walk, or
whether the loop is closed this weekend — answering well, without a link, builds
the standing that eventually makes a post acceptable. This is the slowest and
highest-value channel and it should not be rushed.

## Not worth it

- **wellness-seeker** — r/yoga and r/Meditation are promo-hostile and not local.
  No path in.
- **sports-fan** — permit-league softball has no Reddit audience. Skip.
- **music-fan** — depends entirely on SummerStage, which is dark until May 2027.
  Revisit in spring.

## Rules checklist — run before the first post in any new sub

1. Read the sidebar rules **and** the wiki, in full.
2. Search the sub for "newsletter", "blog", "self promotion" — mod replies in
   old threads are usually blunter than the written rule.
3. Check whether there is a weekly/monthly self-promo thread. If so, that is
   where we go, permanently.
4. Check the last 30 days of posts: is anything link-led upvoted, or is it all
   images and text?
5. If the rules are ambiguous, **message the mods before posting.** A yes from a
   mod is worth more than a careful reading.
6. Record the outcome in this file so the next pass does not re-litigate it.

## Open question worth deciding before Phase 3

Four personas exist in `_personas/` with **no subscribers**: `photographer`,
`first-timer`, `history-buff`, `picnicker`. Two of them are better Reddit fits
than half the active list:

- **photographer** — Reddit rewards images far more than text. r/itookapicture,
  r/photocritique and the NYC photo subs would take park photography on its
  merits, with no promotion problem at all.
- **first-timer** — maps directly onto what people actually ask in r/AskNYC.

If Reddit is the growth channel, these two deserve attention ahead of
wellness-seeker and sports-fan, which have nowhere to go.

## Cadence summary

| Phase | Subs | Posts/week | Starts |
|---|---|---|---|
| 1 | r/CentralPark | 1 | **Fri 2026-10-16**, weekly to Nov 6 |
| 2 | + r/RunNYC, r/NYCbike | 1–2 | after 4 weeks of Phase 1, rules read |
| 3 | + one niche sub/month | 2–3 | after Phase 2 settles |
| 3.5 | r/AskNYC *measurement only* | 0 | needs Reddit API credentials |
| 4 | general NYC subs | answers, not posts | last, slowly |

Ceiling is **three or four posts a week across everything** — not ten.
