#!/usr/bin/env python3
"""Validate and merge collected public events into the website JSON feed. No network."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sync_events import export

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/zot_event_crawl/src/crawlers'))
from club_sources import write_json


def normalized(value):
    return ' '.join(re.sub(r'[^\w]+', ' ', str(value or '').casefold()).split())


def canonical_url(value):
    parts = urlsplit(value or '')
    if not parts.hostname or parts.path.lower().endswith('.ics'):
        return ''  # Many different events share the same calendar-feed URL.
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(('utm_', 'mc_')) and k.lower() not in ('fbclid', 'gclid')]
    return urlunsplit(('https', parts.netloc.lower(), parts.path.rstrip('/'), urlencode(sorted(query)), ''))


def merge_public(base, collected):
    # Require explicit event records, not raw newsletter/candidate arrays.
    for event in collected:
        if not isinstance(event, dict) or event.get('source') not in ('club_calendar', 'club_newsletter', 'club_website') or not event.get('start_datetime'):
            raise ValueError('Collected input must contain dated public event records, not raw text or candidates')
    public = export([*base, *collected])
    merged, removed = [], []
    by_slot = {}
    for event in public:
        start = event.get('start_datetime')
        instant = datetime.fromisoformat(start).astimezone(timezone.utc).isoformat() if start else ''
        slot = (normalized(event['title']), instant, bool(event.get('all_day')))
        prior = None
        if instant:
            for other in by_slot.get(slot, []):
                if event['source'] == other['source']:
                    continue  # Distinct source-issued IDs may describe distinct sessions.
                same_id = event.get('organizer_id') and event.get('organizer_id') == other.get('organizer_id')
                name = normalized(event.get('organizer_name'))
                same_name = name and name == normalized(other.get('organizer_name'))
                link = canonical_url(event.get('source_url'))
                same_url = link and link == canonical_url(other.get('source_url'))
                location, prior_location = normalized(event.get('location')), normalized(other.get('location'))
                different_places = location and prior_location and location != prior_location
                if same_url or (not different_places and (same_id or same_name)):
                    prior = other
                    break
        if prior:
            removed.append({'removed': {'source': event['source'], 'id': event['id']},
                            'kept': {'source': prior['source'], 'id': prior['id']},
                            'reason': 'same_title_start_and_organizer_or_event_url'})
        else:
            merged.append(event)
            by_slot.setdefault(slot, []).append(event)
    return merged, removed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', nargs='+', type=Path, default=[ROOT / 'tools/zot_event_crawl/data/output/unified_events.json'])
    parser.add_argument('--collected', type=Path, default=ROOT / 'tools/zot_event_crawl/data/output/public_feeds/public_events.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/output/unified_events.json')
    parser.add_argument('--report', type=Path, default=ROOT / 'tools/zot_event_crawl/data/output/public_feeds/website_import_report.json')
    args = parser.parse_args()
    inputs = [*args.base, args.collected]
    if args.output.resolve() in [p.resolve() for p in inputs] or args.report.resolve() in [p.resolve() for p in inputs] or args.output.resolve() == args.report.resolve():
        parser.error('Output/report must differ from input snapshots and from each other')
    base = []
    for path in args.base:
        feed = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(feed, list):
            parser.error('Each base input must be an event array')
        base.extend(feed)
    collected = json.loads(args.collected.read_text(encoding='utf-8'))
    if not isinstance(collected, list):
        parser.error('Collected input must be an event array')
    # Complete all validation before replacing the website feed.
    merged, removed = merge_public(base, collected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + '.tmp')
    temp.write_text(json.dumps(merged, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    temp.replace(args.output)
    write_json(args.report, {'base_records': len(base), 'collected_records': len(collected),
                            'website_records': len(merged), 'duplicates_removed': removed,
                            'output': str(args.output)})
    print(f'Website feed: {len(merged)} events; {len(removed)} duplicate records removed. Saved {args.output}')


if __name__ == '__main__':
    main()
