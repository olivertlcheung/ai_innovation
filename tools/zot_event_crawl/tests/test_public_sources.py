import base64
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/crawlers'))
from public_sources import archive_links, calendar_feeds, public_url, published_sources, source_kind


class PublicSourceTests(unittest.TestCase):
    def test_embedded_google_calendar_retains_link_evidence(self):
        sources = published_sources('<iframe title="Club Calendar" src="https://calendar.google.com/calendar/embed?src=club%40group.calendar.google.com&amp;ctz=America%2FLos_Angeles"></iframe>', 'https://club.example/events')
        feed = next(s for s in sources if s['kind'] == 'calendar_feed')
        self.assertEqual(feed['url'], 'https://calendar.google.com/calendar/ical/club%40group.calendar.google.com/public/basic.ics')
        self.assertEqual(feed['found_on'], 'https://club.example/events')
        self.assertIn('/embed?', feed['derived_from'])

    def test_encoded_calendar_id_and_multiple_embedded_calendars(self):
        cid = base64.urlsafe_b64encode(b'club@group.calendar.google.com').decode().rstrip('=')
        self.assertEqual(len(calendar_feeds('https://calendar.google.com/calendar?cid=' + cid)), 1)
        self.assertEqual(len(calendar_feeds('https://calendar.google.com/calendar/embed?src=a%40uci.edu&src=b%40uci.edu')), 2)
        self.assertEqual(calendar_feeds('https://www.google.com/calendar/render?cid=webcal://club.example/calendar.ics'), ['https://club.example/calendar.ics'])

    def test_add_event_and_secret_calendars_are_not_collected(self):
        self.assertEqual(calendar_feeds('https://calendar.google.com/calendar/render?action=TEMPLATE&text=Hello'), [])
        self.assertEqual(public_url('https://calendar.google.com/calendar/ical/club/private-secret/basic.ics'), '')
        self.assertEqual(public_url('file:///tmp/calendar.ics'), '')

    def test_webcal_and_feed_autodiscovery(self):
        sources = published_sources('<a href="webcal://club.example/calendar.ics">Calendar</a><link rel="alternate" type="application/rss+xml" href="/newsletter/feed/">', 'https://club.example/')
        self.assertEqual({s['kind'] for s in sources}, {'calendar_feed', 'newsletter_feed'})
        self.assertEqual(sources[0]['url'], 'https://club.example/calendar.ics')

    def test_newsletter_signups_are_separate_from_readable_issues(self):
        self.assertEqual(source_kind('https://club.us1.list-manage.com/subscribe?u=A&id=B', 'Newsletter'), 'newsletter_subscription')
        self.assertEqual(source_kind('https://docs.google.com/forms/d/e/FORM/viewform', 'Newsletter'), 'newsletter_subscription')
        self.assertEqual(source_kind('https://club.example/newsletter/archive', 'Past newsletter issues'), 'newsletter_archive')
        self.assertEqual(source_kind('https://us1.campaign-archive.com/?u=A&id=B'), 'newsletter_issue')

    def test_archive_links_exclude_subscriptions_and_unsubscribe_actions(self):
        html = '<a href="/newsletter/november">November issue</a><a href="https://us1.campaign-archive.com/?u=A&id=B">Read</a><a href="/unsubscribe">Unsubscribe</a><a href="/newsletter/subscribe">Subscribe</a>'
        links = archive_links(html, 'https://club.example/newsletter/archive')
        self.assertEqual(len(links), 2)
        self.assertTrue(all('subscribe' not in s['url'] for s in links))

    def test_generic_blog_and_comment_feeds_do_not_displace_calendar_requests(self):
        sources = published_sources('<link type="application/rss+xml" title="Blog Feed" href="/feed/"><link type="application/rss+xml" title="Comments Feed" href="/comments/feed/">', 'https://club.example/')
        self.assertEqual(sources, [])


if __name__ == '__main__':
    unittest.main()
