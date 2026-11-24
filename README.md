# ZotLife — UCI events from your crawler

Repository: https://github.com/AI-Innovation-2026-Fall-Group-8/ai_innovation

For the new public calendar/newsletter tools and the command that imports their
valid events into this website, see [Public feeds](tools/zot_event_crawl/PUBLIC_FEEDS.md).

The website loads `data/output/unified_events.json` over HTTP on page load.
Events are not embedded in HTML. Your crawler remains a separate collection tool;
its original folder has not been changed. The included feed contains 295 events
from your supplied snapshot, whose records were updated on November 10, 2026.

## Run locally

From this repository directory:

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

Open http://127.0.0.1:8765/ in a browser. The root page opens the original prototype
filename. Double-clicking the HTML file uses `file://`, which cannot reliably fetch
JSON; the page explains that a web server is needed.

## Refresh after a crawl

1. Run your existing crawler/pipeline to produce its unified output. This website
   does not run crawlers in visitors' browsers or schedule collection jobs.
2. From this repository directory, export the new snapshot:

   ```sh
   python3 scripts/sync_events.py "/Users/zhaohuilinAnne/Downloads/zot_event_crawl-main/data/output/unified_events.json"
   ```

   The command writes the website's `data/output/unified_events.json`. It can also
   read any other path with the same unified schema. The supplied raw ZotSpot
   `events.json` is also supported, including its `start_date`, `category`,
   `group_name` and `url` aliases. Prefer the deduplicated unified output; do not
   combine overlapping snapshots or test files.
3. Refresh the local browser. No HTML edits or build step are required.
4. Review and commit the updated public feed:

   ```sh
   git diff --stat
   git add data/output/unified_events.json
   git commit -m "Refresh UCI event snapshot"
   ```

   Deploy the new commit through your normal hosting process. A local file change
   alone does not change an already hosted website. Uploading only the HTML also
   does not update the feed.

The exporter keeps a defined set of event fields, strips markup from display text,
removes raw crawler payloads, deduplicates by `(source, id)`, and rejects invalid
dates before replacing the feed atomically. It reconstructs missing end times from
the supplied crawler's raw date text when available and adds timezone offsets.
This avoids marking a multi-day event as past based only on its start date.
It also reads the single-day HTML layout with a date paragraph followed by an
hour-only time range, which the supplied unified crawler had left unparsed.
Records from different sources are kept distinct; cross-source duplicate matching
belongs in your collection pipeline. Separate recurring occurrences need distinct IDs.

The public feed is approximately 292 KB versus 1.6 MB for the supplied unified
crawler output. Only the public export should be deployed; keep crawler auth,
cookies, debug files and raw collection data outside the website directory.

## What the website does

- Starts with UCI events, showing upcoming and ongoing events in Pacific Time.
- Offers All dates, Past events, and Dates unconfirmed views.
- Searches titles, descriptions, organizers, locations and source topic tags.
- Displays the actual eventCategory and eventTags labels, with a category filter
  generated from the feed (27 categories in the supplied snapshot).
- Opens RSVP or official event links in a new tab.
- Shows the latest record update date, separately from loading the page.
- Has loading, empty, error, timeout and retry states.
- Keeps the prototype's other sample listings behind an unchecked demo option.
- Displays imported text as text and rejects unsafe action-link protocols.

A record without an end time is considered past after its start time. Unknown
dates appear under All dates or Dates unconfirmed. The saved snapshot may contain
outdated details or broad recurring-event date ranges; follow the official link
for the specific session schedule. Loading JSON does not itself verify freshness.
A page refresh revalidates the published feed; it does not perform a fresh crawl.

Real event badges use source categories and topics, rather than inferred generic
"Events / Clubs" labels. The original broad resource buttons are shown only when
you enable demo listings. A selected event category filters real events only;
clearing filters resets the category and date selections.

## Browsing and filters

- **Search tags:** a separate, case-insensitive partial match against source tags
  and categories, with suggestions from the feed. It combines with the main
  keyword search and category selector.
- **Dates:** upcoming/ongoing, today, tomorrow, next seven calendar days, all dates,
  past events, or unconfirmed dates. Day boundaries use Pacific Time regardless
  of the visitor's timezone.
- **From / Through:** inclusive date bounds. Entering a date switches the preset
  to All dates; events match if their schedules overlap the selected days.
  Reversed bounds show a validation message. Other filters still apply.
- **Starts at:** morning (6 AM–noon), afternoon (noon–5 PM), evening (5–9 PM), or
  night (9 PM–6 AM). These filter the original start time. All-day and undated
  events do not match a time-of-day filter. No session times are inferred for
  multi-day events.
- **Order and headings:** earliest start first, grouped by Pacific start date,
  with one heading per day. Undated events and optional demos follow dated
  events. Multi-day events appear once under their actual start date. The
  highlighted When block appears directly below each card title.
- **Visible filters:** the summary lists keywords, tag query, category, dates and
  start-time filter. Category choices show the matching count under other filters
  and the category total when they differ. Clear filters resets every filter,
  turns demos off and restores all 295 events in this snapshot.

The reported 13-result view had `leadership` in the main search. All event
categories clears only the category selection; the search still narrows results.
The new summary makes that visible. Browser verification confirmed Clear filters
restores 295/295; regression tests verify every category's unfiltered total.

## ZotSpot dates and tags

The importer decodes `raw_data.fields` to find the named positional fields. It
uses `eventDates` (`p4` in the supplied schema) as the authoritative schedule,
before the potentially incomplete `start_datetime` / `end_datetime`. It also
accepts `eventsDates`, `start_date` and `start_data` HTML as fallbacks. Both dates
and times are extracted after decoding HTML and entities, with support for:

- A date paragraph followed by `8 AM – 10 AM` or `11:30 AM – 12 PM`.
- Separate full start and end dates, including multi-day / multi-year ranges.
- Overnight ranges such as `11 PM – 1 AM`.
- Date-only schedules, exported with `all_day: true` and displayed without an
  invented time. The end-of-day boundary is used only for filtering.

The original cleaned schedule is retained as `date_text` in the public feed.
Timezone offsets are calculated for each date in America/Los_Angeles (or the
record's supplied timezone), so daylight saving changes are handled by date.
The supplied snapshot now has 295 parsed starts and ends, recovering 266 starts
that were missing from its normalized fields. No newer events were crawled.

`eventCategory` (`p5`) supplies primary categories. `eventTags` (`p22`) supplies
additional topics; the visible linked label is preferred over accessibility text
such as "Job slash Volunteer Opportunities". Repeated labels are removed without
merging distinct topics. Normalized categories and tags are fallbacks when the
original fields are unavailable. New source categories automatically appear in
the filter after the next export and page refresh.

## Why this architecture

```text
ZotSpot / future club websites / other future sources
                         ↓
           Your crawler and source adapters
                         ↓
         Private unified_events.json snapshot
                         ↓  scripts/sync_events.py
       Website data/output/unified_events.json
                         ↓  HTTP fetch on page load
                 ZotLife event cards
```

For this amount of data, a static JSON feed is simpler to operate than a database
and API. Keeping collection out of the frontend means adding a new source does not
require a different page layout. Next, automate the crawl/export/deployment process
when the collection tools are stable. Consider a backend when you need shared user
accounts, saved events across devices, submissions, or a much larger searchable feed.

For a future club-site or Instagram adapter, export the same event schema. Prefer
an official event feed, calendar or approved API where available. Handling source
access, refresh failures and duplicate detection belongs to the crawler project;
none of those adapters have been added in this change.

### Unified source record

```json
{
  "id": "club-talk-2026-11-20",
  "source": "club-site",
  "source_url": "https://example.org/events/talk",
  "title": "Club speaker night",
  "description": "Meet the speakers and ask questions.",
  "start_datetime": "2026-11-20T18:00:00",
  "end_datetime": "2026-11-20T20:00:00",
  "timezone": "America/Los_Angeles",
  "location": "Student Center",
  "organizer_name": "Example Club",
  "organizer_type": "club",
  "categories": ["Professional"],
  "tags": ["Networking"],
  "rsvp_url": "https://example.org/events/talk",
  "cost": "FREE",
  "last_updated": "2026-11-16T12:00:00-08:00"
}
```

`id` and `title` are required. A source adapter should supply an official link,
source name, timezone and update timestamp. Unknown dates can be null. The exporter
converts local timestamps to timestamps with offsets; run it before publishing.
A new source's cards automatically use “View official event” rather than ZotSpot.
The website does not load multiple overlapping crawler output and test files.

## Verification

Python 3.9+ with timezone data and Node.js 18+ for the JavaScript checks:

```sh
python3 -m unittest discover -s tests -v
node tests/test_app.cjs
```

Python tests cover HTML schedule layouts, hour-only times, date-field priority,
field-header decoding, overnight and all-day ranges, daylight saving offsets,
original source labels, raw-record aliases, deduplication and unsafe links. JavaScript checks cover
the actual feed, category counts and filters, source badges, all-day display,
ongoing events, search, optional demos, safe rendering,
unknown dates, malformed JSON, HTTP failures, retry and local-file guidance.
Browser checks verified the root entry, real feed, no-results view, tag search,
next-seven-days filtering, date headings, highlighted times, the reported
13-result search state, and clearing filters back to all 295 events. No deployment or GitHub push was performed.

## Git workflow used

Work is on `feature/uci-event-feed`, based on upstream commit `c0187b6`.

1. Export and test the public feed.
2. Connect the frontend and verify behavior.
3. Document refresh/deployment and complete validation.

Follow-up commits correct ZotSpot HTML schedule parsing and replace generic
badges with original categories and topics, with expanded regression coverage.
Later commits add tag search, date/time filters, chronological date groups, and
visible active filters with contextual category counts.

Inspect the work with `git log --oneline c0187b6..HEAD` and
`git diff c0187b6..HEAD --stat`. All work is local; publish the reviewed branch
through your normal GitHub process.
