"use strict";
/* The website: loads data/events.json (made ahead of time by the Python pipeline) and draws it.
   No server, no OCR, no heavy work here - so pages stay fast. */

const T = {
  en: {
    brand: "uOttawa Events", visual: "Visual", compact: "Compact", filters: "Filters", upcoming: "Upcoming", missed: "Missed",
    categories: "Categories", hidden_default: "hidden by default",
    g_now: "Happening now", g_soon: "Starting soon", g_today: "Later today", g_tomorrow: "Tomorrow", g_week: "This week", g_later: "Later this month",
    g_missed: "Past week",
    empty_upcoming: "No upcoming events match your filters.", empty_missed: "Nothing missed in the past week.",
    empty_none: "No events yet. The first automatic update hasn't run.", load_error: "Could not load events. Please try again later.",
    donation: "By donation", show_more: "Show more", show_less: "Show less",
    rsvp_yes: "RSVP required", rsvp_no: "Drop-in", free: "Free", paid: "Paid", cost_unknown: "Cost not stated", mixed: "{a} (free for some)",
    loc_unknown: "Location not stated", time_unknown: "time not stated", online: "Online", cancelled: "Cancelled", updated: "Updated",
    upd_cancelled: "This event has been cancelled.", upd_resched: "Rescheduled: {o} → {n}", upd_resched_x: "Rescheduled – check the original post for details.",
    upd_loc: "Location changed: {o} → {n}", upd_loc_x: "Location changed – check the original post.", upd_post: "update post",
    only_en: "This event is only offered in English.", only_fr: "This event is only offered in French.",
    maybe_en: "This event may be geared toward English speakers", maybe_fr: "This event may be geared toward French speakers",
    translated_en: "Automatically translated from French.", translated_fr: "Automatically translated from English.",
    weekly: "Repeats weekly until {d}.", biweekly: "Repeats every two weeks until {d}.",
    assumed: "The post did not give an end date, so we assumed it ends with the school year ({d}).",
    unclear: "Only the date was clear in the post – see the original post for the rest.",
    view_post: "View original post ↗", last_updated: "Last updated", demo: "DEMO DATA – not real events.",
    disclaimer: "Events are collected automatically from clubs' public posts and can contain mistakes. Always check the original post."
  },
  fr: {
    brand: "Événements uOttawa", visual: "Visuel", compact: "Compact", filters: "Filtres", upcoming: "À venir", missed: "Manqués",
    categories: "Catégories", hidden_default: "masquée par défaut",
    g_now: "En cours", g_soon: "Bientôt", g_today: "Plus tard aujourd'hui", g_tomorrow: "Demain", g_week: "Cette semaine", g_later: "Plus tard ce mois-ci",
    g_missed: "Semaine dernière",
    empty_upcoming: "Aucun événement à venir ne correspond à vos filtres.", empty_missed: "Rien de manqué la semaine dernière.",
    empty_none: "Aucun événement pour l'instant. La première mise à jour automatique n'a pas encore eu lieu.", load_error: "Impossible de charger les événements. Réessayez plus tard.",
    donation: "Contribution volontaire", show_more: "Voir plus", show_less: "Voir moins",
    rsvp_yes: "Inscription requise", rsvp_no: "Sans inscription", free: "Gratuit", paid: "Payant", cost_unknown: "Coût non précisé", mixed: "{a} (gratuit pour certains)",
    loc_unknown: "Lieu non précisé", time_unknown: "heure non précisée", online: "En ligne", cancelled: "Annulé", updated: "Mis à jour",
    upd_cancelled: "Cet événement a été annulé.", upd_resched: "Reporté : {o} → {n}", upd_resched_x: "Reporté – consultez la publication d'origine.",
    upd_loc: "Changement de lieu : {o} → {n}", upd_loc_x: "Changement de lieu – consultez la publication d'origine.", upd_post: "publication",
    only_en: "Cet événement est offert en anglais seulement.", only_fr: "Cet événement est offert en français seulement.",
    maybe_en: "Cet événement semble s'adresser à un public anglophone", maybe_fr: "Cet événement semble s'adresser à un public francophone",
    translated_en: "Traduit automatiquement du français.", translated_fr: "Traduit automatiquement de l'anglais.",
    weekly: "Se répète chaque semaine jusqu'au {d}.", biweekly: "Se répète toutes les deux semaines jusqu'au {d}.",
    assumed: "La publication ne donnait pas de date de fin; nous supposons qu'il se termine avec l'année scolaire ({d}).",
    unclear: "Seule la date était claire dans la publication – voir la publication d'origine pour le reste.",
    view_post: "Voir la publication d'origine ↗", last_updated: "Dernière mise à jour", demo: "DONNÉES DE DÉMO – ce ne sont pas de vrais événements.",
    disclaimer: "Les événements sont recueillis automatiquement à partir des publications publiques des clubs et peuvent contenir des erreurs. Vérifiez toujours la publication d'origine."
  }
};

// ---------- tiny helpers
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode: ignore */ } }
};
const DEMO = new URLSearchParams(location.search).has("demo");
const state = {
  lang: store.get("lang", (navigator.language || "en").startsWith("fr") ? "fr" : "en"),
  tab: "upcoming",
  mode: store.get("mode", "visual"),
  hidden: new Set(store.get("hidden", ["religion"])),    // religion is hidden by default
  expanded: new Set()                                    // events whose full description is open
};
let DATA = null, TZ = "America/Toronto";
const t = (k, vars = {}) => (T[state.lang][k] ?? k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? "");

// ---------- dates (always shown in Ottawa time)
const loc = () => (state.lang === "fr" ? "fr-CA" : "en-CA");
const fDate = (d) => new Intl.DateTimeFormat(loc(), { timeZone: TZ, weekday: "short", month: "short", day: "numeric" }).format(d);
const fTime = (d) => new Intl.DateTimeFormat(loc(), { timeZone: TZ, hour: "numeric", minute: "2-digit" }).format(d);
const fDay = (ymd) => fDate(zoned(ymd, 12, 0));
const dayKey = (d) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
const dayDiff = (a, b) => Math.round((Date.parse(a) - Date.parse(b)) / 864e5);
function tzOffset(d) {
  const p = Object.fromEntries(new Intl.DateTimeFormat("en-US", { timeZone: TZ, hourCycle: "h23", year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", second: "numeric" })
    .formatToParts(d).map((x) => [x.type, x.value]));
  return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - Math.floor(d.getTime() / 1000) * 1000;
}
function zoned(ymd, h, m) {                      // "2026-11-28" + 23:59 in Ottawa time -> Date
  const [Y, M, D] = ymd.split("-").map(Number), base = Date.UTC(Y, M - 1, D, h, m);
  let ts = base;
  for (let i = 0; i < 2; i++) ts = base - tzOffset(new Date(ts));
  return new Date(ts);
}
const endOfDay = (ymd) => zoned(ymd, 23, 59);

// ---------- turn events into "instances" (one card each)
function instances(now) {
  const up = [], missed = [], today = dayKey(now);
  for (const ev of DATA.events) {
    if (state.hidden.has(ev.category)) continue;
    const dl = ev.dependency && ev.dependency.deadline;
    if (dl && now > endOfDay(dl)) continue;       // sign-up window closed -> nothing to act on
    const rec = ev.recurrence;
    if (rec && rec.until < today) continue;
    const mk = (iso) => {
      const start = new Date(iso), ymd = iso.slice(0, 10);
      let end;
      if (ev.date_only) end = endOfDay(ev.end_date || ymd);
      else if (!rec && ev.end) end = new Date(ev.end);
      else end = new Date(start.getTime() + (ev.duration_min || 120) * 60000);
      return { ev, start, end };
    };
    const all = (rec ? rec.occurrences : [ev.start]).map(mk);
    const next = all.find((i) => i.end >= now);
    if (next && next.start - now <= DATA.upcoming_ms) up.push(next);
    const past = all.filter((i) => i.end < now);
    if (past.length) {
      const last = past[past.length - 1];
      if (rec || now - last.end <= DATA.missed_ms) missed.push(last);   // recurring: stays until its end date
    }
  }
  return { up, missed };
}

const ORDER = ["now", "soon", "today", "tomorrow", "week", "later"];
function groupOf(i, now) {
  if (!i.ev.date_only && i.start <= now) return "now";
  const diff = dayDiff(dayKey(i.start), dayKey(now));
  if (!i.ev.date_only && i.start - now <= 2 * 3600e3) return "soon";
  if (diff <= 0) return "today";
  return diff === 1 ? "tomorrow" : diff <= 6 ? "week" : "later";
}

// ---------- drawing
const byLang = (v) => (v && typeof v === "object" ? v[state.lang] || "" : v || "");   // {en, fr} or plain text
function clubName(c) {
  const name = byLang(c.name), acr = byLang(c.acronym);
  if (name && acr) return `${name} (${acr})`;
  return name || acr || "@" + c.handle;
}
function updateText(u) {
  const nd = (iso) => `${fDate(new Date(iso))} ${fTime(new Date(iso))}`;
  if (u.kind === "cancelled") return t("upd_cancelled");
  if (u.kind === "location") return u.new ? t("upd_loc", { o: u.old || "?", n: u.new }) : t("upd_loc_x");
  return u.new ? t("upd_resched", { o: nd(u.old), n: nd(u.new) }) : t("upd_resched_x");
}
function whenText(i) {
  const { ev, start, end } = i, rec = ev.recurrence;
  const hasEnd = !ev.date_only && ((!rec && ev.end) || (rec && ev.duration_min));
  if (ev.date_only) {
    const last = ev.end_date && ev.end_date !== ev.start.slice(0, 10) ? " – " + fDay(ev.end_date) : "";
    return `${fDate(start)}${last} · ${t("time_unknown")}`;
  }
  let s = `${fDate(start)} · ${fTime(start)}`;
  if (hasEnd) s += dayKey(end) === dayKey(start) ? `–${fTime(end)}` : ` – ${fDate(end)} ${fTime(end)}`;
  return s;
}
function costChip(c) {
  if (c.type === "free") return `<span class="chip free">${t("free")}</span>`;
  if (c.type === "paid") return `<span class="chip">${esc(c.amount || t("paid"))}</span>`;
  if (c.type === "donation") return `<span class="chip">${esc(t("donation") + (c.amount ? " (" + c.amount + ")" : ""))}</span>`;
  if (c.type === "mixed") return `<span class="chip">${esc(t("mixed", { a: c.amount }))}</span>`;
  return `<span class="chip">${t("cost_unknown")}</span>`;
}
function card(i) {
  const ev = i.ev, L = state.lang, rec = ev.recurrence;
  const name = clubName(ev.club);
  const avatar = ev.club.avatar
    ? `<img class="avatar" src="${esc(ev.club.avatar)}" alt="" loading="lazy">`
    : `<div class="avatar" aria-hidden="true">${esc((byLang(ev.club.acronym) || ev.club.handle).slice(0, 2).toUpperCase())}</div>`;
  const place = ev.location ? (ev.location.online ? t("online") + (ev.location.text !== "Online" ? " – " + esc(ev.location.text) : "") : esc(ev.location.text)) : t("loc_unknown");
  const notes = [];
  if (ev.language_note) notes.push(t(ev.language_note));
  if (ev.translated_from) notes.push(t("translated_" + L));
  if (rec) {
    notes.push(t(rec.freq, { d: fDay(rec.until) }));
    if (rec.until_assumed) notes.push(t("assumed", { d: fDay(rec.until) }));
  }
  if (ev.date_only && !ev.location) notes.push(t("unclear"));
  const desc = (ev.description[L] || "").trim();
  const safeUrl = /^https:\/\//.test(ev.post_url) ? ev.post_url : "#";
  const updates = (ev.updates || []).map((u) =>
    `<div class="upd"><strong>${t("updated")}:</strong> ${esc(updateText(u))} <a class="link" href="${esc(u.url)}" target="_blank" rel="noopener">${t("upd_post")} ↗</a></div>`).join("");
  const poster = ev.image
    ? `<a class="poster-link" href="${esc(safeUrl)}" target="_blank" rel="noopener"><img class="poster" src="${esc(ev.image)}" alt="${esc(ev.title[L])}" loading="lazy"></a>` : "";
  return `<article class="card ${ev.status === "cancelled" ? "cancelled" : ""}">
    ${poster}
    <div class="row">
    ${avatar}
    <div class="body">
      <h3>${esc(ev.title[L])}</h3><div class="club">${esc(name)}</div>
      <div class="rows">
        <div><b>🕒</b> ${esc(whenText(i))}</div>
        <div><b>📍</b> ${place}</div>
      </div>
      <div class="chips">
        ${ev.status === "cancelled" ? `<span class="chip bad">${t("cancelled")}</span>` : ""}
        <span class="chip ${ev.rsvp_required ? "rsvp" : ""}">${t(ev.rsvp_required ? "rsvp_yes" : "rsvp_no")}</span>
        ${costChip(ev.cost)}
      </div>
      ${desc ? `<div class="desc ${state.expanded.has(ev.id) ? "" : "clamp"}">${esc(desc)}</div><button class="more" data-more="${esc(ev.id)}" hidden>${t(state.expanded.has(ev.id) ? "show_less" : "show_more")}</button>` : ""}
      ${notes.map((n) => `<div class="note">${esc(n)}</div>`).join("")}
      ${updates}
      <a class="link" href="${esc(safeUrl)}" target="_blank" rel="noopener">${t("view_post")}</a>
    </div></div></article>`;
}

function render() {
  if (!DATA) return;
  const now = new Date(), { up, missed } = instances(now);
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
  document.querySelectorAll("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.lang === state.lang));
  document.querySelectorAll("[data-mode]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.mode === state.mode));
  document.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-selected", b.dataset.tab === state.tab));
  $("#list").className = state.mode === "compact" ? "compact" : "";

  let html = "";
  if (state.tab === "upcoming") {
    const groups = {};
    up.forEach((i) => (groups[groupOf(i, now)] ||= []).push(i));
    for (const g of ORDER) {
      if (!groups[g]) continue;
      html += `<div class="group">${t("g_" + g)}</div>` + groups[g].sort((a, b) => a.start - b.start).map(card).join("");
    }
    if (!html) html = `<div class="empty">${t(DATA.events.length ? "empty_upcoming" : "empty_none")}</div>`;
  } else {
    html = missed.length
      ? `<div class="group">${t("g_missed")}</div>` + missed.sort((a, b) => b.start - a.start).map(card).join("")
      : `<div class="empty">${t("empty_missed")}</div>`;
  }
  $("#list").innerHTML = html;
  document.querySelectorAll(".desc").forEach((el) => {          // show the button only when the text is really cut off
    const btn = el.nextElementSibling;
    if (btn && btn.dataset.more) btn.hidden = el.classList.contains("clamp") ? !(el.scrollHeight > el.clientHeight + 1) : false;
  });

  // filter panel
  $("#filterBtn").textContent = t("filters");
  $("#filterPanel").innerHTML = `<h2>${t("categories")}</h2><div class="opts">` + DATA.categories.map((c) =>
    `<label><input type="checkbox" data-cat="${esc(c.id)}" ${state.hidden.has(c.id) ? "" : "checked"}> ${esc(c[state.lang] || c.en)}` +
    `${c.id === "religion" ? ` <small>(${t("hidden_default")})</small>` : ""}</label>`).join("") + "</div>";

  const gen = DATA.generated_at ? `${t("last_updated")}: ${fDate(new Date(DATA.generated_at))} ${fTime(new Date(DATA.generated_at))}` : "";
  $("#foot").innerHTML = `${DEMO ? `<p><strong>${t("demo")}</strong></p>` : ""}<p>${esc(gen)}</p><p>${t("disclaimer")}</p>`;
}

// ---------- wiring
document.addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  if (b.dataset.lang) { state.lang = b.dataset.lang; store.set("lang", state.lang); }
  else if (b.dataset.mode) { state.mode = b.dataset.mode; store.set("mode", state.mode); }
  else if (b.dataset.tab) { state.tab = b.dataset.tab; }
  else if (b.dataset.more) { const id = b.dataset.more; state.expanded.has(id) ? state.expanded.delete(id) : state.expanded.add(id); }
  else if (b.id === "filterBtn") {
    const p = $("#filterPanel"); p.hidden = !p.hidden; b.setAttribute("aria-expanded", String(!p.hidden)); return;
  } else return;
  render();
});
document.addEventListener("change", (e) => {
  const c = e.target.dataset && e.target.dataset.cat;
  if (!c) return;
  e.target.checked ? state.hidden.delete(c) : state.hidden.add(c);
  store.set("hidden", [...state.hidden]);
  render();
});

fetch(DEMO ? "data/events.demo.json" : "data/events.json", { cache: "no-cache" })
  .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
  .then((d) => {
    DATA = { upcoming_ms: 31 * 864e5, missed_ms: 7 * 864e5, categories: [], events: [], ...d };
    TZ = DATA.timezone || TZ;
    render();
    setInterval(render, 60000);                  // keep "happening now" fresh
  })
  .catch(() => { $("#list").innerHTML = `<div class="empty">${t("load_error")}</div>`; });
