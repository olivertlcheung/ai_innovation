const DEMO_LISTINGS = [
  {"id":"1","title":"ASUCI General Club Fair","categories":["Clubs","Events"],"description":"Explore 100+ student organizations, grab free swag, and sign up for clubs that match your interests.","datetime":"Oct 29, 2025, 11:00 AM","location":"Ring Road, Main Campus","contact":"https://asuci.uci.edu/clubfair","source":"Club Website"},
  {"id":"2","title":"Part-Time Barista — Anteatery Café","categories":["Jobs"],"description":"On-campus café hiring part-time baristas. Flexible shifts, work-study eligible, training provided.","datetime":null,"location":"Anteatery, Student Center","contact":"https://jobs.uci.edu/listing/4821","source":"Career Center"},
  {"id":"3","title":"FRESH Basic Needs Hub — Free Groceries","categories":["Basic Needs"],"description":"Weekly grocery distribution for students facing food insecurity. No application needed, just bring your student ID.","datetime":"Every Tuesday, 10:00 AM - 2:00 PM","location":"FRESH Basic Needs Hub, G319 Student Center","contact":"fresh@uci.edu","source":"Canvas"},
  {"id":"4","title":"Subleaser Needed — Studio Near Campus","categories":["Housing"],"description":"Winter quarter sublease available, 5 min walk to campus, furnished studio, utilities included.","datetime":null,"location":"Camino Del Sol Apartments","contact":"subleasestudent@gmail.com","source":"Instagram"},
  {"id":"5","title":"Fall Career & Internship Fair","categories":["Career Fairs","Jobs"],"description":"Meet recruiters from 80+ companies hiring for internships and full-time roles across all majors.","datetime":"Nov 5, 2025, 10:00 AM - 3:00 PM","location":"Bren Events Center","contact":"https://career.uci.edu/fall-fair","source":"Career Center"},
  {"id":"6","title":"Mindfulness & Stress Relief Workshop","categories":["Health/Wellness"],"description":"Guided meditation and breathing exercises to help manage midterm stress. Open to all students.","datetime":"Oct 31, 2025, 4:00 PM","location":"Student Health Center, Room 201","contact":"wellness@uci.edu","source":"Student Health Center"},
  {"id":"7","title":"Computer Science Club Weekly Meeting","categories":["Clubs"],"description":"Weekly meetup for CS students: coding challenges, project showcases, and guest speaker talks.","datetime":"Every Wednesday, 6:00 PM","location":"DBH 1300","contact":"https://csclub.ics.uci.edu","source":"Club Website"},
  {"id":"8","title":"Campus Food Pantry Volunteer Opportunity","categories":["Basic Needs","Jobs"],"description":"Volunteer hours available for students who want to help stock and distribute food at the pantry.","datetime":null,"location":"FRESH Basic Needs Hub","contact":"fresh-volunteer@uci.edu","source":"Canvas"},
  {"id":"9","title":"Roommate Wanted — 2BR Apartment","categories":["Housing"],"description":"Looking for a clean, quiet roommate to share a 2-bedroom apartment starting Winter quarter. $900/month.","datetime":null,"location":"University Hills","contact":"roommatewanted@uci.edu","source":"Instagram"},
  {"id":"10","title":"Free Flu Shot Clinic","categories":["Health/Wellness","Events"],"description":"Free flu vaccinations for all students with valid student ID. Walk-ins welcome, no appointment needed.","datetime":"Nov 3, 2025, 9:00 AM - 1:00 PM","location":"Student Health Center Lobby","contact":"https://shc.uci.edu/flu","source":"Student Health Center"},
  {"id":"11","title":"Women in STEM Networking Night","categories":["Clubs","Career Fairs"],"description":"Connect with alumnae and industry professionals in STEM fields over dinner and casual networking.","datetime":"Nov 7, 2025, 6:00 PM","location":"Calit2 Auditorium","contact":"https://wistem.uci.edu/networking","source":"Club Website"},
  {"id":"12","title":"Resident Assistant (RA) Hiring","categories":["Jobs","Housing"],"description":"Housing office hiring RAs for next academic year. Free housing + stipend included. Applications due soon.","datetime":"Applications due Dec 1, 2025","location":"Housing Administration Office","contact":"https://housing.uci.edu/ra-jobs","source":"Canvas"},
  {"id":"13","title":"Late Night Study Jam & Free Snacks","categories":["Events","Basic Needs"],"description":"Finals prep event with free coffee, snacks, and quiet study space open until 2 AM.","datetime":"Dec 8, 2025, 8:00 PM - 2:00 AM","location":"Langson Library","contact":"https://library.uci.edu/latenight","source":"Instagram"},
  {"id":"14","title":"Peer Tutoring Program Sign-Up","categories":["Basic Needs","Clubs"],"description":"Free peer tutoring for math, chemistry, and physics courses. Sign up for weekly sessions.","datetime":null,"location":"Learning & Academic Resource Center","contact":"https://larc.sa.uci.edu","source":"Canvas"},
  {"id":"15","title":"Tech Company Info Session — DataCore Inc.","categories":["Career Fairs","Jobs"],"description":"Info session with Q&A about internship and new-grad software engineering roles. Pizza provided.","datetime":"Nov 12, 2025, 5:30 PM","location":"Engineering Hall 2430","contact":"https://career.uci.edu/datacore-infosession","source":"Career Center"},
  {"id":"16","title":"Yoga on the Lawn","categories":["Health/Wellness","Events"],"description":"Free weekly outdoor yoga session for all skill levels. Mats provided, just bring water.","datetime":"Every Friday, 3:00 PM","location":"Aldrich Park","contact":"wellness@uci.edu","source":"Instagram"},
  {"id":"17","title":"Emergency Housing Assistance Program","categories":["Housing","Basic Needs"],"description":"Short-term emergency housing support for students facing unexpected housing insecurity.","datetime":null,"location":"Dean of Students Office","contact":"deanofstudents@uci.edu","source":"Canvas"},
  {"id":"18","title":"Anteater Entrepreneurship Club Pitch Night","categories":["Clubs","Events"],"description":"Student founders pitch their startups to peers and local investors. Open to all majors, free admission.","datetime":"Nov 14, 2025, 7:00 PM","location":"The Cove, Student Center","contact":"https://aec.uci.edu/pitchnight","source":"Club Website"}
];

let UCI_EVENTS = [];
let LISTINGS = [];
let feedState = 'loading';
const activeCategories = new Set(['Events']);
const eventPeriod = document.getElementById('eventPeriod');
const showDemos = document.getElementById('showDemos');
const eventCategoryFilter = document.getElementById('eventCategoryFilter');
const tagSearch = document.getElementById('tagSearch');
const dateFrom = document.getElementById('dateFrom');
const dateTo = document.getElementById('dateTo');
const timeOfDay = document.getElementById('timeOfDay');
[tagSearch, timeOfDay].forEach(control => control.addEventListener('input', render));
[dateFrom, dateTo].forEach(control => control.addEventListener('input', () => {
  eventPeriod.value = 'all';
  render();
}));
timeOfDay.addEventListener('change', render);
showDemos.addEventListener('change', () => {
  if (!showDemos.checked) {
    activeCategories.clear();
    activeCategories.add('Events');
  }
  render();
});
eventCategoryFilter.addEventListener('change', render);
eventPeriod.addEventListener('change', render);

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
}

function safeContact(value) {
  if (isEmail(value)) return `mailto:${value}`;
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) ? url.href : '';
  } catch { return ''; }
}

function eventDate(value, dateOnly = false) {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Los_Angeles', dateStyle: 'medium', ...(dateOnly ? {} : {timeStyle: 'short'})
  }).format(new Date(value));
}

function uniqueLabels(values) {
  const seen = new Set();
  return values.filter(value => typeof value === 'string').map(value => value.trim()).filter(value => {
    const key = value.toLowerCase();
    if (!value || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function updateEventCategoryFilter() {
  const selected = eventCategoryFilter.value;
  const totals = new Map(), matching = new Map();
  UCI_EVENTS.forEach(item => item.sourceCategories.forEach(category => totals.set(category, (totals.get(category) || 0) + 1)));
  getFilteredListings(true).filter(item => item.isEvent).forEach(item => item.sourceCategories.forEach(category => matching.set(category, (matching.get(category) || 0) + 1)));
  eventCategoryFilter.innerHTML = '<option value="">All event categories</option>' +
    [...totals].sort(([a], [b]) => a.localeCompare(b)).map(([category, total]) => {
      const count = matching.get(category) || 0;
      const label = count === total ? String(total) : `${count} matching / ${total} total`;
      return `<option value="${escapeHtml(category)}">${escapeHtml(category)} (${label})</option>`;
    }).join('');
  eventCategoryFilter.value = totals.has(selected) ? selected : '';
}

function updateActiveFilters() {
  const filters = [];
  if (searchText.trim()) filters.push(`Search: “${searchText.trim()}”`);
  if (tagSearch.value.trim()) filters.push(`Tag: “${tagSearch.value.trim()}”`);
  if (eventCategoryFilter.value) filters.push(`Category: ${eventCategoryFilter.value}`);
  const periods = {upcoming: 'Upcoming & ongoing', today: 'Today', tomorrow: 'Tomorrow', next7: 'Next 7 days', past: 'Past events', undated: 'Dates unconfirmed'};
  if (periods[eventPeriod.value]) filters.push(`Dates: ${periods[eventPeriod.value]}`);
  if (dateFrom.value) filters.push(`From: ${dateFrom.value}`);
  if (dateTo.value) filters.push(`Through: ${dateTo.value}`);
  if (timeOfDay.value) filters.push(`Start time: ${timeOfDay.value}`);
  const groups = [...activeCategories].filter(category => category !== 'Events');
  if (groups.length) filters.push(`Resource groups: ${groups.join(', ')}`);
  document.getElementById('activeFilters').textContent = filters.length
    ? `Active filters — ${filters.join(' · ')}`
    : 'No active search, tag, category or time filters.';
}

const PACIFIC = 'America/Los_Angeles';
function dayKey(value) {
  const parts = new Intl.DateTimeFormat('en-US', {timeZone: PACIFIC, year: 'numeric', month: '2-digit', day: '2-digit'}).formatToParts(new Date(value));
  const part = type => parts.find(value => value.type === type).value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

function addDays(key, count) {
  // Calendar arithmetic, not 24-hour arithmetic across daylight saving changes.
  return new Date(Date.parse(key + 'T12:00:00Z') + count * 86400000).toISOString().slice(0, 10);
}

function overlapsDates(item, first, last) {
  if (!item.start) return false;
  const start = dayKey(item.start);
  const end = dayKey(item.end || item.start);
  return (!first || end >= first) && (!last || start <= last);
}

function matchesTimeFilters(item) {
  if (!item.isEvent) return !dateFrom.value && !dateTo.value && !timeOfDay.value;
  const today = dayKey(Date.now());
  let matchesPeriod;
  switch (eventPeriod.value) {
    case 'all': matchesPeriod = true; break;
    case 'past': matchesPeriod = isPastEvent(item); break;
    case 'undated': matchesPeriod = !item.start; break;
    case 'today': matchesPeriod = overlapsDates(item, today, today); break;
    case 'tomorrow': matchesPeriod = overlapsDates(item, addDays(today, 1), addDays(today, 1)); break;
    case 'next7': matchesPeriod = overlapsDates(item, today, addDays(today, 6)); break;
    default: matchesPeriod = Boolean(item.start) && !isPastEvent(item);
  }
  if (!matchesPeriod) return false;
  if ((dateFrom.value || dateTo.value) && !overlapsDates(item, dateFrom.value, dateTo.value)) return false;
  if (timeOfDay.value) {
    // A source's multi-day range does not tell us each session's time. Use start time only.
    if (!item.start || item.allDay) return false;
    const hour = Number(new Intl.DateTimeFormat('en-US', {timeZone: PACIFIC, hour: 'numeric', hourCycle: 'h23'}).format(new Date(item.start)));
    const periods = {morning: [6, 12], afternoon: [12, 17], evening: [17, 21], night: [21, 30]};
    const [first, last] = periods[timeOfDay.value] || [0, 24];
    const normalizedHour = timeOfDay.value === 'night' && hour < 6 ? hour + 24 : hour;
    if (normalizedHour < first || normalizedHour >= last) return false;
  }
  return true;
}

function dayHeading(item) {
  if (!item.isEvent) return 'Demo resources';
  if (!item.start) return 'Dates to be confirmed';
  const date = new Intl.DateTimeFormat('en-US', {timeZone: PACIFIC, weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'}).format(new Date(item.start));
  const key = dayKey(item.start), today = dayKey(Date.now());
  return `${date}${key === today ? ' · Today' : key === addDays(today, 1) ? ' · Tomorrow' : ''}`;
}

function updateTagSuggestions() {
  const tags = uniqueLabels(UCI_EVENTS.flatMap(item => item.tags)).sort((a, b) => a.localeCompare(b));
  document.getElementById('tagSuggestions').innerHTML = tags.map(tag => `<option value="${escapeHtml(tag)}"></option>`).join('');
}

function isPastEvent(item) {
  return Boolean(item.start && new Date(item.end || item.start).getTime() < Date.now());
}
let searchText = "";

const searchInput = document.getElementById('searchInput');
const categoryFilters = document.getElementById('categoryFilters');
const resultsInfo = document.getElementById('resultsInfo');
const cardGrid = document.getElementById('cardGrid');
const emptyState = document.getElementById('emptyState');
const clearFiltersBtn = document.getElementById('clearFiltersBtn');

function isEmail(str) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(str);
}

function getFilteredListings(ignoreEventCategory = false) {
  return LISTINGS.filter(item => {
    const text = [item.title, item.description, item.organizer, item.location, ...(item.tags || [])].join(' ').toLowerCase();
    const matchesSearch = text.includes(searchText.toLowerCase());
    const matchesCategory = activeCategories.size === 0 ||
      item.categories.some(cat => activeCategories.has(cat));
    const matchesPeriod = matchesTimeFilters(item);
    const query = tagSearch.value.trim().toLowerCase();
    const matchesTag = !query || (item.tags || item.categories).some(tag => tag.toLowerCase().includes(query));
    const matchesEventCategory = ignoreEventCategory || !eventCategoryFilter.value ||
      (item.isEvent && item.sourceCategories.includes(eventCategoryFilter.value));
    return matchesSearch && matchesCategory && matchesPeriod && matchesEventCategory && matchesTag;
  }).sort((a, b) => {
    if (!a.isEvent || !b.isEvent) return Number(Boolean(b.isEvent)) - Number(Boolean(a.isEvent));
    if (!a.start || !b.start) return Number(Boolean(b.start)) - Number(Boolean(a.start));
    return new Date(a.start) - new Date(b.start) || a.title.localeCompare(b.title) || a.id.localeCompare(b.id);
  });
}

function renderCards(listings) {
  resultsInfo.textContent = `Showing ${listings.length} of ${LISTINGS.length} loaded listings`;

  if (listings.length === 0) {
    cardGrid.hidden = true;
    emptyState.hidden = false;
    cardGrid.innerHTML = '';
    return;
  }

  cardGrid.hidden = false;
  emptyState.hidden = true;

  const groups = new Map();
  listings.forEach(item => {
    const key = !item.isEvent ? 'demo' : item.start ? dayKey(item.start) : 'undated';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });

  function cardHtml(item) {
    const tagsHtml = (item.isEvent ? item.displayTags : item.categories).map((cat, i) => {
      const cls = item.isEvent ? (item.sourceCategories.includes(cat) ? 'blue-bg' : 'yellow-bg') : (i % 2 === 0 ? 'blue-bg' : 'yellow-bg');
      return `<span class="tag ${cls}">${escapeHtml(cat)}</span>`;
    }).join('');

    const dateLabel = item.isEvent && item.start
      ? `${eventDate(item.start, item.allDay)}${item.end && (!item.allDay || eventDate(item.end, true) !== eventDate(item.start, true)) ? ' – ' + (item.allDay || dayKey(item.start) !== dayKey(item.end) ? eventDate(item.end, item.allDay) : new Intl.DateTimeFormat('en-US', {timeZone: PACIFIC, timeStyle: 'short'}).format(new Date(item.end))) : ''}${item.allDay ? ' (all day)' : ' PT'}`
      : item.datetime;
    const datetimeRow = dateLabel
      ? `<div class="event-when"><strong>When</strong><span>${escapeHtml(dateLabel)}</span></div>`
      : '';

    const contactHref = safeContact(item.contact);
    const contactLabel = item.isEvent ? (item.source === 'ZotSpot' ? 'View on ZotSpot ↗' : 'View official event ↗') : isEmail(item.contact) ? 'Email' : 'Visit Link';

    return `
      <div class="card">
        <h3>${escapeHtml(item.title)}</h3>
        ${datetimeRow}
        <div class="tags">${tagsHtml}</div>
        <p class="desc">${escapeHtml(item.description)}</p>
        ${item.isEvent ? `<div class="meta-row"><strong>Organizer:</strong> ${escapeHtml(item.organizer)}</div><div class="meta-row">${!item.start ? 'Date to be confirmed' : isPastEvent(item) ? 'Past event' : 'Upcoming / ongoing'}${item.cost ? ' · ' + escapeHtml(item.cost) : ''}</div>` : '<div class="meta-row">Demo listing</div>'}
        <div class="meta-row"><strong>Where:</strong> ${escapeHtml(item.location)}</div>
        ${contactHref ? `<a class="contact-link" href="${escapeHtml(contactHref)}" target="_blank" rel="noopener noreferrer">${contactLabel}</a>` : '<p class="meta-row">Official link not provided</p>'}
        <div class="via-source">via ${escapeHtml(item.source)}</div>
      </div>
    `;
  }
  cardGrid.innerHTML = [...groups].map(([key, items], index) => `
    <section class="date-group" aria-labelledby="day-${index}">
      <h2 class="date-heading" id="day-${index}">${escapeHtml(dayHeading(items[0]))}<span>${items.length} ${items.length === 1 ? 'listing' : 'listings'}</span></h2>
      <div class="day-grid">${items.map(cardHtml).join('')}</div>
    </section>`).join('');
}

function render() {
  if (feedState !== 'ready') {
    cardGrid.hidden = true;
    emptyState.hidden = true;
    resultsInfo.textContent = feedState === 'loading' ? 'Loading UCI events…' : 'Event feed unavailable';
    return;
  }
  updateActiveFilters();
  const invalidRange = Boolean(dateFrom.value && dateTo.value && dateFrom.value > dateTo.value);
  document.getElementById('filterError').hidden = !invalidRange;
  if (invalidRange) {
    cardGrid.hidden = true;
    emptyState.hidden = true;
    resultsInfo.textContent = 'Choose a valid date range to see events.';
    return;
  }
  updateFilterButtonStates();
  LISTINGS = showDemos.checked ? [...UCI_EVENTS, ...DEMO_LISTINGS] : UCI_EVENTS;
  updateEventCategoryFilter();
  const filtered = getFilteredListings();
  renderCards(filtered);
}

searchInput.addEventListener('input', (e) => {
  searchText = e.target.value;
  render();
});

categoryFilters.addEventListener('click', (e) => {
  const btn = e.target.closest('.filter-btn');
  if (!btn) return;

  const category = btn.dataset.category;

  if (category === 'All') {
    activeCategories.clear();
  } else {
    if (activeCategories.has(category)) {
      activeCategories.delete(category);
    } else {
      activeCategories.add(category);
    }
  }

  updateFilterButtonStates();
  render();
});

function updateFilterButtonStates() {
  const buttons = categoryFilters.querySelectorAll('.filter-btn');
  buttons.forEach(btn => {
    const cat = btn.dataset.category;
    btn.hidden = !['All', 'Events'].includes(cat) && !showDemos.checked;
    if (cat === 'All') {
      btn.classList.toggle('active', activeCategories.size === 0);
      btn.setAttribute('aria-pressed', String(activeCategories.size === 0));
    } else {
      btn.classList.toggle('active', activeCategories.has(cat));
      btn.setAttribute('aria-pressed', String(activeCategories.has(cat)));
    }
  });
}

function clearFilters() {
  searchText = '';
  searchInput.value = '';
  activeCategories.clear();
  eventPeriod.value = 'all';
  eventCategoryFilter.value = '';
  tagSearch.value = '';
  dateFrom.value = '';
  dateTo.value = '';
  timeOfDay.value = '';
  showDemos.checked = false;
  updateFilterButtonStates();
  render();
}
clearFiltersBtn.addEventListener('click', clearFilters);
document.getElementById('resetFiltersBtn').addEventListener('click', clearFilters);

function normalizeFeed(rows) {
  if (!Array.isArray(rows)) throw new Error('The event feed must contain a JSON array.');
  const seen = new Set();
  return rows.map(row => {
    if (!row || typeof row !== 'object' || !row.id || typeof row.title !== 'string' || !row.title.trim()) {
      throw new Error('An event is missing its id or title.');
    }
    for (const field of ['start_datetime', 'end_datetime']) {
      const value = row[field];
      if (value != null && (typeof value !== 'string' || !/(Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value)))) {
        throw new Error('Event dates need timezone offsets. Run scripts/sync_events.py to export the crawler JSON.');
      }
    }
    if (row.end_datetime && (!row.start_datetime || Date.parse(row.end_datetime) < Date.parse(row.start_datetime))) {
      throw new Error('An event has an invalid date range.');
    }
    const source = typeof row.source === 'string' ? row.source : 'unknown';
    const sourceCategories = uniqueLabels(Array.isArray(row.categories) ? row.categories : []);
    const topics = uniqueLabels(Array.isArray(row.tags) ? row.tags : []);
    const displayTags = uniqueLabels([...sourceCategories, ...topics]);
    return {
      id: `${source}:${row.id}`, title: row.title,
      description: typeof row.description === 'string' ? row.description : '',
      start: row.start_datetime || null, end: row.end_datetime || null,
      categories: ['Events', ...sourceCategories], sourceCategories,
      displayTags: displayTags.length ? displayTags : ['Event'], tags: displayTags, allDay: row.all_day === true,
      location: row.location || 'Location not provided', organizer: row.organizer_name || 'Organizer not provided',
      contact: safeContact(row.rsvp_url || '') || safeContact(row.source_url || ''),
      source: new Map([['zotspot', 'ZotSpot'], ['club_calendar', 'Public calendar'], ['club_newsletter', 'Club newsletter'], ['club_website', 'Club website']]).get(source) || source, cost: row.cost || '',
      lastUpdated: typeof row.last_updated === 'string' ? row.last_updated : '', isEvent: true
    };
  }).filter(item => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

async function loadEvents() {
  feedState = 'loading';
  document.getElementById('feedError').hidden = true;
  document.getElementById('snapshotNote').textContent = '';
  render();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch('./data/output/unified_events.json', {cache: 'no-cache', signal: controller.signal});
    if (!response.ok) throw new Error(`The event file could not be loaded (HTTP ${response.status}).`);
    UCI_EVENTS = normalizeFeed(await response.json());
    updateTagSuggestions();
    feedState = 'ready';
    const dates = UCI_EVENTS.map(item => item.lastUpdated.slice(0, 10)).filter(value => /^\d{4}-\d{2}-\d{2}$/.test(value)).sort();
    const updated = dates.length ? ` Latest record update: ${dates[dates.length - 1]}.` : '';
    document.getElementById('snapshotNote').textContent =
      `${UCI_EVENTS.length} events loaded from the saved event feed.${updated} Times shown in Pacific Time. Refreshing the page reads the latest published JSON; check the official source for current details.`;
  } catch (error) {
    feedState = 'error';
    UCI_EVENTS = [];
    document.getElementById('feedError').hidden = false;
    document.getElementById('feedErrorMessage').textContent = location.protocol === 'file:'
      ? 'To load the JSON event file, open this website through a web server. See the README for local startup instructions.'
      : `Unable to load UCI events. ${error.name === 'AbortError' ? 'The request timed out.' : error.message}`;
  } finally {
    clearTimeout(timeout);
    render();
  }
}

document.getElementById('retryFeed').addEventListener('click', loadEvents);
updateFilterButtonStates();
loadEvents();
