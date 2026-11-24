"""Parse public ICS schedules and readable RSS/Atom newsletter entries."""
from datetime import date, datetime, time, timedelta, timezone
import re
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from club_sources import Document, clean_url, digest, now

DEFAULT_ZONE = 'America/Los_Angeles'


def calendar_dependencies():
    try:
        from icalendar import Calendar
        import recurring_ical_events
    except ImportError as error:
        raise RuntimeError('Install calendar dependencies: python -m pip install -r tools/zot_event_crawl/requirements-public-feeds.txt') from error
    return Calendar, recurring_ical_events


def aware(value, zone):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=zone)
    return datetime.combine(value, time.min, tzinfo=zone)


def calendar_events(text, feed_url, club, window_start, window_end, max_events=2000):
    """Return unified events and review records. Window is [start, end)."""
    Calendar, recurrence = calendar_dependencies()
    candidates, events = [], []
    def review(reason, component=None):
        candidates.append({'club_id': club['id'], 'source_url': feed_url,
                           'extraction': 'icalendar', 'status': 'needs_review', 'reason': reason,
                           'uid': str(component.get('UID', '')) if component else ''})
    try:
        calendar = Calendar.from_ical(text)
    except Exception as error:
        review('invalid_calendar: ' + str(error))
        return events, candidates
    if str(calendar.get('METHOD', '')).upper() == 'CANCEL':
        review('cancelled_calendar')
        return events, candidates
    try:
        zone = ZoneInfo(str(calendar.get('X-WR-TIMEZONE', DEFAULT_ZONE)))
    except (KeyError, ValueError):
        zone = ZoneInfo(DEFAULT_ZONE)
    low, high = aware(window_start, zone), aware(window_end, zone)
    valid = Calendar()
    # Preserve embedded timezone definitions and calendar-level properties.
    for key, value in calendar.items():
        valid[key] = value
    recurring_uids = set()
    for component in calendar.subcomponents:
        if component.name != 'VEVENT':
            if component.name == 'VTIMEZONE':
                valid.add_component(component)
            continue
        if any(k in component for k in ('RRULE', 'RDATE', 'RECURRENCE-ID')):
            recurring_uids.add(str(component.get('UID', '')))
        if not component.get('SUMMARY') or not component.get('DTSTART') or not component.get('UID'):
            review('missing_uid_title_or_start', component)
            continue
        if component.errors:
            review('invalid_event_properties: ' + str(component.errors), component)
            continue
        if str(component.get('CLASS', 'PUBLIC')).upper() != 'PUBLIC':
            review('non_public_event', component)
            continue
        # Avoid expanding pathological high-frequency rules into millions of rows.
        rule = component.get('RRULE', {})
        if rule and (str(rule.get('FREQ', [''])[0]).upper() not in ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY')
                     or any(k in rule for k in ('BYSECOND', 'BYMINUTE', 'BYHOUR'))):
            review('high_frequency_recurrence_not_supported', component)
            continue
        try:
            start = component.decoded('DTSTART')
            end = component.decoded('DTEND', None)
            if not isinstance(start, (date, datetime)):
                raise ValueError('invalid_start')
            for key in ('DTSTART', 'DTEND', 'RECURRENCE-ID'):
                value = component.get(key)
                if value is not None and value.params.get('TZID') and isinstance(value.dt, datetime) and value.dt.tzinfo is None:
                    raise ValueError('unknown_timezone: ' + str(value.params['TZID']))
            if end is not None and (isinstance(start, datetime) != isinstance(end, datetime)
                                    or aware(end, zone) < aware(start, zone)):
                raise ValueError('invalid_end')
            if 'DURATION' in component and component.decoded('DURATION') < timedelta(0):
                raise ValueError('negative_duration')
            valid.add_component(component)
        except Exception as error:
            review(str(error), component)
    try:
        occurrences = recurrence.of(valid, keep_recurrence_attributes=True).between(low, high)
    except Exception as error:
        review('recurrence_expansion_failed: ' + str(error))
        return [], candidates
    seen = set()
    for event in occurrences:
        if str(event.get('STATUS', '')).upper() == 'CANCELLED':
            review('cancelled_event', event)
            continue
        try:
            start_value = event.decoded('DTSTART')
            start = aware(start_value, zone)
            all_day = not isinstance(start_value, datetime)
            end_value = event.decoded('DTEND', None)
            if end_value is None and 'DURATION' in event:
                end_value = start_value + event.decoded('DURATION')
            end = aware(end_value, zone) if end_value is not None else (start + timedelta(days=1) if all_day else None)
            # RFC 5545 all-day DTEND is exclusive; ZotLife stores an inclusive end.
            if all_day and end:
                if end <= start:
                    raise ValueError('empty_all_day_range')
                end -= timedelta(seconds=1)
            if end and end < start:
                raise ValueError('end_before_start')
            if start >= high or (end or start) < low:
                continue
            uid = str(event['UID'])
            occurrence = event.decoded('RECURRENCE-ID', start_value)
            identity = uid + ('|' + occurrence.isoformat() if uid in recurring_uids else '')
            event_id = digest(feed_url + '|' + identity)
            if event_id in seen:
                continue
            seen.add(event_id)
            if len(events) >= max_events:
                review('event_limit_reached')
                break
            url = clean_url(str(event.get('URL', '')), feed_url) or feed_url
            location = Document(str(event.get('LOCATION', ''))).root.text()
            description = Document(str(event.get('DESCRIPTION', ''))).root.text()
            categories = event.get('CATEGORIES', [])
            categories = categories if isinstance(categories, list) else [categories]
            labels = list(dict.fromkeys(str(v).strip() for category in categories
                                        for v in getattr(category, 'cats', [category]) if str(v).strip()))
            timestamp = now()
            events.append({'id': event_id, 'source': 'club_calendar', 'source_url': url,
                           'title': str(event['SUMMARY']), 'description': description,
                           'start_datetime': start.isoformat(), 'end_datetime': end.isoformat() if end else None,
                           'timezone': str(zone), 'all_day': all_day, 'location': location,
                           'location_type': 'virtual' if re.search(r'https?://', location) else 'physical' if location else 'tbd',
                           'organizer_name': club['name'], 'organizer_id': club['id'],
                           'organizer_type': club.get('organizer_type', 'club'), 'organizer_url': club['website'],
                           'categories': labels or ['Club events'], 'tags': labels,
                           'audience': 'students', 'rsvp_url': url if event.get('URL') else club['website'], 'rsvp_required': None, 'cost': '',
                           'first_seen': timestamp, 'last_updated': timestamp,
                           'raw_data': {'extraction': 'icalendar', 'feed_url': feed_url, 'uid': uid,
                                        'recurrence_id': occurrence.isoformat() if uid in recurring_uids else None,
                                        'timezone_fallback': str(zone), 'event_link_provided': bool(event.get('URL'))}})
        except Exception as error:
            review('invalid_occurrence: ' + str(error), event)
    return sorted(events, key=lambda e: datetime.fromisoformat(e['start_datetime'])), candidates


def newsletter_entries(text, page_url):
    """RSS/Atom publication dates stay metadata, never become event start dates."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    def tag(node):
        return node.tag.rsplit('}', 1)[-1]
    result = []
    for entry in root.iter():
        if tag(entry) not in ('item', 'entry'):
            continue
        fields = {}
        links = []
        for child in entry:
            name = tag(child)
            value = ''.join(child.itertext()).strip()
            fields[name] = value
            if name == 'link' and child.attrib.get('rel', 'alternate') == 'alternate':
                link = clean_url(child.attrib.get('href') or value, page_url)
                if link:
                    links.append(link)
        body = fields.get('encoded') or fields.get('content') or fields.get('description') or fields.get('summary', '')
        result.append({'title': fields.get('title', ''), 'url': next(iter(links), page_url),
                       'text': Document(body).root.text(), 'html': body,
                       'published_at': fields.get('published') or fields.get('pubDate') or fields.get('updated'),
                       'event_links': Document(body).links(page_url)})
    return result
