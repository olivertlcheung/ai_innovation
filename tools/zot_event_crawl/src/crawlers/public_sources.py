"""Find published public calendar and newsletter links, retaining their evidence."""
import base64
import re
from urllib.parse import parse_qs, quote, unquote, urlsplit

from club_sources import Document, clean_url, host_matches, now, platform


def public_url(value, base=''):
    value = str(value or '').strip()
    if value.lower().startswith('webcal://'):
        value = 'https://' + value[9:]
    url = clean_url(value, base)
    # Do not collect secret calendar addresses, even if someone published one.
    if re.search(r'/private(?:-[^/]+)?/', url, re.I):
        return ''
    return url if url.startswith(('https://', 'http://')) else ''


def calendar_feeds(url):
    """Convert only published Google calendar IDs to their public ICS addresses."""
    url = public_url(url)
    if not url:
        return []
    parts = urlsplit(url)
    if parts.path.lower().endswith('.ics') or '/public/basic.ics' in parts.path:
        return [url]
    if parts.hostname not in ('calendar.google.com', 'www.google.com') or '/calendar' not in parts.path:
        return []
    query = parse_qs(parts.query)
    if query.get('action', [''])[0].upper() == 'TEMPLATE' or '/event' in parts.path:
        return []  # An add-one-event button is not a subscribable calendar.
    ids = list(query.get('src', []))
    linked_feeds = []
    for value in query.get('cid', []):
        if value.startswith(('webcal://', 'https://', 'http://')):
            linked = public_url(value)
            if linked and urlsplit(linked).path.lower().endswith('.ics'):
                linked_feeds.append(linked)
            continue
        if '@' in value:
            ids.append(value)
        else:
            try:
                ids.append(base64.urlsafe_b64decode(value + '=' * (-len(value) % 4)).decode())
            except (ValueError, UnicodeError):
                continue
    derived = ['https://calendar.google.com/calendar/ical/' + quote(cid, safe='') + '/public/basic.ics'
               for cid in ids if '@' in cid and not any(c.isspace() for c in cid)]
    return list(dict.fromkeys([*linked_feeds, *derived]))


def source_kind(url, label=''):
    p = urlsplit(url)
    host, path = p.hostname or '', p.path.lower()
    words = label.lower() + ' ' + unquote(path)
    if re.search(r'/comments?/|comment-page-|comments? feed', words):
        return None
    if platform(url):
        return None
    if calendar_feeds(url):
        return 'calendar_feed' if path.endswith('.ics') else 'calendar_page'
    if ('docs.google.com' == host and '/forms/' in path or 'forms.gle' == host
            or 'list-manage.com' in host and '/subscribe' in path
            or re.search(r'\bsubscribe\b|sign.?up', words) and re.search(r'newsletter|mailing|email', words)):
        return 'newsletter_subscription'
    if ('campaign-archive.com' in host and ('/home/' in path or not parse_qs(p.query).get('id'))
            or re.search(r'newsletter|newsletters', words) and re.search(r'archive|past issues|previous issues', words)):
        return 'newsletter_archive'
    if ('campaign-archive.com' in host or host_matches(host, 'mailchi.mp')
            or 'hubspotpreview' in host or 'hs_preview' in parse_qs(p.query)):
        return 'newsletter_issue'
    if re.search(r'newsletter|mailing', words) and (path.endswith(('.rss', '.atom', '/feed', '/feed/')) or '/rss' in path):
        return 'newsletter_feed'
    if re.search(r'newsletter|mailing.list', words):
        return 'newsletter_page'
    if re.search(r'calendar', words):
        return 'calendar_page'
    return None


def published_sources(html, page_url):
    doc = Document(html)
    links = [{'url': n.attrs.get('href', ''), 'label': n.text() or n.attrs.get('aria-label', '')}
             for n in doc.root.walk('a')]
    for node in doc.root.walk():
        # Calendars are often embedded in an iframe, not linked by an anchor.
        if node.tag == 'iframe':
            links.append({'url': node.attrs.get('src', ''), 'label': node.attrs.get('title', '')})
        elif node.tag == 'link' and node.attrs.get('type', '').lower() in ('text/calendar', 'application/rss+xml', 'application/atom+xml'):
            if node.attrs['type'].lower() != 'text/calendar' and not re.search(r'newsletter|mailing', node.attrs.get('href', '') + ' ' + node.attrs.get('title', ''), re.I):
                continue  # Generic blog/comment feeds are not newsletter archives.
            links.append({'url': node.attrs.get('href', ''), 'label': node.attrs.get('title', ''),
                          'kind': 'calendar_feed' if node.attrs['type'].lower() == 'text/calendar' else 'newsletter_feed'})
    results, seen = [], set()
    for link in links:
        url = public_url(link['url'], page_url)
        if not url:
            continue
        kind = link.get('kind') or source_kind(url, link['label'])
        if not kind:
            continue
        targets = [(url, kind, None)]
        if kind == 'calendar_page':
            targets.extend((feed, 'calendar_feed', url) for feed in calendar_feeds(url))
        for target, target_kind, derived in targets:
            if (target, target_kind) in seen:
                continue
            seen.add((target, target_kind))
            results.append({'url': target, 'kind': target_kind, 'found_on': page_url,
                            'link_label': link['label'], 'derived_from': derived,
                            'evidence': 'public_calendar_id' if derived else 'published_link',
                            'discovered_at': now()})
    return results


def archive_links(html, page_url):
    """Follow public issue/archive links, never unsubscribe, subscribe, or forms."""
    result = []
    base = urlsplit(page_url)
    for link in Document(html).links(page_url):
        url = public_url(link['url'], page_url)
        if not url or platform(url):
            continue
        p = urlsplit(url)
        words = (link['label'] + ' ' + p.path).lower()
        if re.search(r'unsubscribe|preferences|subscribe|/forms/|/abuse|privacy|login|sign.?in', words):
            continue
        kind = source_kind(url, link['label'])
        if kind in ('newsletter_issue', 'newsletter_archive', 'newsletter_feed'):
            result.append({'url': url, 'kind': kind})
        elif re.search(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d{2}\b|\bthe public good\b|\bnewsletter\b', link['label'], re.I):
            result.append({'url': url, 'kind': 'newsletter_issue'})
        elif p.hostname == base.hostname and (re.search(r'/p/|/issues?/|/archive/|/newsletters?/', p.path, re.I)
                                               or re.search(r'past issues|previous|older|next|view.*browser', words)):
            result.append({'url': url, 'kind': 'newsletter_issue'})
    return list({(v['url'], v['kind']): v for v in result}.values())
