/**
 * TNFirefly Governor Race Tracker - Data Renderer
 * Fetches JSON from jsDelivr CDN and renders into page containers.
 * Shared across all dynamic pages.
 * 
 * Include via: <script src="https://cdn.jsdelivr.net/gh/LongDriveMarketing/tn-governor-race-2026@main/assets/data-renderer.js"></script>
 */

const DATA_BASE = 'https://cdn.jsdelivr.net/gh/LongDriveMarketing/tn-governor-race-2026@main/data';

async function fetchData(file) {
  try {
    const resp = await fetch(`${DATA_BASE}/${file}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch(e) {
    console.error(`Failed to fetch ${file}:`, e);
    return null;
  }
}

function fmtDate(d) {
  if (!d) return '';
  return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { year:'numeric', month:'long', day:'numeric' });
}
function fmtDateShort(d) {
  if (!d) return '';
  return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { year:'numeric', month:'short', day:'numeric' });
}
function fmtMonth(d) {
  if (!d) return '';
  return new Date(d + 'T12:00:00').toLocaleDateString('en-US', { year:'numeric', month:'long' });
}

/* ===========================
   NEWS PAGE RENDERER
   =========================== */
function renderNews(data, container) {
  if (!data || !data.articles) { container.innerHTML = '<p style="color:var(--text-dim)">Unable to load news data.</p>'; return; }
  
  const articles = data.articles;
  
  // Group by month
  const months = {};
  articles.forEach(a => {
    const m = fmtMonth(a.date);
    if (!months[m]) months[m] = [];
    months[m].push(a);
  });
  
  let html = '';
  
  // Filter bar
  html += `<div class="filter-bar">
    <button class="filter-btn active" data-filter="all">All</button>
    <button class="filter-btn" data-filter="tnfirefly">🔥 TNFirefly</button>
    <button class="filter-btn" data-filter="rep">Republican</button>
    <button class="filter-btn" data-filter="dem">Democrat</button>
    <button class="filter-btn" data-filter="policy">Policy</button>
    <button class="filter-btn" data-filter="finance">Finance</button>
  </div>`;
  
  for (const [month, arts] of Object.entries(months)) {
    html += `<div class="news-month-group"><h3 class="month-label">${month}</h3>`;
    arts.forEach(a => {
      const partyBorder = a.party === 'rep' ? '#c0392b' : a.party === 'dem' ? '#2980b9' : 'var(--gold)';
      const tnfClass = a.tnfirefly ? ' tnf-original' : '';
      const tags = (a.tags || []).join(' ');
      html += `
        <article class="news-card${tnfClass}" data-party="${a.party}" data-tags="${tags}" data-tnf="${a.tnfirefly}" style="border-left:3px solid ${partyBorder}">
          ${a.tnfirefly ? '<div class="tnf-label">🔥 TNFIREFLY ORIGINAL</div>' : ''}
          <div class="news-date">${fmtDateShort(a.date)} · ${a.source}</div>
          <h4 class="news-title">${a.url ? `<a href="${a.url}" target="_blank">${a.title}</a>` : a.title}</h4>
          <p class="news-summary">${a.summary}</p>
          ${a.candidate ? `<span class="news-tag">${a.candidate}</span>` : ''}
        </article>`;
    });
    html += '</div>';
  }
  
  container.innerHTML = html;
  
  // Wire up filter buttons
  container.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const f = btn.dataset.filter;
      container.querySelectorAll('.news-card').forEach(card => {
        if (f === 'all') { card.style.display = ''; return; }
        if (f === 'tnfirefly') { card.style.display = card.dataset.tnf === 'true' ? '' : 'none'; return; }
        if (f === 'rep' || f === 'dem') { card.style.display = card.dataset.party === f ? '' : 'none'; return; }
        card.style.display = card.dataset.tags.includes(f) ? '' : 'none';
      });
      // Hide empty month groups
      container.querySelectorAll('.news-month-group').forEach(g => {
        const visible = g.querySelectorAll('.news-card:not([style*="display: none"])');
        g.style.display = visible.length ? '' : 'none';
      });
    });
  });
}

/* ===========================
   ENDORSEMENTS PAGE RENDERER
   =========================== */
function renderEndorsements(data, container) {
  if (!data || !data.endorsements) { container.innerHTML = '<p style="color:var(--text-dim)">Unable to load endorsement data.</p>'; return; }
  
  const { candidates, endorsements, holdouts, analysis } = data;
  let html = '';
  
  // Score cards
  html += '<div class="score-row">';
  for (const [key, c] of Object.entries(candidates)) {
    const numClass = c.party === 'rep' ? 'rep-num' : c.party === 'dem' ? 'dem-num' : 'total-num';
    html += `<div class="score-card"><div class="score-num ${numClass}">${c.count}</div><div class="score-label">${c.name}</div></div>`;
  }
  if (holdouts) {
    html += `<div class="score-card"><div class="score-num total-num">${holdouts.length}+</div><div class="score-label">Notable Holdouts</div></div>`;
  }
  html += '</div>';
  
  // Group endorsements by candidate
  const grouped = {};
  endorsements.forEach(e => {
    if (!grouped[e.candidate]) grouped[e.candidate] = [];
    grouped[e.candidate].push(e);
  });
  
  for (const [key, c] of Object.entries(candidates)) {
    const cEnds = grouped[key] || [];
    const pClass = c.party === 'rep' ? 'rep' : 'dem';
    const initials = c.name.split(' ').map(w => w[0]).join('');
    
    html += `<div class="endorse-section">
      <div class="endorse-header">
        <div class="endorse-avatar ${pClass}">${initials}</div>
        <div class="endorse-header-info">
          <h2>${c.name}</h2>
          <div class="endorse-count">${c.count} ENDORSEMENTS · ${c.label.toUpperCase()}</div>
        </div>
      </div>
      <div class="endorse-grid">`;
    
    cEnds.forEach(e => {
      const cardClass = e.type === 'org' ? 'org' : pClass;
      const typeLabel = e.type === 'elected' ? 'Elected Official' : e.type === 'org' ? 'Organization' : e.type === 'notable' ? 'Notable Figure' : 'Political Signal';
      const typeClass = e.type === 'org' ? 'org-type' : e.type;
      html += `
        <div class="endorse-card ${cardClass}">
          <div class="endorse-name">${e.name}</div>
          <div class="endorse-role">${e.role}</div>
          <span class="endorse-type ${typeClass}">${typeLabel}</span>
          ${e.note ? `<div class="endorse-note">${e.note}</div>` : ''}
        </div>`;
    });
    
    html += '</div>';
    if (analysis && analysis[key]) {
      html += `<div class="analysis-box"><h4>TNFirefly Analysis</h4><p>${analysis[key]}</p></div>`;
    }
    html += '</div>';
  }
  
  // Holdouts
  if (holdouts && holdouts.length) {
    html += `<div class="endorse-section"><h2 style="color:var(--gold);margin-bottom:16px;">Notable Holdouts</h2><div class="endorse-grid">`;
    holdouts.forEach(h => {
      html += `<div class="endorse-card holdout">
        <div class="endorse-name">${h.name}</div>
        <div class="endorse-role">${h.role}</div>
        <span class="endorse-type holdout-type">Undeclared</span>
        ${h.note ? `<div class="endorse-note">${h.note}</div>` : ''}
      </div>`;
    });
    html += '</div></div>';
  }
  
  container.innerHTML = html;
}

/* ===========================
   TIMELINE PAGE RENDERER
   =========================== */
function renderTimeline(data, container) {
  if (!data || !data.events) { container.innerHTML = '<p style="color:var(--text-dim)">Unable to load timeline data.</p>'; return; }
  
  let html = '<div class="timeline-track">';
  
  data.events.forEach(ev => {
    const dotColor = ev.party === 'rep' ? '#c0392b' : ev.party === 'dem' ? '#2980b9' : ev.party === 'ind' ? '#7f8c8d' : 'var(--gold)';
    const futureClass = ev.future ? ' future-event' : '';
    const majorClass = ev.major ? ' major-event' : '';
    
    html += `
      <div class="tl-item${futureClass}${majorClass}">
        <div class="tl-dot" style="background:${dotColor}"></div>
        <div class="tl-content">
          <div class="tl-date">${fmtDate(ev.date)}${ev.future ? ' <span class="future-badge">UPCOMING</span>' : ''}</div>
          <h4 class="tl-title">${ev.title}</h4>
          <p class="tl-desc">${ev.desc}</p>
        </div>
      </div>`;
  });
  
  html += '</div>';
  container.innerHTML = html;
}

/* ===========================
   POLLS PAGE RENDERER
   =========================== */
function renderPolls(data, container) {
  if (!data) { container.innerHTML = '<p style="color:var(--text-dim)">Unable to load polling data.</p>'; return; }
  
  let html = '';
  
  // Race ratings
  if (data.raceRatings && data.raceRatings.length) {
    html += '<div class="ratings-row">';
    data.raceRatings.forEach(r => {
      html += `<div class="rating-card"><div class="rating-source">${r.source}</div><div class="rating-value">${r.rating}</div></div>`;
    });
    html += '</div>';
  }
  
  // Polls
  if (data.polls && data.polls.length) {
    data.polls.forEach(poll => {
      html += `
        <div class="poll-card">
          <div class="poll-header">
            <div class="poll-name">${poll.pollster}</div>
            <div class="poll-meta">${fmtDateShort(poll.date)} · ${poll.sampleSize} · MoE ${poll.margin}</div>
            <div class="poll-type">${poll.type === 'republican_primary' ? 'Republican Primary' : poll.type === 'democratic_primary' ? 'Democratic Primary' : 'General Election (Hypothetical)'}</div>
          </div>
          <div class="poll-bars">`;
      
      poll.results.forEach(r => {
        if (r.candidate === 'Undecided') {
          html += `<div class="poll-row undecided"><span class="poll-cand">Undecided</span><div class="poll-bar-track"><div class="poll-bar" style="width:${r.pct}%;background:#555"></div></div><span class="poll-pct">${r.pct}%</span></div>`;
        } else {
          const barColor = r.party === 'rep' ? '#c0392b' : r.party === 'dem' ? '#2980b9' : '#7f8c8d';
          html += `<div class="poll-row"><span class="poll-cand">${r.candidate}</span><div class="poll-bar-track"><div class="poll-bar" style="width:${r.pct}%;background:${barColor}"></div></div><span class="poll-pct">${r.pct}%</span></div>`;
        }
      });
      
      html += '</div></div>';
    });
  } else {
    html += '<div class="empty-state"><p>No public polls currently available.</p></div>';
  }
  
  // Analysis
  if (data.analysis) {
    html += `<div class="analysis-box"><h4>TNFirefly Analysis</h4><p>${data.analysis}</p></div>`;
  }
  
  container.innerHTML = html;
}

/* ===========================
   WATCHLIST PAGE RENDERER
   =========================== */
function renderWatchlist(data, container) {
  if (!data) { container.innerHTML = '<p style="color:var(--text-dim)">Unable to load watchlist data.</p>'; return; }
  
  let html = '';
  
  // Countdown
  if (data.filingDeadline) {
    html += '<div id="wl-countdown" class="countdown-box"></div>';
  }
  
  // Still Watching
  if (data.watching && data.watching.length) {
    html += '<h3 class="wl-section-title">👀 Still Watching</h3><div class="wl-grid">';
    data.watching.forEach(w => {
      const pClass = w.party === 'rep' ? 'rep' : w.party === 'dem' ? 'dem' : 'ind';
      const likelihood = w.likelihood || 0;
      const lLabel = likelihood >= 50 ? 'Moderate' : likelihood >= 25 ? 'Low' : 'Very Low';
      const statusBadge = w.status === 'possible' ? '<span class="wl-badge possible">Possible</span>' : '';
      html += `
        <div class="wl-card ${pClass}">
          <div class="wl-name">${w.name} ${statusBadge}</div>
          <div class="wl-role">${w.role}</div>
          <div class="wl-meter"><div class="wl-meter-label">Likelihood: ${lLabel}</div><div class="wl-meter-track"><div class="wl-meter-fill" style="width:${likelihood}%"></div></div></div>
          <p class="wl-detail">${w.detail}</p>
        </div>`;
    });
    html += '</div>';
  }
  
  // Declined
  if (data.declined && data.declined.length) {
    html += '<h3 class="wl-section-title" style="margin-top:40px;">✗ Declined / Running Elsewhere</h3><div class="wl-grid">';
    data.declined.forEach(d => {
      html += `
        <div class="wl-card declined">
          <div class="wl-name">${d.name}</div>
          <div class="wl-role">${d.role}</div>
          <div class="wl-status">${d.status}</div>
          <p class="wl-detail">${d.detail}</p>
        </div>`;
    });
    html += '</div>';
  }
  
  // Analysis boxes
  if (data.analysis) {
    if (data.analysis.trump) {
      html += `<div class="analysis-box"><h4>The Trump Factor</h4><p>${data.analysis.trump}</p></div>`;
    }
    if (data.analysis.postDeadline) {
      html += `<div class="analysis-box"><h4>What Happens After March 10?</h4><p>${data.analysis.postDeadline}</p></div>`;
    }
  }
  
  container.innerHTML = html;
  
  // Start countdown if deadline exists
  if (data.filingDeadline) {
    updateCountdown(data.filingDeadline);
    setInterval(() => updateCountdown(data.filingDeadline), 60000);
  }
}

function updateCountdown(deadline) {
  const el = document.getElementById('wl-countdown');
  if (!el) return;
  const now = new Date();
  const target = new Date(deadline);
  const diff = target - now;
  
  if (diff <= 0) {
    el.innerHTML = '<div class="countdown-expired">📋 Filing deadline has passed — the field is locked.</div>';
    return;
  }
  
  const days = Math.floor(diff / 86400000);
  const hours = Math.floor((diff % 86400000) / 3600000);
  const mins = Math.floor((diff % 3600000) / 60000);
  
  el.innerHTML = `
    <div class="countdown-label">Filing Deadline — March 10, 2026 at Noon CT</div>
    <div class="countdown-nums">
      <div class="cd-unit"><span class="cd-val">${days}</span><span class="cd-lbl">Days</span></div>
      <div class="cd-unit"><span class="cd-val">${hours}</span><span class="cd-lbl">Hours</span></div>
      <div class="cd-unit"><span class="cd-val">${mins}</span><span class="cd-lbl">Min</span></div>
    </div>`;
}

/* ===========================
   UTILITIES
   =========================== */

// Show loading state in container
function showLoading(container) {
  container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-dim)"><div style="font-size:24px;margin-bottom:8px;">⏳</div>Loading live data...</div>';
}

// Update "last updated" timestamp
function showLastUpdated(dateStr) {
  const el = document.getElementById('last-updated');
  if (el && dateStr) {
    el.textContent = `Data last updated: ${fmtDate(dateStr)}`;
  }
}

// Init function - call from each page
async function initPage(type) {
  const container = document.getElementById('dynamic-content');
  if (!container) { console.error('No #dynamic-content container found'); return; }
  
  showLoading(container);
  
  const fileMap = {
    news: 'news.json',
    endorsements: 'endorsements.json',
    timeline: 'timeline.json',
    polls: 'polls.json',
    watchlist: 'watchlist.json'
  };
  
  const renderMap = {
    news: renderNews,
    endorsements: renderEndorsements,
    timeline: renderTimeline,
    polls: renderPolls,
    watchlist: renderWatchlist
  };
  
  const file = fileMap[type];
  const render = renderMap[type];
  
  if (!file || !render) { console.error('Unknown page type:', type); return; }
  
  const data = await fetchData(file);
  if (data) {
    render(data, container);
    showLastUpdated(data.lastUpdated);
  }
}
