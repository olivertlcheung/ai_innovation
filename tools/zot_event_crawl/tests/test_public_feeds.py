from datetime import date, datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/zot_event_crawl/src/crawlers'))
sys.path.insert(0, str(ROOT / 'scripts'))
from public_feed_parser import calendar_events, newsletter_entries
from public_feed_crawler import collect_public
from update_public_events import merge_public

HAS_CALENDAR = bool(importlib.util.find_spec('icalendar') and importlib.util.find_spec('recurring_ical_events'))
CLUB = {'id': '123', 'name': 'Club A', 'website': 'https://club.example/'}
FEED = 'https://club.example/events.ics'


def ics(*events):
    return 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//ZotLife tests//EN\r\nX-WR-TIMEZONE:America/Los_Angeles\r\n' + ''.join('BEGIN:VEVENT\r\n' + e.replace('\n', '\r\n') + '\r\nEND:VEVENT\r\n' for e in events) + 'END:VCALENDAR\r\n'


def parse(text, start=date(2026, 10, 1), end=date(2026, 12, 1)):
    return calendar_events(text, FEED, CLUB, start, end)


class FakeClient:
    def __init__(self, pages):
        self.pages, self.requests = pages, []
    def fetch(self, url):
        self.requests.append(url)
        text, content_type = self.pages.get(url, ('', 'text/html'))
        return {'url': url, 'requested_url': url, 'status': 'ok' if url in self.pages else 'http_error',
                'text': text, 'content_type': content_type}


@unittest.skipUnless(HAS_CALENDAR, 'Install requirements-public-feeds.txt for calendar tests')
class CalendarTests(unittest.TestCase):
    def test_folded_text_escaping_duration_and_category_labels(self):
        events, candidates = parse(ics('UID:one\nSUMMARY:Speaker\, night\nDTSTART;TZID=America/Los_Angeles:20261120T180000\nDURATION:PT2H\nDESCRIPTION:Meet\\npeople and learn\n more.\nLOCATION:DBH 4011\nCATEGORIES:Career,Networking\nURL:https://club.example/event/one'))
        self.assertEqual(candidates, [])
        self.assertEqual(events[0]['title'], 'Speaker, night')
        self.assertEqual(events[0]['start_datetime'], '2026-11-20T18:00:00-08:00')
        self.assertEqual(events[0]['end_datetime'], '2026-11-20T20:00:00-08:00')
        self.assertEqual(events[0]['tags'], ['Career', 'Networking'])
        self.assertIn('learnmore', events[0]['description'])

    def test_all_day_exclusive_end_and_default_one_day(self):
        for end, expected in [('\nDTEND;VALUE=DATE:20261123', '2026-11-22T23:59:59-08:00'), ('', '2026-11-20T23:59:59-08:00')]:
            events, _ = parse(ics('UID:day\nSUMMARY:Fair\nDTSTART;VALUE=DATE:20261120' + end))
            self.assertTrue(events[0]['all_day'])
            self.assertEqual(events[0]['end_datetime'], expected)

    def test_recurrence_exclusion_and_dst(self):
        events, candidates = parse(ics('UID:weekly\nSUMMARY:Weekly meeting\nDTSTART;TZID=America/Los_Angeles:20261019T180000\nDTEND;TZID=America/Los_Angeles:20261019T190000\nRRULE:FREQ=WEEKLY;COUNT=4\nEXDATE;TZID=America/Los_Angeles:20261026T180000'))
        self.assertEqual(candidates, [])
        self.assertEqual([e['start_datetime'] for e in events], ['2026-10-19T18:00:00-07:00', '2026-11-02T18:00:00-08:00', '2026-11-09T18:00:00-08:00'])
        self.assertEqual(len({e['id'] for e in events}), 3)

    def test_cancelled_override_does_not_reappear_from_master(self):
        text = ics('UID:weekly\nSUMMARY:Weekly\nDTSTART;TZID=America/Los_Angeles:20261102T180000\nDTEND;TZID=America/Los_Angeles:20261102T190000\nRRULE:FREQ=WEEKLY;COUNT=3',
                   'UID:weekly\nSUMMARY:Weekly\nRECURRENCE-ID;TZID=America/Los_Angeles:20261109T180000\nDTSTART;TZID=America/Los_Angeles:20261109T180000\nSTATUS:CANCELLED')
        events, _ = parse(text)
        self.assertEqual([e['start_datetime'][0:10] for e in events], ['2026-11-02', '2026-11-16'])

    def test_moved_occurrence_uses_original_recurrence_id(self):
        master = 'UID:weekly\nSUMMARY:Weekly\nDTSTART:20261102T180000Z\nRRULE:FREQ=WEEKLY;COUNT=2'
        original, _ = parse(ics(master))
        moved, _ = parse(ics(master, 'UID:weekly\nSUMMARY:Weekly moved\nRECURRENCE-ID:20261109T180000Z\nDTSTART:20261110T180000Z'))
        self.assertEqual(original[1]['id'], moved[1]['id'])

    def test_bad_cancelled_private_and_high_frequency_records_are_reviewed(self):
        text = ics('UID:bad\nSUMMARY:Bad\nDTSTART:20261120T180000Z\nDTEND:20261119T180000Z',
                   'UID:cancel\nSUMMARY:Cancelled\nDTSTART:20261120T180000Z\nSTATUS:CANCELLED',
                   'UID:private\nSUMMARY:Private\nDTSTART:20261120T180000Z\nCLASS:PRIVATE',
                   'UID:dense\nSUMMARY:Too frequent\nDTSTART:20261120T180000Z\nRRULE:FREQ=SECONDLY',
                   'UID:no-start\nSUMMARY:No start')
        events, candidates = parse(text)
        self.assertEqual(events, [])
        self.assertEqual(len(candidates), 5)

    def test_window_end_is_exclusive_and_overlapping_event_included(self):
        text = ics('UID:overlap\nSUMMARY:Long\nDTSTART:20261031T230000\nDTEND:20261101T020000',
                   'UID:end\nSUMMARY:End\nDTSTART:20261102T000000')
        events, _ = parse(text, date(2026, 11, 1), date(2026, 11, 2))
        self.assertEqual([e['title'] for e in events], ['Long'])

    def test_single_event_identity_survives_schedule_edit(self):
        a, _ = parse(ics('UID:stable\nSUMMARY:One\nDTSTART:20261120T180000Z'))
        b, _ = parse(ics('UID:stable\nSUMMARY:Edited\nDTSTART:20261121T190000Z'))
        self.assertEqual(a[0]['id'], b[0]['id'])

    def test_unknown_timezone_is_reviewed_instead_of_assumed(self):
        events, candidates = parse(ics('UID:zone\nSUMMARY:Bad zone\nDTSTART;TZID=MadeUp/Timezone:20261120T180000'))
        self.assertEqual(events, [])
        self.assertIn('unknown_timezone', candidates[0]['reason'])

    def test_calendar_import_runs_through_actual_website_exporter(self):
        events, _ = parse(ics('UID:one\nSUMMARY:Calendar workshop\nDTSTART:20261120T180000Z'))
        merged, _ = merge_public([], events)
        self.assertEqual(merged[0]['source'], 'club_calendar')
        self.assertEqual(merged[0]['organizer_name'], 'Club A')


class NewsletterTests(unittest.TestCase):
    def test_rss_publication_time_is_only_metadata(self):
        entries = newsletter_entries('<rss><channel><item><title>Weekly news</title><link>https://club.example/newsletter/one</link><pubDate>Fri, 20 Nov 2026 10:00:00 GMT</pubDate><description><![CDATA[<p>Join us next Friday!</p><a href="https://club.example/event/talk">RSVP</a>]]></description></item></channel></rss>', 'https://club.example/feed/')
        self.assertEqual(entries[0]['text'], 'Join us next Friday! RSVP')
        self.assertNotIn('start_datetime', entries[0])
        self.assertIn('20 Nov', entries[0]['published_at'])

    def test_atom_namespaces_and_entry_links(self):
        entries = newsletter_entries('<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>News</title><link href="/newsletter/one"/><published>2026-11-20</published><content type="html">Text</content></entry></feed>', 'https://club.example/')
        self.assertEqual(entries[0]['url'], 'https://club.example/newsletter/one')

    def test_collector_preserves_text_links_and_unclear_date_candidate(self):
        home = '<a href="/newsletter/archive">Newsletter archives</a>'
        archive = '<a href="/newsletter/one">November 2026</a>'
        issue = '<title>Weekly news</title><meta property="article:published_time" content="2026-11-20"><p>Our upcoming workshop is next Friday. Details to follow.</p><a href="/events/talk">RSVP for workshop</a>'
        client = FakeClient({CLUB['website']: (home, 'text/html'), 'https://club.example/newsletter/archive': (archive, 'text/html'), 'https://club.example/newsletter/one': (issue, 'text/html')})
        with tempfile.TemporaryDirectory() as tmp:
            events, raw, candidates = collect_public(client, [CLUB], tmp, Path(tmp)/'sources.json', date(2026, 11, 1), date(2026, 12, 1), 3)
            self.assertEqual(events, [])
            issue_record = next(r for r in raw if r['url'].endswith('/one'))
            self.assertEqual(issue_record['published_at'], '2026-11-20')
            self.assertEqual(issue_record['event_links'][0]['url'], 'https://club.example/events/talk')
            self.assertTrue(any(c['raw_record_id'] == issue_record['id'] for c in candidates))
            self.assertTrue((Path(tmp)/'newsletter_raw_text.json').exists())

    def test_newsletter_jsonld_events_are_imported_without_using_publication_date(self):
        structured = {'@type': 'Event', 'name': 'Newsletter workshop', 'startDate': '2026-11-25T18:00:00', 'url': 'https://club.example/event/workshop'}
        issue_url = 'https://club.example/newsletter/one'
        club = {**CLUB, 'public_sources': [{'url': issue_url, 'kind': 'newsletter_issue', 'found_on': CLUB['website']}]}
        client = FakeClient({issue_url: ('<meta property="article:published_time" content="2026-11-20"><script type="application/ld+json">' + json.dumps(structured) + '</script>', 'text/html')})
        with tempfile.TemporaryDirectory() as tmp:
            events, _, _ = collect_public(client, [club], tmp, Path(tmp)/'sources.json', date(2026, 11, 1), date(2026, 12, 1), 1)
            self.assertEqual(events[0]['source'], 'club_newsletter')
            self.assertTrue(events[0]['start_datetime'].startswith('2026-11-25'))

    def test_redirect_to_signup_is_not_reported_as_collected_newsletter(self):
        class SignupClient(FakeClient):
            def fetch(self, url):
                return {'url': 'https://docs.google.com/forms/d/e/FORM/viewform', 'status': 'ok', 'text': '<p>Sign up</p>', 'content_type': 'text/html'}
        with tempfile.TemporaryDirectory() as tmp:
            _, raw, _ = collect_public(SignupClient({}), [CLUB], tmp, Path(tmp)/'sources.json', date(2026, 11, 1), date(2026, 12, 1), 1)
            self.assertEqual(raw, [])
            report = json.loads((Path(tmp)/'crawl_report.json').read_text())
            self.assertEqual(report['records'][0]['pages'][0]['status'], 'subscription_only')

    def test_public_collector_help_does_not_require_calendar_packages(self):
        proc = subprocess.run([sys.executable, '-B', str(ROOT/'tools/zot_event_crawl/src/crawlers/club_crawler.py'), '--collect-public-feeds', '--help'], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('--from-date', proc.stdout)

    def test_newsletters_receive_budget_even_with_many_calendar_details(self):
        archive_url = 'https://club.example/newsletter/archive'
        calendar_url = 'https://club.example/calendar'
        club = {**CLUB, 'public_sources': [{'url': calendar_url, 'kind': 'calendar_page'}, {'url': archive_url, 'kind': 'newsletter_archive'}]}
        details = ''.join(f'<a href="/events/{i}">Event {i}</a>' for i in range(20))
        client = FakeClient({calendar_url: (details, 'text/html'), archive_url: ('<a href="/newsletter/one">November 2026</a>', 'text/html')})
        with tempfile.TemporaryDirectory() as tmp:
            collect_public(client, [club], tmp, Path(tmp)/'sources.json', date(2026, 11, 1), date(2026, 12, 1), 4)
            self.assertIn(archive_url, client.requests)
            self.assertIn('https://club.example/newsletter/one', client.requests)


class ImportTests(unittest.TestCase):
    def row(self, **overrides):
        return {'id': 'one', 'source': 'zotspot', 'title': 'Workshop', 'start_datetime': '2026-11-25T18:00:00-08:00', 'organizer_id': '123', 'organizer_name': 'Club A', 'source_url': 'https://club.example/event', **overrides}

    def test_cross_source_duplicates_match_time_and_organizer(self):
        merged, duplicates = merge_public([self.row()], [self.row(id='new', source='club_calendar', start_datetime='2026-11-26T02:00:00+00:00')])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(merged[0]['source'], 'zotspot')

    def test_distinct_organizers_and_recurrence_dates_are_preserved(self):
        merged, _ = merge_public([self.row()], [self.row(id='other', source='club_calendar', organizer_id='456', organizer_name='Club B', source_url='https://other.example/event'), self.row(id='next', source='club_calendar', start_datetime='2026-12-02T18:00:00-08:00')])
        self.assertEqual(len(merged), 3)

    def test_candidates_cannot_be_imported(self):
        with self.assertRaises(ValueError):
            merge_public([], [{'id': 'draft', 'title': 'Next Friday', 'status': 'needs_review'}])

    def test_distinct_source_issued_sessions_and_different_venues_survive(self):
        merged, _ = merge_public([self.row(location='DBH 4011'), self.row(id='second', location='DBH 4011')], [self.row(id='new', source='club_calendar', source_url='https://club.example/another-event', location='Student Center')])
        self.assertEqual(len(merged), 3)


if __name__ == '__main__':
    unittest.main()
