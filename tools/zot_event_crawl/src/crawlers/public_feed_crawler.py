#!/usr/bin/env python3
"""Collect published public calendars and newsletter archives into unified events."""
import argparse
from datetime import date, datetime, timedelta
import heapq
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from club_sources import ROOT, Document, PublicClient, digest, now, platform, relevant_pages, write_json
from club_event_crawler import raw_record, structured_events
from public_sources import archive_links, calendar_feeds, public_url, published_sources, source_kind
from public_feed_parser import DEFAULT_ZONE, aware, calendar_dependencies, calendar_events, newsletter_entries

PRIORITY = {'calendar_feed': 0, 'calendar_page': 1, 'event_page': 1,
            'newsletter_feed': 2, 'newsletter_archive': 2, 'newsletter_page': 2,
            'newsletter_issue': 3, 'website': 4, 'newsletter_subscription': 5}


def event_links(html, url):
    result = []
    for link in Document(html).links(url):
        target = public_url(link['url'], url)
        if not target or platform(target):
            continue
        text = link['label'] + ' ' + urlsplit(target).path
        if re.search(r'unsubscribe|preferences|privacy|/forms/|subscribe', text, re.I):
            continue
        if re.search(r'/events-category/|/departament/|/category/|/page/\d+', urlsplit(target).path):
            continue
        if re.search(r'\bevents?\b|rsvp|register|workshop|seminar|meeting|details', text, re.I):
            result.append({**link, 'url': target})
    return list({item['url']: item for item in result}.values())[:100]


def collect_public(client, clubs, output_dir, sources_output, window_start, window_end,
                   pages_per_club=12, max_events=2000):
    if window_end <= window_start or (window_end - window_start).days > 366:
        raise ValueError('The calendar window must be positive and no longer than 366 days')
    output = Path(output_dir)
    events, raws, candidates, sources, reports = [], [], [], [], []
    identities, raw_indices = set(), {}
    zone = ZoneInfo(DEFAULT_ZONE)
    low, high = aware(window_start, zone), aware(window_end, zone)
    def save_raw(raw):
        key = raw['id']
        if key not in raw_indices:
            raw_indices[key] = len(raws)
            raws.append(raw)
        else:
            old = raws[raw_indices[key]]
            if not raw.get('published_at'):
                raw['published_at'] = old.get('published_at')
            raws[raw_indices[key]] = raw
    def add_events(extracted, evidence, club):
        for event in extracted:
            start = datetime.fromisoformat(event['start_datetime'])
            end = datetime.fromisoformat(event['end_datetime']) if event.get('end_datetime') else start
            if start >= high or end < low:
                continue
            key = (event['source'], event['id'])
            if key not in identities:
                identities.add(key)
                event.setdefault('raw_data', {})['source_evidence'] = evidence
                events.append(event)
    def checkpoint():
        write_json(output / 'public_events.json', sorted(events, key=lambda e: datetime.fromisoformat(e['start_datetime'])))
        write_json(output / 'newsletter_raw_text.json', raws)
        write_json(output / 'event_candidates.json', candidates)
        write_json(sources_output, sources)
        write_json(output / 'crawl_report.json', {
            'updated_at': now(), 'window_start': window_start.isoformat(), 'window_end_exclusive': window_end.isoformat(),
            'clubs_processed': len(reports), 'events': len(events), 'newsletter_records': len(raws),
            'candidates': len(candidates), 'sources_discovered': len(sources), 'records': reports})
    for club in clubs:
        queue, seen, queued, evidence_seen = [], set(), set(), set()
        attempts, count, serial = [], 0, 0
        start_event_count = len(events)
        def enqueue(url, kind='website', found_on=None, label='', evidence=None):
            nonlocal serial
            url = public_url(url)
            if not url or platform(url):
                return
            source = {'club_id': club['id'], 'club_name': club['name'], 'url': url, 'kind': kind,
                      'found_on': found_on or club.get('directory_url') or club['website'],
                      'link_label': label, 'discovered_at': now(), **(evidence or {})}
            key = (url, source['found_on'])
            if key not in evidence_seen:
                sources.append(source)
                evidence_seen.add(key)
            if url in queued or url in seen or kind == 'newsletter_subscription':
                return
            # Use ICS rather than spend a request on Google's interactive calendar UI.
            feeds = calendar_feeds(url) if kind != 'calendar_feed' else []
            if feeds:
                for feed in feeds:
                    enqueue(feed, 'calendar_feed', source['found_on'], label,
                            {'derived_from': url, 'evidence': 'public_calendar_id'})
                return
            serial += 1
            heapq.heappush(queue, (PRIORITY.get(kind, 4), serial, url, kind, source))
            queued.add(url)
        enqueue(club['website'])
        for seed in club.get('public_sources', []):
            enqueue(seed['url'], seed['kind'], seed.get('found_on'), seed.get('link_label', ''), seed)
        while queue and count < pages_per_club:
            # Reserve the second half of the budget for newsletter sources when
            # calendars expose many detail/category links.
            newsletters = [i for i, item in enumerate(queue) if item[3].startswith('newsletter')]
            if count >= max(1, pages_per_club // 2) and newsletters:
                index = min(newsletters, key=lambda i: queue[i][:2])
                _, _, url, kind, evidence = queue.pop(index)
                heapq.heapify(queue)
            else:
                _, _, url, kind, evidence = heapq.heappop(queue)
            if url in seen:
                continue
            seen.add(url)
            page = client.fetch(url)
            count += 1
            final = page['url']
            if final != url and final in seen:
                attempts.append({'url': url, 'final_url': final, 'kind': kind, 'status': 'duplicate_redirect'})
                continue
            seen.add(final)
            attempt = {k: v for k, v in page.items() if k != 'text'}
            attempt['kind'] = kind
            attempts.append(attempt)
            evidence['collection_status'] = page['status']
            if page['status'] != 'ok':
                continue
            if not public_url(final) or platform(final):
                attempt['status'] = 'unsupported_redirect'
                continue
            body, content_type = page['text'], page.get('content_type', '')
            destination_kind = source_kind(final, evidence.get('link_label', ''))
            if destination_kind == 'newsletter_subscription':
                attempt['status'] = 'subscription_only'
                evidence['collection_status'] = 'subscription_only'
                continue
            if 'BEGIN:VCALENDAR' in body[:200].upper():
                extracted, review = calendar_events(body, final, club, window_start, window_end, max_events)
                add_events(extracted, evidence, club)
                candidates.extend(review)
                attempt.update(kind='calendar_feed', events_extracted=len(extracted))
                continue
            if kind == 'calendar_feed' or content_type == 'text/calendar':
                attempt['status'] = 'invalid_calendar_response'
                candidates.append({'club_id': club['id'], 'source_url': final, 'status': 'needs_review',
                                   'reason': 'calendar_response_is_not_ics'})
                continue
            entries = newsletter_entries(body, final) if ('xml' in content_type or body.lstrip().startswith(('<?xml', '<rss', '<feed'))) else []
            for entry in entries[:100]:
                raw = {'id': digest(club['id'] + '|' + entry['url']), 'club_id': club['id'],
                       'club_name': club['name'], 'source_kind': 'newsletter_issue', 'status': 'ok',
                       'url': entry['url'], 'title': entry['title'], 'text': entry['text'],
                       'event_links': event_links(entry['html'], entry['url']),
                       'published_at': entry['published_at'], 'fetched_at': page.get('fetched_at', now()),
                       'processing_status': 'needs_event_extraction', 'source_evidence': evidence}
                save_raw(raw)
                candidates.append({'club_id': club['id'], 'source_url': entry['url'], 'raw_record_id': raw['id'],
                                   'status': 'needs_review', 'reason': 'newsletter_text_requires_event_dates'})
                enqueue(entry['url'], 'newsletter_issue', final, entry['title'])
            if entries:
                continue
            if 'html' not in content_type:
                attempt['status'] = 'unsupported_content_type'
                continue
            newsletter = kind.startswith('newsletter')
            extracted, review = structured_events(body, final, club)
            for event in extracted:
                event['source'] = 'club_newsletter' if newsletter else 'club_website'
                event['organizer_type'] = club.get('organizer_type', 'club')
            add_events(extracted, evidence, club)
            candidates.extend(review)
            raw = raw_record(page, club)
            if newsletter:
                raw.update(source_kind=kind, event_links=event_links(body, final),
                           processing_status='structured_events_extracted' if extracted else 'needs_event_extraction',
                           source_evidence=evidence)
                if kind == 'newsletter_archive':
                    raw['processing_status'] = 'archive_index'
                save_raw(raw)
                if not extracted and kind != 'newsletter_archive':
                    candidates.append({'club_id': club['id'], 'source_url': final, 'raw_record_id': raw['id'],
                                       'status': 'needs_review', 'reason': 'newsletter_text_requires_event_dates'})
                for link in archive_links(body, final):
                    enqueue(link['url'], link['kind'], final)
            if newsletter or kind in ('calendar_page', 'event_page'):
                # Explicit RSVP/event links may contain structured event data.
                for link in event_links(body, final)[:10]:
                    enqueue(link['url'], 'event_page', final, link['label'])
            for source in published_sources(body, final):
                enqueue(source['url'], source['kind'], final, source['link_label'], source)
            if kind in ('website', 'calendar_page', 'newsletter_page'):
                for target in relevant_pages(body, final):
                    inferred = source_kind(target) or ('calendar_page' if re.search(r'events?|calendar', urlsplit(target).path, re.I) else 'website')
                    enqueue(target, inferred, final)
        pending = [item[2] for item in sorted(queue) if item[2] not in seen]
        reports.append({'club_id': club['id'], 'club_name': club['name'], 'pages_attempted': count,
                        'events_added': len(events) - start_event_count, 'pending_urls': pending,
                        'page_limit_reached': bool(pending), 'pages': attempts})
        checkpoint()
    checkpoint()
    return events, raws, candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=ROOT / 'data/clubs/club_sources.json')
    parser.add_argument('--club-id', action='append', help='Collect selected club IDs; repeat for several clubs')
    parser.add_argument('--max-clubs', type=int, default=5)
    parser.add_argument('--pages-per-club', type=int, default=12)
    parser.add_argument('--max-events-per-feed', type=int, default=2000)
    parser.add_argument('--from-date', type=date.fromisoformat, default=datetime.now(ZoneInfo(DEFAULT_ZONE)).date() - timedelta(days=7))
    parser.add_argument('--until-date', type=date.fromisoformat, help='Exclusive upper bound; default 180 days after --from-date')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'data/output/public_feeds')
    parser.add_argument('--sources-output', type=Path, default=ROOT / 'data/clubs/club_public_sources.json')
    parser.add_argument('--delay', type=float, default=2)
    args = parser.parse_args()
    end = args.until_date or args.from_date + timedelta(days=180)
    if args.pages_per_club < 1 or args.max_clubs < 1 or args.max_events_per_feed < 1 or not 0 < (end - args.from_date).days <= 366:
        parser.error('Positive limits and a date window of 1–366 days are required')
    try:
        calendar_dependencies()
    except RuntimeError as error:
        parser.error(str(error))
    clubs = json.loads(args.sources.read_text(encoding='utf-8'))
    if args.club_id:
        missing = set(args.club_id) - {str(c['id']) for c in clubs}
        if missing:
            parser.error('Unknown club IDs: ' + ', '.join(sorted(missing)))
        clubs = [c for c in clubs if str(c['id']) in args.club_id]
    events, raws, candidates = collect_public(PublicClient(delay=args.delay, max_bytes=5_000_000),
        clubs[:args.max_clubs], args.output_dir, args.sources_output, args.from_date, end,
        args.pages_per_club, args.max_events_per_feed)
    print(json.dumps({'events': len(events), 'newsletter_records': len(raws), 'review_candidates': len(candidates),
                      'output_dir': str(args.output_dir), 'sources_output': str(args.sources_output)}, indent=2))


if __name__ == '__main__':
    main()
