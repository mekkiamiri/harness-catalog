"""Outputs: a self-contained HTML dashboard and a daily Markdown note (Obsidian)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .config import Config
from .store import Store

CATEGORIES = {
    "tool": "Tools & agents",
    "model": "Models",
    "research": "Research",
    "article": "Articles",
}


def dashboard(cfg: Config, store: Store) -> Path:
    items = store.query(days=cfg.retention_days, limit=2000)
    from .describe import for_you
    for it in items:
        it["for_you"] = for_you(it, cfg.repos_focus)
    data = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "last_run": store.last_run(),
        "categories": CATEGORIES,
        "items": items,
        "events": store.events(days_ahead=365),
        "repos": repos_to_watch(store),
        "alerts": store.recent_notifications(days=7),
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("/*__DATA__*/null", payload)
    cfg.dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.dashboard_path.write_text(html, encoding="utf-8")
    return cfg.dashboard_path


def repos_to_watch(store: Store, limit: int = 30) -> list[dict]:
    from .repos import to_watch
    return to_watch(store, limit)


def markdown_note(cfg: Config, store: Store, per_category: int = 10) -> Path:
    day = datetime.now().date().isoformat()
    lines = [f"# AI radar — {day}", ""]
    alerts = store.recent_notifications(days=1)
    if alerts:
        lines += ["## Alerts", ""] + [f"- {a['message']}" for a in alerts] + [""]
    for cat, label in CATEGORIES.items():
        items = store.query(category=cat, days=2, limit=per_category)
        if not items:
            continue
        lines += [f"## {label}", ""]
        for it in items:
            res = it["signals"].get("resonance") or []
            extra = f" · mentioned by {', '.join(res)}" if res else ""
            lines.append(f"- [{it['title']}]({it['url']}) · score {it['score']:.0f} · {it['source']}{extra}")
            if it.get("brief"):
                lines.append("  " + it["brief"].replace("\n", "\n  "))
        lines.append("")
    folder = Path(cfg.export_markdown).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"ai-radar-{day}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path



TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI radar</title>
<style>
  :root { --bg:#f7f7f5; --card:#fff; --text:#1d1d1f; --muted:#6b6b70; --line:#e4e4e0; --accent:#2f5bd3; --hot:#c2410c; }
  @media (prefers-color-scheme: dark) { :root { --bg:#151517; --card:#1f1f22; --text:#ececec; --muted:#9a9aa0; --line:#2e2e33; --accent:#7aa2ff; --hot:#fb923c; } }
  * { box-sizing: border-box; }
  body { margin:0; font:15px/1.5 system-ui, -apple-system, sans-serif; background:var(--bg); color:var(--text); }
  header { padding:20px 24px 8px; }
  h1 { margin:0; font-size:22px; }
  h3 { margin:18px 0 6px; font-size:15px; color:var(--muted); font-weight:600; }
  .meta { color:var(--muted); font-size:13px; }
  nav, .filters { display:flex; flex-wrap:wrap; gap:8px; padding:8px 24px; align-items:center; }
  button.tab { border:1px solid var(--line); background:var(--card); color:var(--text); padding:6px 12px; border-radius:999px; cursor:pointer; }
  button.tab[aria-pressed=true] { background:var(--accent); color:#fff; border-color:var(--accent); }
  input, select { padding:6px 10px; border:1px solid var(--line); border-radius:8px; background:var(--card); color:var(--text); }
  main { padding:8px 24px 40px; display:grid; gap:14px; grid-template-columns:repeat(auto-fill, minmax(290px, 1fr)); max-width:1400px; }
  main > h3, main > p, main > .wide { grid-column:1 / -1; }
  article { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:14px 16px; display:flex; flex-direction:column; gap:6px;
            transition:transform .12s ease, border-color .12s ease; }
  article:hover { transform:translateY(-2px); border-color:var(--accent); }
  .card-top { display:flex; justify-content:space-between; align-items:center; font-size:12px; color:var(--muted); }
  .chip { display:inline-flex; align-items:center; gap:6px; }
  .dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
  .summary { color:var(--text); opacity:.85; margin:0; display:-webkit-box; -webkit-line-clamp:4; -webkit-box-orient:vertical; overflow:hidden; }
  .card-foot { margin-top:auto; display:flex; justify-content:space-between; align-items:center; gap:8px; }
  article h2 { font-size:16px; margin:0 0 4px; }
  article h2 a { color:var(--text); text-decoration:none; }
  article h2 a:hover { color:var(--accent); }
  .score { font-weight:700; color:var(--accent); font-variant-numeric:tabular-nums; border:1px solid var(--accent); border-radius:999px; padding:0 8px; font-size:12px; }
  .tags { display:flex; gap:6px; flex-wrap:wrap; margin:4px 0; font-size:12px; }
  .tag { border:1px solid var(--line); border-radius:6px; padding:1px 6px; color:var(--muted); }
  .tag.new, .tag.soon { border-color:var(--hot); color:var(--hot); font-weight:600; }
  .tag.res { border-color:var(--accent); color:var(--accent); }
  .tag.fy-yes { border-color:#16a34a; color:#16a34a; font-weight:600; }
  .tag.fy-maybe { border-color:#ca8a04; color:#ca8a04; }
  article.speaking { outline:2px solid var(--accent); outline-offset:2px; }
  .listen { display:flex; gap:6px; align-items:center; flex-wrap:wrap; }
  .listen button, .listen select { font:inherit; font-size:13px; border:1px solid var(--line); border-radius:6px; background:transparent; color:inherit; padding:3px 8px; cursor:pointer; }
  .desc { color:var(--muted); margin:4px 0 0; }
  details { margin-top:6px; } summary { cursor:pointer; color:var(--accent); font-size:13px; }
  .brief { white-space:pre-wrap; margin:6px 0 0; }
  .alerts { margin:4px 24px 0; padding:10px 14px; border:1px solid var(--hot); border-radius:12px; background:var(--card); max-width:1052px; }
  .alerts li { margin:2px 0; }
  .empty { color:var(--muted); padding:40px 0; text-align:center; }
</style>
</head>
<body>
<header>
  <h1>AI radar</h1>
  <div class="meta" id="meta"></div>
  <div class="listen" id="listen" hidden>
    <button id="say" title="Read the visible cards aloud (free, built into the browser)">🎧 Listen</button>
    <button id="skip" title="Next card" hidden>⏭</button>
    <select id="voice" aria-label="Voice"></select>
    <select id="rate" aria-label="Speed"><option>0.9</option><option selected>1</option><option>1.15</option><option>1.3</option><option>1.5</option></select>
  </div>
</header>
<div id="alerts"></div>
<nav id="tabs"></nav>
<div class="filters" id="filters">
  <input id="q" type="search" placeholder="Filter (name, description)…" aria-label="Filter">
  <select id="period" aria-label="Period">
    <option value="1">Today</option>
    <option value="7">7 days</option>
    <option value="30" selected>30 days</option>
  </select>
  <label class="meta"><input type="checkbox" id="resonant"> Mentioned by several sources</label>
  <label class="meta"><input type="checkbox" id="forme"> For me only</label>
</div>
<main id="list"></main>
<script>
const DATA = /*__DATA__*/null;
const state = { cat: "all", q: "", days: 30, resonant: false, forme: false };
const safeUrl = u => /^https?:\/\//i.test(String(u || "")) ? u : "#";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const age = iso => (Date.now() - new Date(iso)) / 86400000;
const until = d => Math.ceil((new Date(d + "T23:59:59") - Date.now()) / 86400000);
const fmt = d => d ? new Date(d.length > 10 ? d : d + "T12:00:00").toLocaleDateString("en-GB", {day:"numeric", month:"short", year:"numeric"}) : "?";

function meta() {
  const r = DATA.last_run, rep = r ? r.report : {};
  const err = rep.errors && Object.keys(rep.errors).length ? ` · failing sources: ${Object.keys(rep.errors).join(", ")}` : "";
  document.getElementById("meta").textContent =
    `Generated ${new Date(DATA.generated_at).toLocaleString("en-GB")} · ${DATA.items.length} items over 30 days · ${DATA.events.length} upcoming events` +
    (r ? ` · last run: ${rep.new ?? 0} new` : "") + err;
}

function alerts() {
  if (!DATA.alerts || !DATA.alerts.length) return;
  document.getElementById("alerts").innerHTML = `<div class="alerts"><strong>Alerts (7 days)</strong><ul>` +
    DATA.alerts.slice(0, 12).map(a => `<li>${esc(a.message)}</li>`).join("") + "</ul></div>";
}

function tabs() {
  const nav = document.getElementById("tabs");
  const cats = { all: "All", trends: "Languages", repos: "Repos", ...DATA.categories, events: "Events & CFPs" };
  nav.innerHTML = "";
  for (const [k, v] of Object.entries(cats)) {
    const n = k === "all" ? DATA.items.length : k === "events" ? DATA.events.length : k === "repos" ? (DATA.repos || []).length : k === "trends" ? "" : DATA.items.filter(i => i.category === k).length;
    const b = document.createElement("button");
    b.className = "tab"; b.textContent = n === "" ? v : `${v} (${n})`;
    b.setAttribute("aria-pressed", state.cat === k);
    b.onclick = () => { state.cat = k; tabs(); render(); };
    nav.appendChild(b);
  }
  document.getElementById("filters").style.display = ["events", "trends", "repos"].includes(state.cat) ? "none" : "flex";
}

const CAT_COLOR = { tool: "#2f9e6e", model: "#7c5cd6", research: "#d08a1f", article: "#2f7bd3" };
const ago = iso => { const d = Math.floor(age(iso)); return d < 1 ? "today" : d === 1 ? "yesterday" : `${d} days ago`; };
const briefLine = b => { const m = /\*\*What it is\*\*:\s*(.+)/i.exec(b || ""); return m ? m[1] : ""; };

function itemCard(i) {
  const s = i.signals, t = [];
  if (age(i.first_seen) < 1) t.push('<span class="tag new">new</span>');
  if (s.stars != null) t.push(`<span class="tag">★ ${s.stars} · ${s.stars_per_day}/day</span>`);
  if (s.votes) t.push(`<span class="tag">▲ ${s.votes}</span>`);
  if (s.points) t.push(`<span class="tag">${s.points} pts</span>`);
  if (s.likes) t.push(`<span class="tag">♥ ${s.likes}</span>`);
  if (s.free) t.push('<span class="tag">free</span>');
  if (s.language) t.push(`<span class="tag">${esc(s.language)}</span>`);
  if (s.network) t.unshift(`<span class="tag res" title="Published by an account you follow ([people] github)">👥 ${esc(s.network)}</span>`);
  if ((s.resonance || []).length) t.push(`<span class="tag res">${s.resonance.length} sources</span>`);
  if (s.emergence) t.push(`<span class="tag new">${esc(s.emergence)}</span>`);
  if (i.status !== "new") t.push(`<span class="tag">${esc(i.status)}</span>`);
  const desc = (i.description || "").length >= 60 ? i.description : (s.readme || i.description || "");
  const summary = briefLine(i.brief) || desc;
  const fy = { ...(i.for_you || {}) };
  const fb = /\*\*For you\*\*:\s*(Yes|Maybe|No)\b[\s—:-]*(.*)/i.exec(i.brief || "");
  if (fb) { fy.level = fb[1].toLowerCase() === "yes" ? "yes" : fb[1].toLowerCase() === "maybe" ? "maybe" : "no"; fy.why = [fb[2].slice(0, 90)]; }
  if (fy.level === "yes") t.unshift(`<span class="tag fy-yes" title="Matches your focus topics">For you · ${esc(fy.why.join(", "))}</span>`);
  if (fy.level === "maybe") t.unshift(`<span class="tag fy-maybe" title="Matches one of your focus topics">Maybe for you · ${esc(fy.why.join(", "))}</span>`);
  const verdict = fy.level === "yes" ? `For you: yes, ${fy.why.join(" and ")}.` : fy.level === "maybe" ? `Maybe for you: ${fy.why[0]}.` : "";
  const say = [i.title.replace(/[\/_-]+/g, " "), String(summary).slice(0, 600), verdict].filter(Boolean).join(". ");
  const brief = i.brief ? `<details><summary>Full brief</summary><div class="brief">${esc(i.brief)}</div></details>` : "";
  const lab = i.lab ? `<details><summary>Lab</summary><div class="brief">${esc(i.lab)}</div></details>` : "";
  const res = (s.resonance || []).length ? ` title="Mentioned by ${esc(s.resonance.join(", "))}"` : "";
  return `<article${res} data-say="${esc(say)}">
    <div class="card-top"><span class="chip"><span class="dot" style="background:${CAT_COLOR[i.category] || "#888"}"></span>${esc(DATA.categories[i.category] || i.category)} · ${esc(i.source)}</span><span>${ago(i.first_seen)}</span></div>
    <h2><a href="${esc(safeUrl(i.url))}" target="_blank" rel="noopener">${esc(i.title)}</a></h2>
    ${summary ? `<p class="summary">${esc(summary)}</p>` : ""}${brief}${lab}
    <div class="card-foot"><div class="tags">${t.join("")}</div><span class="score" title="${esc(JSON.stringify(s.score_detail || {}))}">${Math.round(i.score)}</span></div>
  </article>`;
}

function eventCard(e, withCfp) {
  const t = [];
  if (e.watched) t.push('<span class="tag soon">★ watchlist</span>');
  t.push(`<span class="tag">${esc(e.kind)}</span>`, `<span class="tag">${esc(e.online ? "online" : e.location || e.country)}</span>`);
  (e.languages || []).forEach(l => t.push(`<span class="tag">${esc(l)}</span>`));
  if ((e.tags || []).includes("call-for-speakers")) t.push('<span class="tag soon">looking for speakers</span>');
  if (withCfp && e.cfp_close) {
    const d = until(e.cfp_close);
    t.push(`<span class="tag ${d <= 30 ? "soon" : ""}">CFP closes ${fmt(e.cfp_close)} · ${d} days</span>`);
    if (e.cfp_open && new Date(e.cfp_open) > Date.now()) t.push(`<span class="tag">opens ${fmt(e.cfp_open)}</span>`);
    if (e.cfp_close_prev) t.push(`<span class="tag soon">moved from ${fmt(e.cfp_close_prev)}</span>`);
  }
  t.push(`<span class="tag">${esc(e.source)}</span>`);
  const cfp = withCfp && e.cfp_url ? ` · <a href="${esc(safeUrl(e.cfp_url))}" target="_blank" rel="noopener">submit</a>` : "";
  return `<article><h2><a href="${esc(safeUrl(e.url))}" target="_blank" rel="noopener">${esc(e.name)}</a></h2>
    <div class="tags">${t.join("")}</div><p class="desc">${fmt(e.start_at)}${e.end_at && e.end_at.slice(0,10) !== e.start_at.slice(0,10) ? " → " + fmt(e.end_at) : ""}${cfp}</p></article>`;
}

function renderEvents(main) {
  const cfps = DATA.events.filter(e => e.cfp_close && until(e.cfp_close) >= 0).sort((a, b) => (b.watched - a.watched) || a.cfp_close.localeCompare(b.cfp_close));
  const online = DATA.events.filter(e => e.online && age(e.start_at) < 1 && until(e.start_at.slice(0,10)) <= 30);
  const confs = DATA.events.filter(e => e.kind === "conference" && !e.online);
  const block = (title, list, cfp) => list.length ? `<h3>${title} (${list.length})</h3>` + list.map(e => eventCard(e, cfp)).join("") : "";
  const body = block("Open CFPs, by closing date", cfps, true) + block("Online in the next 30 days", online, false) +
    block("Upcoming conferences", confs, false);
  main.innerHTML = body ? '<p class="meta">Dates come from community agendas and public CFP APIs: always verify on the official site before submitting.</p>' + body
    : '<p class="empty">No events. Conference and CFP tracking is off by default: set <code>[events] enabled = true</code> in ~/.ai-radar/config.toml.</p>';
}

function renderTrends(main) {
  const t = (DATA.last_run && DATA.last_run.report.trends) || {};
  const table = (rows, cols) => `<article class="wide"><table style="width:100%;border-collapse:collapse">` +
    `<tr>${cols.map(c => `<th style="text-align:left;color:var(--muted);font-weight:600">${c[1]}</th>`).join("")}</tr>` +
    rows.map(r => `<tr>${cols.map(c => `<td>${esc(c[2] ? c[2](r) : r[c[0]])}</td>`).join("")}</tr>`).join("") + "</table></article>";
  const sign = v => v == null ? "—" : (v > 0 ? "+" : "") + v;
  let html = "";
  const repos = t.new_ai_repos;
  if (repos && repos.languages.length) html += `<h3>Languages of new AI repos (last ${repos.window_days} days, star-weighted)</h3>` +
    table(repos.languages, [["language", "Language"], ["share", "Share %"], ["previous_share", "Previous window %", r => r.previous_share ?? "—"]]);
  if (t.frameworks && t.frameworks.length) html += "<h3>Frameworks used by new AI repos (14 days)</h3>" +
    table(t.frameworks, [["framework", "Framework"], ["repos", "Repos"], ["stars", "Stars"]]);
  if (t.pypl) html += `<h3>Tutorial searches (PYPL, ${esc(t.pypl.month)})</h3>` +
    table(t.pypl.languages, [["language", "Language"], ["share", "Share %"], ["change_12m", "12-month change (pts)", r => sign(r.change_12m)]]);
  main.innerHTML = html || '<p class="empty">No trend data yet.</p>';
}

function renderRepos(main) {
  const list = DATA.repos || [];
  if (!list.length) { main.innerHTML = '<p class="empty">No repository analysed yet (runs after the next collection).</p>'; return; }
  main.innerHTML = '<p class="meta wide">Repositories worth watching or contributing to, best first. Score: growth, newsletter mentions, entry tickets, organization backing, activity, match with your focus.</p>' +
    list.map(i => {
      const s = i.signals, c = s.contrib || {}, why = [];
      if ((s.mentioned_by || []).length) why.push(`<span class="tag res">in ${esc(s.mentioned_by.join(", "))}</span>`);
      if (s.stars_per_day) why.push(`<span class="tag">★ ${s.stars} · ${s.stars_per_day}/day</span>`);
      if (c.good_first_issues) why.push(`<span class="tag new">${c.good_first_issues} good first issues</span>`);
      if (c.help_wanted) why.push(`<span class="tag">${c.help_wanted} help wanted</span>`);
      if (c.org_backed) why.push('<span class="tag">organization</span>');
      if (c.days_since_push != null) why.push(`<span class="tag">pushed ${c.days_since_push === 0 ? "today" : c.days_since_push + " d ago"}</span>`);
      (c.focus_match || []).forEach(f => why.push(`<span class="tag new">${esc(f)}</span>`));
      if (s.language) why.push(`<span class="tag">${esc(s.language)}</span>`);
      return `<article><div class="card-top"><span class="chip"><span class="dot" style="background:#2f9e6e"></span>Repository</span><span>${ago(i.first_seen)}</span></div>
        <h2><a href="${esc(safeUrl(i.url))}" target="_blank" rel="noopener">${esc(i.title)}</a></h2>
        ${i.description ? `<p class="summary">${esc(i.description)}</p>` : ""}
        <div class="card-foot"><div class="tags">${why.join("")}</div><span class="score" title="contribution score">${Math.round(s.contrib_score || 0)}</span></div></article>`;
    }).join("");
}

function render() {
  const main = document.getElementById("list");
  if (state.cat === "repos") return renderRepos(main);
  if (state.cat === "events") return renderEvents(main);
  if (state.cat === "trends") return renderTrends(main);
  const q = state.q.toLowerCase();
  const items = DATA.items
    .filter(i => state.cat === "all" || i.category === state.cat)
    .filter(i => i.status === "starred" || age(i.first_seen) <= state.days)
    .filter(i => !state.resonant || (i.signals.resonance || []).length > 0)
    .filter(i => !state.forme || ["yes", "maybe"].includes((i.for_you || {}).level))
    .filter(i => !q || (i.title + " " + i.description).toLowerCase().includes(q))
    .sort((a, b) => b.score - a.score);
  main.innerHTML = items.length ? items.map(itemCard).join("") : '<p class="empty">Nothing for these filters.</p>';
}

document.getElementById("q").oninput = e => { state.q = e.target.value; render(); };
document.getElementById("period").onchange = e => { state.days = +e.target.value; render(); };
document.getElementById("resonant").onchange = e => { state.resonant = e.target.checked; render(); };
// --- Listen: the visible cards read aloud by the browser's own speech synthesis (free, offline) ---
const speech = { on: false, queue: [], i: 0 };
const sayBtn = document.getElementById("say"), skipBtn = document.getElementById("skip");
const voiceSel = document.getElementById("voice"), rateSel = document.getElementById("rate");
function fillVoices() {
  const vs = speechSynthesis.getVoices();
  if (!vs.length) return;
  const saved = localStorage.getItem("radar-voice");
  const best = vs.find(v => v.name === saved) || vs.find(v => /^en/i.test(v.lang) && /natural|premium|enhanced|neural|siri/i.test(v.name))
    || vs.find(v => /^en/i.test(v.lang)) || vs[0];
  voiceSel.innerHTML = vs.map(v => `<option${v === best ? " selected" : ""}>${esc(v.name)}</option>`).join("");
}
function stopSpeech() {
  speech.on = false; speech.cur = null; speechSynthesis.cancel();
  document.querySelectorAll("article.speaking").forEach(a => a.classList.remove("speaking"));
  sayBtn.textContent = "🎧 Listen"; skipBtn.hidden = true;
}
function nextCard() {
  if (!speech.on || speech.i >= speech.queue.length) return stopSpeech();
  const a = speech.queue[speech.i++];
  document.querySelectorAll("article.speaking").forEach(x => x.classList.remove("speaking"));
  a.classList.add("speaking"); a.scrollIntoView({ behavior: "smooth", block: "center" });
  const u = new SpeechSynthesisUtterance(a.dataset.say);
  const v = speechSynthesis.getVoices().find(x => x.name === voiceSel.value);
  if (v) { u.voice = v; u.lang = v.lang; }
  u.rate = Number(rateSel.value) || 1;
  speech.cur = u;  // a cancelled utterance may fire onend or onerror: only the current one moves on
  u.onend = u.onerror = () => { if (speech.cur === u) nextCard(); };
  speechSynthesis.speak(u);
}
if ("speechSynthesis" in window) {
  document.getElementById("listen").hidden = false;
  fillVoices(); speechSynthesis.onvoiceschanged = fillVoices;
  voiceSel.onchange = () => localStorage.setItem("radar-voice", voiceSel.value);
  sayBtn.onclick = () => {
    if (speech.on) return stopSpeech();
    speech.queue = [...document.querySelectorAll("#list article[data-say]")];
    if (!speech.queue.length) return;
    speech.i = 0; speech.on = true; sayBtn.textContent = "■ Stop"; skipBtn.hidden = false; nextCard();
  };
  skipBtn.onclick = () => { speech.cur = null; speechSynthesis.cancel(); nextCard(); };
}
document.getElementById("forme").onchange = e => { state.forme = e.target.checked; render(); };
meta(); alerts(); tabs(); render();
</script>
</body>
</html>
"""


def weekly_digest(cfg: Config, store: Store) -> Path:
    """Stable weekly file (ISO week): ~/.ai-radar/weekly/YYYY-Www.md. Rewritten on every run of the week.
    Other tools (e.g. a speaker coach) read it to turn the week's news into talk ideas."""
    today = datetime.now().date()
    year, week, _ = today.isocalendar()
    lines = [f"# AI radar — week {year}-W{week:02d}", "",
             f"_Generated {datetime.now().astimezone().isoformat(timespec='minutes')}. "
             "Event dates are leads from community agendas (not verified)._", ""]

    top = store.query(days=7, limit=10)
    if top:
        lines += ["## Top 10 of the week", ""]
        for it in top:
            res = it["signals"].get("resonance") or []
            what = brief_line(it.get("brief", ""))
            lines.append(f"- **{it['title']}** ({CATEGORIES.get(it['category'], it['category'])}, score {it['score']:.0f})"
                         + (f" — mentioned by {', '.join(res)}" if res else "") + f" — {it['url']}")
            if what:
                lines.append(f"  {what}")
        lines.append("")

    rising = sorted((it for it in store.query(days=7, limit=500) if it["signals"].get("resonance")),
                    key=lambda it: (-len(it["signals"]["resonance"]), -it["score"]))[:5]
    if rising:
        lines += ["## Rising topics (most independent sources)", ""]
        lines += [f"- {it['title']} — {len(it['signals']['resonance'])} sources" for it in rising] + [""]

    last = store.last_run() or {}
    trends = (last.get("report") or {}).get("trends") or {}
    langs = (trends.get("new_ai_repos") or {}).get("languages") or []
    if langs:
        lines += ["## Languages and frameworks", "",
                  "- New AI repos (star-weighted): " + ", ".join(f"{l['language']} {l['share']}%" for l in langs[:6])]
        fw = trends.get("frameworks") or []
        if fw:
            lines.append("- Frameworks in new AI repos: " + ", ".join(f"{f['framework']} ({f['repos']})" for f in fw[:6]))
        pypl = trends.get("pypl")
        if pypl:
            lines.append(f"- Tutorial searches (PYPL {pypl['month']}): " + ", ".join(
                f"{l['language']} {l['share']}%" + (f" ({l['change_12m']:+} pts/12 months)" if l["change_12m"] is not None else "")
                for l in pypl["languages"][:5]))
        lines.append("")

    cfps = store.upcoming_cfps(days=30)
    if cfps:
        lines += ["## CFPs closing within 30 days", ""]
        for ev in sorted(cfps, key=lambda e: (not e["watched"], e["cfp_close"])):
            star = "★ " if ev["watched"] else ""
            lines.append(f"- {star}{ev['name']} — closes {ev['cfp_close']} — {ev['cfp_url'] or ev['url']} (source: {ev['source']})")
        lines.append("")

    online = store.events(online_only=True, days_ahead=14)
    speakers = [ev for ev in online if "call-for-speakers" in ev["tags"]]
    if online:
        lines += ["## Online events in the next 14 days", ""]
        lines += [f"- {ev['start_at'][:10]} — {ev['name']} ({ev['location'] or ev['kind']}) — {ev['url']}" for ev in online[:15]]
        lines.append("")
    if speakers:
        lines += ["## Meetups looking for speakers", ""]
        lines += [f"- {ev['name']} ({ev['location']}) — {ev['url']}" for ev in speakers] + [""]

    cfg.weekly_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.weekly_dir / f"{year}-W{week:02d}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def brief_line(brief: str) -> str:
    """The "What it is" sentence of a brief (same parsing as briefLine() in the dashboard script)."""
    for line in (brief or "").splitlines():
        if line.lower().startswith("**what it is**"):
            return line.split(":", 1)[-1].strip()
    return ""
