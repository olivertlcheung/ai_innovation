#!/usr/bin/env python3
"""Discover club websites/social links using published ZotSpot links. Stdlib only."""
import argparse
from collections import deque
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[2]
USER_AGENT = 'ZotLifeResearchCrawler/1.0'
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
SOCIAL_HOSTS = {'instagram': ('instagram.com',), 'linkedin': ('linkedin.com',),
                'discord': ('discord.gg','discord.com'), 'tiktok': ('tiktok.com',),
                'facebook': ('facebook.com',), 'youtube': ('youtube.com','youtu.be')}
HUBS = ('linktr.ee', 'beacons.ai')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()[:20]


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def walk(self, tag=None):
        if tag is None or self.tag == tag:
            yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk(tag)

    def text(self):
        if self.tag in ('script', 'style', 'noscript', 'svg'):
            return ''
        return ' '.join(' '.join(child.text() if isinstance(child, Node) else child
                               for child in self.children).split())


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node('document')
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, value):
        self.stack[-1].children.append(value)

    def links(self, base):
        result = []
        for node in self.root.walk('a'):
            url = clean_url(node.attrs.get('href', ''), base)
            if url:
                result.append({'url': url, 'label': node.text() or node.attrs.get('aria-label', '')})
        return result


def clean_url(value, base=''):
    value = unescape(str(value or '')).strip()
    if not value or value.startswith(('#', 'javascript:', 'tel:', 'data:')):
        return ''
    if value.lower().startswith('mailto:'):
        return 'mailto:' + value[7:].split('?')[0]
    parts = urlsplit(urljoin(base, value))
    if parts.scheme.lower() not in ('http','https') or not parts.hostname or parts.username or parts.password:
        return ''
    host = parts.hostname.lower()
    # Known outgoing-link wrappers; keep destination, never execute page scripts.
    if host in ('l.instagram.com', 'l.facebook.com'):
        target = (parse_qs(parts.query).get('u') or [''])[0]
        return clean_url(target) if target and urlsplit(target).hostname not in ('l.instagram.com','l.facebook.com') else ''
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or '/', parts.query, ''))


def host_matches(host, suffix):
    return host == suffix or host.endswith('.' + suffix)


def platform(url):
    if url.lower().startswith('mailto:'):
        return 'email'
    host = urlsplit(url).hostname or ''
    for name, domains in SOCIAL_HOSTS.items():
        if any(host_matches(host, domain) for domain in domains):
            return name
    return None


def profile_url(url):
    name = platform(url)
    parts = urlsplit(url)
    if name == 'instagram':
        path = parts.path.strip('/').split('/')
        if not path[0] or path[0].lower() in {'p','reel','reels','stories','explore','accounts','direct','share'}:
            return ''
        return f'https://www.instagram.com/{path[0]}/'
    if name in ('linkedin','tiktok','facebook','youtube'):
        if any(word in parts.path.lower() for word in ('sharer','sharearticle','intent/','login','signup')):
            return ''
        return urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
    return url


def directory_clubs(html, url):
    doc, result = Document(html), []
    for card in doc.root.walk('li'):
        if 'list-group-item' not in card.attrs.get('class', '').split():
            continue
        website = next((a for a in card.walk('a') if a.attrs.get('aria-label', '').strip().lower() == 'website'), None)
        heading = next(card.walk('h2'), None)
        if website is None or heading is None:
            continue
        website_url = clean_url(website.attrs.get('href'), url)
        if not website_url:
            continue
        ids = [re.search(r'(?:cb_club_|a-mission_|^club_)(\d+)', n.attrs.get('id','')) for n in card.walk()]
        club_id = next((match[1] for match in ids if match), digest(heading.text() + website_url))
        category = next((n.text() for n in card.walk('p') if 'grey-element' in n.attrs.get('class','').split()), '')
        result.append({'id':club_id, 'name':heading.text(), 'category':category,
                       'directory_url':url, 'website':website_url,
                       'website_evidence':{'page_url':url,'link_label':'Website','href':website_url},
                       'social_links':{}, 'crawl_status':'not_started', 'pages':[]})
    next_pages = [link['url'] for link in doc.links(url)
                  if urlsplit(link['url']).hostname == urlsplit(url).hostname
                  and urlsplit(link['url']).path.rstrip('/') == '/club_signup'
                  and ('load all' in link['label'].lower() or link['label'].strip().lower() in ('next','next page'))]
    return result, list(dict.fromkeys(next_pages))


def social_links(html, page_url):
    results, seen = [], set()
    for link in Document(html).links(page_url):
        kind = platform(link['url'])
        normalized = profile_url(link['url']) if kind else ''
        if not normalized or (kind, normalized) in seen:
            continue
        seen.add((kind, normalized))
        scope = 'individual' if kind == 'linkedin' and urlsplit(normalized).path.startswith('/in/') else 'organization' if kind == 'linkedin' and urlsplit(normalized).path.startswith(('/company/','/school/')) else 'unconfirmed'
        results.append({'platform':kind,'url':normalized,'account_scope':scope,'found_on':page_url,
                        'link_label':link['label'],'evidence':'published_link','discovered_at':now()})
    return results


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PublicClient:
    """Bounded, polite public HTTP client. Reports blocks instead of bypassing them."""
    def __init__(self, delay=2.0, timeout=20, max_bytes=30_000_000):
        self.delay, self.timeout, self.max_bytes = max(0, delay), timeout, max_bytes
        self.opener, self.robots, self.last = build_opener(NoRedirect()), {}, {}

    def _validate(self, url):
        parts = urlsplit(url)
        if not clean_url(url) or parts.scheme not in ('http','https'):
            raise ValueError('not_public_http_url')
        addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80))
        if any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
            raise ValueError('non_public_address')

    def _request(self, url):
        self._validate(url)
        host = urlsplit(url).netloc
        wait = self.delay - (time.monotonic() - self.last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self.last[host] = time.monotonic()
        req = Request(url, headers={'User-Agent':USER_AGENT,'Accept':'text/html,application/ld+json,application/json,text/calendar;q=0.8,*/*;q=0.5'})
        with self.opener.open(req, timeout=self.timeout) as response:
            data = response.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                raise ValueError('response_too_large')
            return data.decode(response.headers.get_content_charset() or 'utf-8', errors='replace'), response.headers.get_content_type()

    def allowed(self, url):
        parts = urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self.robots:
            robot_url = origin + '/robots.txt'
            try:
                for _ in range(5):
                    try:
                        text, _ = self._request(robot_url)
                        parser = RobotFileParser(robot_url)
                        parser.parse(text.splitlines())
                        self.robots[origin] = parser
                        crawl_delay = parser.crawl_delay(USER_AGENT) or parser.crawl_delay('*')
                        if crawl_delay:
                            self.delay = max(self.delay, crawl_delay)
                        break
                    except HTTPError as error:
                        if error.code in (301,302,303,307,308):
                            robot_url = clean_url(error.headers.get('Location'),robot_url)
                            if not robot_url:
                                raise ValueError('invalid_robots_redirect')
                            continue
                        self.robots[origin] = error.code == 404
                        break
                else:
                    self.robots[origin] = False
            except Exception:
                self.robots[origin] = False
        parser = self.robots[origin]
        return parser if isinstance(parser, bool) else parser.can_fetch(USER_AGENT, url)

    def fetch(self, url):
        original = url
        result = {'requested_url':original,'url':url,'status':'error','fetched_at':now(),'text':'','content_type':''}
        try:
            for _ in range(6):
                self._validate(url)
                if not self.allowed(url):
                    result.update(url=url,status='robots_blocked')
                    return result
                try:
                    text, content_type = self._request(url)
                except HTTPError as error:
                    if error.code in (301,302,303,307,308):
                        target = clean_url(error.headers.get('Location'), url)
                        if not target:
                            raise ValueError('invalid_redirect')
                        url = target
                        continue
                    result.update(url=url,status='rate_limited' if error.code == 429 else 'http_error', http_status=error.code)
                    return result
                result.update(url=url,text=text,content_type=content_type,status='ok')
                if any(marker in text.lower() for marker in ('cf-chl-', 'captcha-container', 'challenge-platform')):
                    result['status'] = 'challenge_required'
                elif any(part in urlsplit(url).path.lower() for part in ('accounts/login','/auth/login','/checkpoint/')):
                    result['status'] = 'login_required'
                return result
            raise ValueError('too_many_redirects')
        except (URLError, ValueError, OSError) as error:
            result.update(url=url,error=str(error))
            return result


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2) + '\n',encoding='utf-8')
    tmp.replace(path)


def relevant_pages(html, url):
    parts = urlsplit(url)
    prefix = '/' + parts.path.strip('/').split('/')[0] + '/' if parts.hostname == 'zotspot.uci.edu' else ''
    result = []
    for link in Document(html).links(url):
        other = urlsplit(link['url'])
        if platform(link['url']):
            continue
        same_site = other.hostname == parts.hostname and (not prefix or other.path.startswith(prefix))
        hub = any(host_matches(other.hostname or '', domain) for domain in HUBS)
        if hub or (same_site and re.search(r'contact|about|event|calendar|connect|social|newsletter|announcement|archive', link['label'] + ' ' + other.path, re.I)):
            if not re.search(r'logout|signout|login|signup|register|wp-admin|\.pdf$', other.path,re.I):
                result.append(link['url'])
    return list(dict.fromkeys(result))


def discover(client, directory_url, output, max_clubs=None, max_directory_pages=3, pages_per_club=3, directory_html=None):
    from public_sources import published_sources
    pending, visited, clubs, directory_report = deque([directory_url]), set(), {}, []
    while pending and len(visited) < max_directory_pages:
        url = pending.popleft()
        if url in visited:
            continue
        visited.add(url)
        page = {'url':url,'status':'ok','text':Path(directory_html).read_text(encoding='utf-8')} if directory_html and len(visited)==1 else client.fetch(url)
        directory_report.append({k:v for k,v in page.items() if k!='text'})
        if page['status'] != 'ok':
            continue
        records, more = directory_clubs(page['text'],page['url'])
        for club in records:
            clubs.setdefault(club['id'],club)
        pending.extend(more)
    records = list(clubs.values())
    enriched = records[:max_clubs] if max_clubs is not None else records
    # Preserve all directory entries even when only a bounded sample is enriched.
    for club in enriched:
        queue, seen = deque([club['website']]), set()
        while queue and len(club['pages']) < pages_per_club:
            url = queue.popleft()
            if url in seen or platform(url):
                continue
            seen.add(url)
            page = client.fetch(url)
            if page['url'] != url and page['url'] in seen:
                continue
            seen.add(page['url'])
            club['pages'].append({k:v for k,v in page.items() if k!='text'})
            if page['status'] != 'ok':
                continue
            for link in social_links(page['text'], page['url']):
                existing = club['social_links'].setdefault(link['platform'],[])
                prior = next((item for item in existing if item['url']==link['url']), None)
                if prior is None:
                    existing.append(link)
                elif link['found_on'] != prior['found_on']:
                    evidence = prior.setdefault('also_found_on', [])
                    if link['found_on'] not in evidence:
                        evidence.append(link['found_on'])
            existing_public = club.setdefault('public_sources', [])
            for source in published_sources(page['text'], page['url']):
                if not any(s['url'] == source['url'] and s['found_on'] == source['found_on'] for s in existing_public):
                    existing_public.append(source)
            queue.extend(relevant_pages(page['text'],page['url']))
        direct = platform(club['website'])
        if direct:
            canonical = profile_url(club['website'])
            if canonical:
                club['social_links'].setdefault(direct,[]).append({'platform':direct,'url':canonical,'found_on':club['directory_url'],'evidence':'directory_website_link','discovered_at':now(),'link_label':'Website'})
        club['crawl_status'] = 'ok' if any(p['status']=='ok' for p in club['pages']) or direct else 'unavailable'
        write_json(output,records)
    write_json(output,records)
    report = {'finished_at':now(),'directory_pages':directory_report,'discovered_clubs':len(records),
              'processed_clubs':len(enriched),'unprocessed_clubs':len(records)-len(enriched),
              'pending_directory_pages':list(pending),'directory_limit_reached':bool(pending),
              'clubs_with_instagram':sum(bool(c['social_links'].get('instagram')) for c in records)}
    write_json(Path(output).with_name('club_discovery_report.json'),report)
    return records, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory-url',default='https://zotspot.uci.edu/club_signup')
    parser.add_argument('--directory-html',type=Path,help='Saved directory HTML for reproducible discovery')
    parser.add_argument('--output',type=Path,default=ROOT/'data/clubs/club_sources.json')
    parser.add_argument('--max-clubs',type=int,help='Only enrich this many clubs; all directory entries are retained')
    parser.add_argument('--max-directory-pages',type=int,default=3)
    parser.add_argument('--pages-per-club',type=int,default=3)
    parser.add_argument('--delay',type=float,default=2)
    args=parser.parse_args()
    if args.max_clubs is not None and args.max_clubs < 0 or args.max_directory_pages<1 or args.pages_per_club<1:
        parser.error('Limits must be positive; --max-clubs can be zero for directory-only discovery')
    _, report=discover(PublicClient(delay=args.delay),args.directory_url,args.output,args.max_clubs,args.max_directory_pages,args.pages_per_club,args.directory_html)
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
