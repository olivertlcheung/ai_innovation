# UCI club website and event crawler

This is the updated crawler, stored in the same local Git repository as ZotLife.
The original files from your download were committed first, followed by the
crawler upgrades. No GitHub account is needed to run it or inspect local history.

The new default workflow uses Python 3.9+ standard libraries only. The original
experimental API/pipeline scripts remain available and retain their own optional
third-party dependencies.

**Public calendars and newsletter archives:** see [PUBLIC_FEEDS.md](PUBLIC_FEEDS.md)
for the reusable `--collect-public-feeds` tool, optional calendar dependencies,
exact saved paths, sample results and the website import command.

## 1. Discover websites and contact links

Run from the top-level `ai_innovation` folder:

```sh
python3 -B tools/zot_event_crawl/src/crawlers/club_crawler.py --max-clubs 5
```

The crawler reads `https://zotspot.uci.edu/club_signup`, associates each listing's
`a[aria-label="Website"]` with its club ID/name, and follows the actual Load all
or Next links. It then visits the published website and a bounded number of
linked contact/about/events pages. It extracts Instagram, LinkedIn, Discord,
TikTok, email, Facebook and YouTube links found there. It also follows published
Linktree/Beacons hubs within the per-club page budget.

There are no guessed handles. Saved links retain `found_on`, link label and
collection timestamp; repeated observations retain additional page evidence.
A published link is evidence of a relationship, not a guarantee of account
ownership. LinkedIn individual profiles are marked `account_scope: individual`
and excluded from automatic event collection. Unconfirmed profiles remain marked
as such. Mail links are collected as contacts; no messages are sent.

Outputs, relative to the crawler folder:

| Path | Contents |
| --- | --- |
| `data/clubs/club_sources.json` | Club IDs/names, official Website links, discovered contact links, provenance and page statuses |
| `data/clubs/club_discovery_report.json` | Directory pages, discovered/processed counts and incomplete work |

`--max-clubs 5` enriches only five groups, while retaining all discovered directory
entries with `not_started` status for the remainder. Omit this flag to process
all discovered groups. This can take a long time. `--pages-per-club 3` and
`--max-directory-pages 3` set traversal limits; `--delay 2` sets a minimum delay.
Rerunning refreshes the snapshot; this version does not resume an interrupted run.
Checkpoints save progress after each group but are not a resume cache.

The old API mode is retained with `--legacy-api`. The old HTML extractor no longer
generates handles by modifying club names. The older handle files included in
`data/clubs/` are preserved input files, not verified accounts, and the new
crawler does not use them.

## 2. Collect event data or save raw text

```sh
python3 -B tools/zot_event_crawl/src/crawlers/club_crawler.py --collect-events --max-clubs 5 --pages-per-club 6 --include-social
```

Official website pages are visited before optional social pages. The collector
extracts explicit schema.org Event JSON-LD into the same unified event fields as
ZotSpot: title, source URL, dates, timezone, location, organizer, tags and RSVP URL.
Unknown properties remain empty/null. Invalid, incomplete or cancelled structured
events remain review candidates.

When no structured event can be extracted, readable HTML text, page title and
available description/caption metadata are preserved for later parsing. Ordinary
page text and post publication dates are never turned into event dates by guess.
Image-only flyers need a future OCR stage. This older collector does not implement
JavaScript-only captions, recurring session inference, ICS parsing or free-text
event extraction. Use the separate public-feed workflow for explicit ICS schedules.

`--include-social` attempts public social landing pages and a limited number of
Instagram post links actually present in those pages. It does not log in, bypass
blocks, enter Discord servers or use private messages. Public HTTP responses may
not contain Instagram captions at all. Blocked pages produce a status record;
they do not count as successful post collection. Without the flag, social links
are discovered but not visited by the event collector.

| Path | Contents |
| --- | --- |
| `data/output/club_events.json` | Explicitly structured events, compatible with the website exporter |
| `data/output/club_raw_text.json` | Readable page text and metadata, including failed/blocked records |
| `data/output/club_event_candidates.json` | Incomplete, invalid or cancelled structured events for review |
| `data/output/club_event_crawl_report.json` | Per-group counts and queued URLs left by page limits |

Files are snapshots replaced on each run. Raw records retain club ID/name, source
URL, platform, fetch timestamp, status and a separate publication timestamp when
provided. Generated snapshots stay outside Git tracking but are included in the
complete ZIP. Original input snapshots from your downloaded data folder are also
included. Repeated redirects to the same final URL are deduplicated on new runs.

The client obeys robots rules and crawl delays, uses bounded request sizes and
page counts, records login/rate-limit/challenge failures, and rejects non-public
HTTP destinations. It does not retry around social access controls.

## Live test included

A bounded live test discovered **1,000 groups** and inspected **three** groups'
websites (997 remain unprocessed). Two sample groups had published Instagram
links. One ZotSpot club website required login. Public Instagram/LinkedIn
attempts were robots-blocked. The collection test saved **nine raw attempt
records** and **zero structured events**, which is why `club_events.json` is an
empty array. One redirect duplicate in that first sample led to an additional
regression fix for future runs. The report retains the original live observations.
There is no claim that every club website or social post was crawled.

## 3. Publish reviewed events to ZotLife

From the top-level website folder:

```sh
python3 -B tools/zot_event_crawl/scripts/merge_event_feeds.py --inputs tools/zot_event_crawl/data/output/unified_events.json tools/zot_event_crawl/data/output/club_events.json --output tools/zot_event_crawl/data/output/combined_events.json
python3 -B scripts/sync_events.py tools/zot_event_crawl/data/output/combined_events.json
```

Review `club_events.json` before publishing. Merge only unified event arrays, not
raw text or candidates. Records deduplicate by `(source, id)`; events appearing
in both ZotSpot and a club site need later cross-source duplicate review. Original
inputs are preserved. The included combined snapshot still contains 295 ZotSpot
events because the bounded live sample yielded no additional structured events.

## Tests

```sh
python3 -B -m unittest discover -s tools/zot_event_crawl/tests -v
```

Tests cover link association, provenance, load-all traversal, domain lookalikes,
robots blocks, blocked social collection, structured event extraction, date-only
schedules, cancelled/invalid candidates, raw-text fallback and website-export
compatibility. The existing `club_crawler.py` entry point is also tested without
requiring its legacy optional packages.
