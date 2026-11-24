// Dependency-free feed, filtering, security and failure-state regression tests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '..');
const code = fs.readFileSync(path.join(root, 'app.js'), 'utf8');
const feed = JSON.parse(fs.readFileSync(path.join(root, 'data/output/unified_events.json'), 'utf8'));

async function createApp(fetcher, protocol = 'http:') {
  const nodes = {};
  const get = id => nodes[id] ||= {textContent: '', innerHTML: '', hidden: false, value: id === 'eventPeriod' ? 'upcoming' : '', checked: false,
    handlers: {}, addEventListener(name, fn) { this.handlers[name] = fn; }, querySelectorAll() { return []; }};
  class FixedDate extends Date { static now() { return Date.parse('2026-11-16T20:00:00Z'); } }
  const context = vm.createContext({document: {getElementById: get}, location: {protocol}, fetch: fetcher,
    Date: FixedDate, URL, Intl, AbortController, setTimeout, clearTimeout, console});
  vm.runInContext(code, context);
  await new Promise(resolve => setImmediate(resolve));
  return {nodes, run: code => vm.runInContext(code, context)};
}
const response = data => async () => ({ok: true, json: async () => data});

async function run() {
  const app = await createApp(response(feed));
  assert.equal(app.run('UCI_EVENTS.length'), feed.length);
  assert.equal(app.run('feedState'), 'ready');
  assert.ok(app.nodes.cardGrid.innerHTML.includes('View on ZotSpot'));
  assert.ok(!app.nodes.cardGrid.innerHTML.includes('Demo listing'));
  const ongoing = await createApp(response([{id:'long',title:'Ongoing service',source:'zotspot', start_datetime:'2021-06-28T00:00:00-07:00', end_datetime:'2028-01-01T10:00:00-08:00'}]));
  assert.equal(ongoing.run('getFilteredListings().length'), 1, 'ongoing multi-year event stays visible');
  app.run("eventPeriod.value = 'all'; render();");
  assert.equal(app.run('getFilteredListings().length'), feed.length);
  app.run("eventPeriod.value = 'past'; render();");
  assert.ok(app.run('getFilteredListings().every(isPastEvent)'));
  app.run("eventPeriod.value = 'all'; searchText = 'zzzz-no-such-event'; render();");
  assert.equal(app.nodes.emptyState.hidden, false);
  app.nodes.clearFiltersBtn.handlers.click();
  assert.equal(app.run('getFilteredListings().length'), feed.length);
  app.run("searchText = UCI_EVENTS[0].organizer.toLowerCase(); render();");
  assert.ok(app.run('getFilteredListings().some(item => item.id === UCI_EVENTS[0].id)'));
  app.run("searchText = ''; showDemos.checked = true; activeCategories.clear(); render();");
  assert.equal(app.run('LISTINGS.length'), feed.length + 18);
  assert.ok(app.nodes.cardGrid.innerHTML.includes('Demo listing'));
  assert.equal(app.run("safeContact('javascript:alert(1)')"), '');
  assert.throws(() => app.run("normalizeFeed([{id:'1',title:'bad', start_datetime:'2026-11-17T18:00:00'}])"), /timezone offsets/);
  assert.throws(() => app.run('normalizeFeed({})'), /JSON array/);
  assert.equal(app.run('normalizeFeed([]).length'), 0);

  const categorized = await createApp(response([
    {id:'workshop',title:'Skill session',source:'zotspot', categories:['Workshop'], tags:['Workshop','Networking','networking'], start_datetime:'2026-12-01T18:00:00-08:00', end_datetime:'2026-12-01T20:00:00-08:00'},
    {id:'social',title:'Meet students',source:'zotspot', categories:['Social'], tags:['Games'], start_datetime:'2026-12-02T18:00:00-08:00'}
  ]));
  assert.match(categorized.nodes.eventCategoryFilter.innerHTML, /Workshop \(1\)/);
  assert.ok(categorized.nodes.cardGrid.innerHTML.includes('>Workshop</span>'));
  assert.ok(categorized.nodes.cardGrid.innerHTML.includes('>Networking</span>'));
  assert.ok(!categorized.nodes.cardGrid.innerHTML.includes('>Clubs</span>'));
  assert.ok(!categorized.nodes.cardGrid.innerHTML.includes('>Events</span>'));
  assert.equal(categorized.run('UCI_EVENTS[0].displayTags.length'), 2);
  categorized.nodes.eventCategoryFilter.value = 'Workshop';
  categorized.nodes.eventCategoryFilter.handlers.change();
  assert.equal(categorized.run('getFilteredListings().length'), 1);
  assert.ok(!categorized.nodes.cardGrid.innerHTML.includes('Meet students'));
  categorized.nodes.clearFiltersBtn.handlers.click();
  assert.equal(categorized.nodes.eventCategoryFilter.value, '');
  assert.equal(categorized.run('getFilteredListings().length'), 2);
  categorized.run("searchText = 'Networking'; render();");
  assert.equal(categorized.run('getFilteredListings().length'), 1);
  const allDay = await createApp(response([{id:'day',title:'Day event',source:'zotspot', all_day:true, start_datetime:'2026-12-01T00:00:00-08:00', end_datetime:'2026-12-01T23:59:59-08:00'}]));
  assert.ok(allDay.nodes.cardGrid.innerHTML.includes('Dec 1, 2026 (all day)'));
  assert.ok(!allDay.nodes.cardGrid.innerHTML.includes('12:00 AM'));

  const publicFeeds = await createApp(response([
    {id:'cal',title:'Calendar workshop',source:'club_calendar',organizer_name:'Club A',categories:['Workshop'],tags:['Career'],start_datetime:'2026-11-17T18:00:00-08:00',end_datetime:'2026-11-17T19:00:00-08:00',rsvp_url:'https://club.example/calendar'},
    {id:'news',title:'Newsletter talk',source:'club_newsletter',organizer_name:'Club B',categories:['Talk'],tags:['Research'],start_datetime:'2026-11-18T12:00:00-08:00',source_url:'https://club.example/newsletter/talk'}
  ]));
  assert.match(publicFeeds.nodes.cardGrid.innerHTML, /Public calendar/);
  assert.match(publicFeeds.nodes.cardGrid.innerHTML, /Club newsletter/);
  assert.match(publicFeeds.nodes.cardGrid.innerHTML, /View official event/);
  publicFeeds.run("eventPeriod.value = 'tomorrow'; tagSearch.value = 'career'; render();");
  assert.equal(publicFeeds.run('getFilteredListings()[0].title'), 'Calendar workshop');
  publicFeeds.nodes.resetFiltersBtn.handlers.click();
  publicFeeds.run("searchText = 'Club B'; eventCategoryFilter.value = 'Talk'; render();");
  assert.equal(publicFeeds.run('getFilteredListings()[0].title'), 'Newsletter talk');

  // Tag input is independent from broad text search and intersects with category.
  categorized.run("searchText = ''; eventCategoryFilter.value = ''; tagSearch.value = 'network'; render();");
  assert.equal(categorized.run('getFilteredListings().length'), 1);
  assert.match(categorized.nodes.activeFilters.textContent, /Tag: “network”/);
  categorized.run("eventCategoryFilter.value = 'Social'; render();");
  assert.equal(categorized.nodes.emptyState.hidden, false);
  assert.match(categorized.nodes.eventCategoryFilter.innerHTML, /Social \(0 matching \/ 1 total\)/);
  categorized.nodes.resetFiltersBtn.handlers.click();
  assert.equal(categorized.run('getFilteredListings().length'), 2);
  assert.equal(categorized.nodes.tagSearch.value, '');

  // Unsorted source data, UTC/Pacific day difference, midnight and overnight ranges.
  const timed = await createApp(response([
    {id:'late',title:'Evening',source:'zotspot',categories:['Social'],tags:['Community'], start_datetime:'2026-11-17T19:00:00-08:00',end_datetime:'2026-11-17T20:00:00-08:00'},
    {id:'morning',title:'Morning',source:'zotspot',categories:['Workshop'],tags:['Career'], start_datetime:'2026-11-17T09:00:00-08:00',end_datetime:'2026-11-17T10:00:00-08:00'},
    {id:'utc',title:'Pacific previous day',source:'zotspot',categories:['Social'], start_datetime:'2026-11-17T01:00:00Z',end_datetime:'2026-11-17T02:00:00Z'},
    {id:'past',title:'Past',source:'zotspot',categories:['Workshop'], start_datetime:'2026-11-15T10:00:00-08:00'},
    {id:'overnight',title:'Overnight',source:'zotspot',categories:['Social'], start_datetime:'2026-11-16T23:00:00-08:00',end_datetime:'2026-11-17T02:00:00-08:00'},
    {id:'week',title:'Day seven',source:'zotspot',categories:['Social'], start_datetime:'2026-11-22T12:00:00-08:00'},
    {id:'outside',title:'Day eight',source:'zotspot',categories:['Social'], start_datetime:'2026-11-23T12:00:00-08:00'},
    {id:'missing',title:'Undated',source:'zotspot',categories:['Social']}
  ]));
  timed.run("eventPeriod.value = 'all'; render();");
  assert.equal(timed.run('getFilteredListings().map(item=>item.id).join(",")'), 'zotspot:past,zotspot:utc,zotspot:overnight,zotspot:morning,zotspot:late,zotspot:week,zotspot:outside,zotspot:missing');
  assert.match(timed.nodes.cardGrid.innerHTML, /Monday, November 16, 2026 · Today/);
  assert.match(timed.nodes.cardGrid.innerHTML, /Tuesday, November 17, 2026 · Tomorrow/);
  assert.equal((timed.nodes.cardGrid.innerHTML.match(/Tuesday, November 17, 2026/g) || []).length, 1, 'same-day events share one heading');
  assert.ok(timed.nodes.cardGrid.innerHTML.indexOf('>Morning</h3>') < timed.nodes.cardGrid.innerHTML.indexOf('>Evening</h3>'));
  assert.ok(timed.nodes.cardGrid.innerHTML.includes('class="event-when"'));
  timed.run("eventPeriod.value = 'today'; render();");
  assert.equal(timed.run('getFilteredListings().length'), 2);
  timed.run("eventPeriod.value = 'tomorrow'; render();");
  assert.equal(timed.run('getFilteredListings().length'), 3, 'includes overlapping overnight event');
  timed.run("eventPeriod.value = 'next7'; render();");
  assert.equal(timed.run('getFilteredListings().length'), 5);
  timed.run("eventPeriod.value = 'all'; dateFrom.value = '2026-11-17'; dateTo.value = '2026-11-17'; render();");
  assert.equal(timed.run('getFilteredListings().length'), 3);
  timed.run("timeOfDay.value = 'morning'; render();");
  assert.equal(timed.run('getFilteredListings()[0].title'), 'Morning');
  timed.run("timeOfDay.value = 'evening'; render();");
  assert.equal(timed.run('getFilteredListings()[0].title'), 'Evening');
  timed.run("timeOfDay.value = 'night'; render();");
  assert.equal(timed.run('getFilteredListings()[0].title'), 'Overnight');
  timed.run("dateFrom.value = '2026-11-20'; dateTo.value = '2026-11-17'; render();");
  assert.equal(timed.nodes.filterError.hidden, false);
  assert.equal(timed.nodes.cardGrid.hidden, true);
  timed.nodes.resetFiltersBtn.handlers.click();
  assert.equal(timed.nodes.filterError.hidden, true);
  assert.equal(timed.run('getFilteredListings().length'), 8);
  timed.run("eventPeriod.value = 'upcoming'; dateFrom.value = '2026-11-15'; dateTo.value = '2026-11-15';");
  timed.nodes.dateFrom.handlers.input();
  assert.equal(timed.nodes.eventPeriod.value, 'all', 'explicit date range replaces preset');
  assert.equal(timed.run('getFilteredListings()[0].title'), 'Past');
  assert.equal(timed.run("addDays('2026-11-01', 1)"), '2026-11-02');
  assert.equal(timed.run("dayKey('2026-11-17T01:00:00Z')"), '2026-11-16');

  // Reproduce the reported category issue: an active keyword narrows every category.
  app.nodes.resetFiltersBtn.handlers.click();
  app.run("searchText = 'leadership'; render();");
  assert.equal(app.run('getFilteredListings().length'), 13);
  assert.match(app.nodes.activeFilters.textContent, /Search: “leadership”/);
  app.nodes.resetFiltersBtn.handlers.click();
  assert.equal(app.run('getFilteredListings().length'), feed.length);
  for (const category of new Set(feed.flatMap(item => item.categories))) {
    app.nodes.eventCategoryFilter.value = category;
    app.nodes.eventCategoryFilter.handlers.change();
    const expected = feed.filter(item => item.categories.includes(category)).length;
    assert.equal(app.run('getFilteredListings().length'), expected, category);
  }

  const hostile = await createApp(response([{id:'hostile',title:'<img src=x onerror=alert(1)>',source:'club-site', source_url:'javascript:alert(1)', start_datetime:'2026-12-01T18:00:00-08:00'}]));
  assert.ok(hostile.nodes.cardGrid.innerHTML.includes('&lt;img'));
  assert.ok(!hostile.nodes.cardGrid.innerHTML.includes('href="javascript:'));
  assert.ok(hostile.nodes.cardGrid.innerHTML.includes('Official link not provided'));

  const undated = await createApp(response([{id:'unknown',title:'TBA',source:'club-site'}]));
  assert.equal(undated.nodes.emptyState.hidden, false);
  undated.run("eventPeriod.value = 'undated'; render();");
  assert.ok(undated.nodes.cardGrid.innerHTML.includes('Date to be confirmed'));

  const empty = await createApp(response([]));
  assert.equal(empty.nodes.emptyState.hidden, false);
  const broken = await createApp(async () => ({ok: false, status: 404}));
  assert.equal(broken.nodes.feedError.hidden, false);
  assert.equal(broken.nodes.emptyState.hidden, true);
  assert.match(broken.nodes.feedErrorMessage.textContent, /404/);
  broken.run("fetch = async () => ({ok:true,json:async()=>[]});");
  await broken.nodes.retryFeed.handlers.click();
  assert.equal(broken.run('feedState'), 'ready');
  assert.equal(broken.nodes.feedError.hidden, true);
  const malformed = await createApp(async () => ({ok:true, json:async () => {throw new SyntaxError('Invalid JSON');}}));
  assert.match(malformed.nodes.feedErrorMessage.textContent, /Invalid JSON/);
  const local = await createApp(async () => {throw new Error('Failed to fetch');}, 'file:');
  assert.match(local.nodes.feedErrorMessage.textContent, /web server/);
  return 'Passed: tag-only search, visible active filters, all 27 categories, date windows/ranges, time-of-day filters, chronological ordering, Pacific date headings, original category badges, topic tags, category filtering and counts, all-day display, real feed loading, ongoing/past/undated filters, search, empty states, optional demos, safe rendering, bad dates, malformed JSON, HTTP errors, retry and file startup guidance.';
}
module.exports = run;
if (require.main === module) run().then(console.log).catch(error => {console.error(error); process.exitCode = 1;});
