/* Tokyo Gigs - reads data/gigs.json (written daily by the scraper) and renders a filterable list. */
(() => {
  "use strict";

  const GENRES = [
    ["Rock & Indie", "--g-rock"], ["Punk & Hardcore", "--g-punk"], ["Metal", "--g-metal"],
    ["Electronic & Club", "--g-elec"], ["Experimental & Noise", "--g-exp"], ["Jazz", "--g-jazz"],
    ["Hip-Hop & R&B", "--g-hiphop"], ["Pop & Idol", "--g-pop"], ["Folk & Acoustic", "--g-folk"],
    ["Classical", "--g-classical"], ["World & Traditional", "--g-world"], ["Jam & Open Mic", "--g-jam"],
    ["Other", "--g-other"],
  ];
  const COLOR = Object.fromEntries(GENRES);
  const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const DOW_LONG = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const DOW_JA = ["日", "月", "火", "水", "木", "金", "土"];
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const MAX_PRICE = 15000;

  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const yen = (n) => "¥" + Number(n).toLocaleString("en-US");

  // ---- storage (per-browser conveniences only; never required) ----
  const store = {
    get(k, d) { try { const v = localStorage.getItem("tg:" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("tg:" + k, JSON.stringify(v)); } catch { /* private mode */ } },
  };

  // ---- dates in Tokyo time ----
  const tokyoToday = () => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tokyo" }).format(new Date());
  const parse = (iso) => { const [y, m, d] = iso.split("-").map(Number); return new Date(Date.UTC(y, m - 1, d)); };
  const fmt = (dt) => dt.toISOString().slice(0, 10);
  const addDays = (iso, n) => { const d = parse(iso); d.setUTCDate(d.getUTCDate() + n); return fmt(d); };
  const dow = (iso) => parse(iso).getUTCDay();

  const TODAY = tokyoToday();

  // ---- running as the installed Android app (Capacitor) or as a web page ----
  const CAP = window.Capacitor;
  const NATIVE = !!(CAP && CAP.isNativePlatform && CAP.isNativePlatform());
  const REPO = "davepomerlo/tokyo-gigs";
  // The app carries a copy of the listings from when it was built; fresh ones come from GitHub.
  const DATA_URLS = NATIVE
    ? [`https://raw.githubusercontent.com/${REPO}/main/docs/data/`, "https://davepomerlo.github.io/tokyo-gigs/data/"]
    : ["data/"];
  function openExternal(url) {
    const B = CAP && CAP.Plugins && CAP.Plugins.Browser;
    if (NATIVE && B) B.open({ url }).catch(() => window.open(url, "_blank"));
    else window.open(url, "_blank", "noopener");
  }
  const saved = new Set(store.get("saved", []));
  const state = Object.assign(
    { range: "week", day: null, genres: [], q: "", maxPrice: MAX_PRICE, area: "", free: false, saved: false },
    store.get("filters", {}), { day: null, q: "" }
  );
  // home-screen shortcuts ("Tonight", "This weekend") open with ?range=...
  const urlRange = new URLSearchParams(location.search).get("range");
  if (["tonight", "weekend", "week", "all"].includes(urlRange)) state.range = urlRange;
  let GIGS = [];

  // ---- theme toggle ----
  const applyTheme = (t) => { if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme; };
  applyTheme(store.get("theme", null));
  $("#themeBtn").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    const next = dark ? "light" : "dark";
    applyTheme(next); store.set("theme", next);
  });

  // ---- filtering ----
  function rangeBounds() {
    if (state.day) return [state.day, state.day];
    switch (state.range) {
      case "tonight": return [TODAY, TODAY];
      case "weekend": {
        const d = dow(TODAY);                          // Fri-Sun; if already the weekend, from today
        const fri = d === 0 ? addDays(TODAY, -2) : d === 6 ? addDays(TODAY, -1) : addDays(TODAY, 5 - d);
        return [fri < TODAY ? TODAY : fri, addDays(fri, 2)];
      }
      case "week": return [TODAY, addDays(TODAY, 6)];
      default: return [TODAY, "9999-12-31"];
    }
  }
  const priceOf = (g) => g.price_adv ?? g.price_door ?? null;
  const matchesText = (g, q) => !q || [g.title, g.venue, g.venue_ja, g.area, g.area_ja, ...(g.artists || [])]
    .some((s) => s && s.toLowerCase().includes(q));

  function passes(g, { skipDate = false, skipGenre = false } = {}) {
    if (!skipDate) {
      const [a, b] = rangeBounds();
      if ((g.end_date || g.date) < a || g.date > b) return false;
    }
    if (!skipGenre && state.genres.length && !g.genres.some((x) => state.genres.includes(x))) return false;
    if (!matchesText(g, state.q)) return false;
    if (state.area && g.area !== state.area) return false;
    if (state.free && !g.free) return false;
    if (state.saved && !saved.has(g.id)) return false;
    if (state.maxPrice < MAX_PRICE) { const p = priceOf(g); if (p != null && p > state.maxPrice) return false; }
    return true;
  }

  // ---- rendering ----
  function renderDays() {
    const counts = {};
    for (const g of GIGS) if (passes(g, { skipDate: true })) counts[g.date] = (counts[g.date] || 0) + 1;
    const n = 35, max = Math.max(1, ...Array.from({ length: n }, (_, i) => counts[addDays(TODAY, i)] || 0));
    const [a, b] = rangeBounds();
    let html = "";
    for (let i = 0; i < n; i++) {
      const iso = addDays(TODAY, i), d = dow(iso), c = counts[iso] || 0;
      const cur = state.day === iso;
      const inRange = !state.day && state.range !== "all" && iso >= a && iso <= b;
      const label = i === 0 ? "Today" : DOW[d];
      html += `<button type="button" class="day${d === 0 || d === 6 ? " weekend" : ""}${c ? "" : " empty"}${inRange ? " inrange" : ""}" data-day="${iso}"
        aria-current="${cur}" aria-label="${DOW_LONG[d]} ${parse(iso).getUTCDate()} ${MONTHS[parse(iso).getUTCMonth()]}, ${c} gigs">
        <span class="dow">${label}</span><span class="num">${parse(iso).getUTCDate()}</span>
        <span class="bar"><i style="height:${Math.round(26 * c / max)}px"></i></span><span class="cnt">${c}</span></button>`;
    }
    $("#days").innerHTML = html;
  }

  function renderGenres() {
    const counts = {};
    for (const g of GIGS) if (passes(g, { skipGenre: true })) for (const x of g.genres) counts[x] = (counts[x] || 0) + 1;
    $("#genres").innerHTML = GENRES.filter(([name]) => counts[name] || state.genres.includes(name)).map(([name, v]) =>
      `<button type="button" class="chip" style="--c:var(${v})" data-genre="${esc(name)}" aria-pressed="${state.genres.includes(name)}">${esc(name)} <span class="n">${counts[name] || 0}</span></button>`
    ).join("");
  }

  function timeCell(g) {
    if (g.start_time && g.open_time) return `<div class="time">${g.start_time}<small>doors ${g.open_time}</small></div>`;
    if (g.start_time) return `<div class="time">${g.start_time}</div>`;
    if (g.open_time) return `<div class="time">${g.open_time}<small>doors</small></div>`;
    return `<div class="time none">${g.note ? esc(g.note) : "time tbc"}</div>`;
  }
  function priceCell(g) {
    if (g.free) return `<div class="price free">Free</div>`;
    const p = priceOf(g);
    if (p == null) return `<div class="price"><small>${g.price_text ? "see info" : "price tbc"}</small></div>`;
    const sub = g.price_adv != null && g.price_door != null ? `<small>door ${yen(g.price_door)}</small>`
      : g.price_adv == null ? `<small>door</small>` : "";
    return `<div class="price">${yen(p)}${sub}</div>`;
  }
  function venueLine(g) {
    const ja = g.venue_ja && g.venue_ja !== g.venue ? ` <span class="ja">${esc(g.venue_ja)}</span>` : "";
    const area = g.area ? `, ${esc(g.area)}` : "";
    return `<b>${esc(g.venue)}</b>${ja}${area}`;
  }

  function detail(g) {
    const rows = [];
    if (g.open_time) rows.push(["Doors 開場", g.open_time]);
    if (g.start_time) rows.push(["Start 開演", g.start_time]);
    if (g.price_adv != null) rows.push(["Advance 前売", yen(g.price_adv)]);
    if (g.price_door != null) rows.push(["Door 当日", yen(g.price_door)]);
    if (g.price_text) rows.push(["Price notes", esc(g.price_text)]);
    if (g.end_date) rows.push(["Runs until", g.end_date]);
    if (g.area) rows.push(["Area", esc(g.area) + (g.area_ja && g.area_ja !== g.area ? ` <span class="ja">${esc(g.area_ja)}</span>` : "")]);
    if (g.note) rows.push(["Note", esc(g.note)]);
    if ((g.artists || []).length > 1 && g.artists.join(", ").toLowerCase() !== g.title.toLowerCase()) rows.push(["Line-up", esc(g.artists.join(", "))]);
    if ((g.tags || []).length) rows.push(["Tagged", esc(g.tags.join(", "))]);
    if (g.genre_guessed) rows.push(["Genre", "Guessed from the venue"]);
    const info = g.ticket_url || (g.sources[0] && g.sources[0].url);
    return `<div class="detail">
      <dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>
      <div class="actions">
        ${info ? `<a class="primary" href="${esc(info)}" target="_blank" rel="noopener">${g.ticket_url ? "Tickets & info" : "Gig page"}</a>` : ""}
        <button type="button" data-save="${g.id}" aria-pressed="${saved.has(g.id)}">${saved.has(g.id) ? "Saved" : "Save"}</button>
        <button type="button" data-ics="${g.id}">Add to calendar</button>
      </div>
      <div class="srcs">Listed on ${g.sources.map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a>`).join(" ")}</div>
    </div>`;
  }

  function renderList() {
    const rows = GIGS.filter((g) => passes(g));
    $("#count").textContent = `${rows.length} gig${rows.length === 1 ? "" : "s"}`;
    if (!rows.length) {
      $("#list").innerHTML = `<div class="empty-state">No gigs match these filters.<br><button type="button" data-action="reset">Clear filters</button></div>`;
      return;
    }
    const [a] = rangeBounds();
    const byDay = new Map();
    for (const g of rows) {
      const key = g.date < a ? a : g.date;                // multi-day events show on the first day in range
      if (!byDay.has(key)) byDay.set(key, []);
      byDay.get(key).push(g);
    }
    let html = "";
    for (const [iso, list] of [...byDay].sort((x, y) => x[0].localeCompare(y[0]))) {
      const dt = parse(iso), d = dt.getUTCDay();
      const rel = iso === TODAY ? "Tonight" : iso === addDays(TODAY, 1) ? "Tomorrow" : DOW_LONG[d];
      html += `<h2 class="dayhead${d === 0 || d === 6 ? " weekend" : ""}" id="d-${iso}"><span class="big">${dt.getUTCDate()}</span>
        <span class="rest">${rel}<small>${MONTHS[dt.getUTCMonth()]} ${DOW_JA[d]}曜日, ${list.length} gig${list.length === 1 ? "" : "s"}</small></span></h2>`;
      for (const g of list) {
        const dots = g.genres.filter((x) => x !== "Other").map((x) =>
          `<span class="dot${g.genre_guessed ? " guess" : ""}" style="--c:var(${COLOR[x] || "--g-other"})">${esc(x)}</span>`).join("");
        html += `<article class="gig" data-id="${g.id}">
          <button type="button" aria-expanded="false">
            ${timeCell(g)}
            <div><div class="title">${saved.has(g.id) ? '<span class="star" aria-label="Saved">★</span> ' : ""}${esc(g.title)}</div>
              <div class="venue">${venueLine(g)}</div>${dots ? `<div class="dots">${dots}</div>` : ""}</div>
            ${priceCell(g)}
          </button>
          ${detail(g)}
        </article>`;
      }
    }
    $("#list").innerHTML = html;
  }

  function renderControls() {
    document.querySelectorAll("[data-range]").forEach((b) => b.setAttribute("aria-pressed", String(!state.day && state.range === b.dataset.range)));
    $("#price").value = state.maxPrice;
    $("#priceOut").textContent = state.maxPrice >= MAX_PRICE ? "any price" : yen(state.maxPrice);
    $("#area").value = state.area;
    $("#free").checked = state.free;
    $("#saved").checked = state.saved;
  }

  function render() {
    renderControls(); renderDays(); renderGenres(); renderList();
    const { q, day, ...keep } = state; store.set("filters", keep);
  }

  // ---- calendar export ----
  // In the app a downloaded .ics goes nowhere, so open Google Calendar's "add event" page instead.
  function googleCalendar(g) {
    const d = g.date.replace(/-/g, "");
    const t = g.start_time || g.open_time;
    let dates;
    if (t) {
      const [h, m] = t.split(":").map(Number);
      const endH = h + 3, endDay = endH >= 24 ? addDays(g.date, 1).replace(/-/g, "") : d;
      const p = (n) => String(n).padStart(2, "0");
      dates = `${d}T${p(h)}${p(m)}00/${endDay}T${p(endH % 24)}${p(m)}00`;
    } else {
      dates = `${d}/${addDays(g.date, 1).replace(/-/g, "")}`;
    }
    const info = g.ticket_url || g.sources[0]?.url || "";
    const price = priceOf(g) != null ? `Price: ${yen(priceOf(g))}` : g.free ? "Free" : "";
    const q = new URLSearchParams({
      action: "TEMPLATE", text: g.title, dates, ctz: "Asia/Tokyo",
      location: [g.venue, g.venue_ja, g.area].filter(Boolean).join(", "),
      details: [price, g.open_time && "Doors " + g.open_time, info].filter(Boolean).join("\n"),
    });
    openExternal(`https://calendar.google.com/calendar/render?${q}`);
  }

  function ics(g) {
    if (NATIVE) { googleCalendar(g); return; }
    const d = g.date.replace(/-/g, "");
    const t = (g.start_time || g.open_time || "").replace(":", "");
    const pad = (s) => s.replace(/[\\,;]/g, (c) => "\\" + c).replace(/\n/g, "\\n");
    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Tokyo Gigs//EN", "BEGIN:VEVENT",
      `UID:${g.id}@tokyo-gigs`, `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`];
    if (t) {
      lines.push(`DTSTART;TZID=Asia/Tokyo:${d}T${t}00`);
      lines.push(`DURATION:PT3H`);
    } else {
      lines.push(`DTSTART;VALUE=DATE:${d}`);
    }
    lines.push(`SUMMARY:${pad(g.title)}`, `LOCATION:${pad([g.venue, g.venue_ja, g.area].filter(Boolean).join(", "))}`);
    const info = g.ticket_url || g.sources[0]?.url;
    if (info) lines.push(`URL:${info}`);
    const price = priceOf(g) != null ? `Price: ${yen(priceOf(g))}` : g.free ? "Free" : "";
    lines.push(`DESCRIPTION:${pad([price, g.open_time && "Doors " + g.open_time, info].filter(Boolean).join("\n"))}`);
    lines.push("END:VEVENT", "END:VCALENDAR");
    const blob = new Blob([lines.join("\r\n")], { type: "text/calendar" });
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `gig-${g.date}.ics` });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  // ---- events ----
  function reset() {
    Object.assign(state, { range: "week", day: null, genres: [], q: "", maxPrice: MAX_PRICE, area: "", free: false, saved: false });
    $("#q").value = "";
    render();
  }
  document.addEventListener("click", (e) => {
    const t = e.target.closest("button, a");
    if (!t) return;
    // in the app, ticket and source links open in a Chrome tab instead of replacing the app
    if (NATIVE && t.tagName === "A" && /^https?:/i.test(t.getAttribute("href") || "")) {
      e.preventDefault(); openExternal(t.href); return;
    }
    if (t.dataset.range) { state.range = t.dataset.range; state.day = null; render(); return; }
    if (t.dataset.day) {
      state.day = state.day === t.dataset.day ? null : t.dataset.day;
      render();
      if (state.day) $("#list").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      return;
    }
    if (t.dataset.genre) {
      const g = t.dataset.genre;
      state.genres = state.genres.includes(g) ? state.genres.filter((x) => x !== g) : [...state.genres, g];
      render(); return;
    }
    if (t.dataset.save) {
      const id = t.dataset.save;
      saved.has(id) ? saved.delete(id) : saved.add(id);
      store.set("saved", [...saved]);
      t.setAttribute("aria-pressed", String(saved.has(id)));
      t.textContent = saved.has(id) ? "Saved" : "Save";
      const title = t.closest(".gig").querySelector(".title");
      title.querySelector(".star")?.remove();
      if (saved.has(id)) title.insertAdjacentHTML("afterbegin", '<span class="star" aria-label="Saved">★</span> ');
      return;
    }
    if (t.dataset.ics) { ics(GIGS.find((g) => g.id === t.dataset.ics)); return; }
    if (t.id === "reset" || t.dataset.action === "reset") { reset(); return; }
    if (t.id === "moreBtn") {
      const open = t.getAttribute("aria-expanded") !== "true";
      t.setAttribute("aria-expanded", String(open));
      $("#extra").classList.toggle("open", open);
      return;
    }
    const gig = t.closest(".gig");
    if (gig && t.parentElement === gig) {
      const open = !gig.classList.contains("open");
      gig.classList.toggle("open", open);
      t.setAttribute("aria-expanded", String(open));
    }
  });
  let qTimer;
  $("#q").addEventListener("input", (e) => {
    clearTimeout(qTimer);
    qTimer = setTimeout(() => { state.q = e.target.value.trim().toLowerCase(); renderDays(); renderGenres(); renderList(); }, 150);
  });
  $("#price").addEventListener("input", (e) => { state.maxPrice = Number(e.target.value); render(); });
  $("#area").addEventListener("change", (e) => { state.area = e.target.value; render(); });
  $("#free").addEventListener("change", (e) => { state.free = e.target.checked; render(); });
  $("#saved").addEventListener("change", (e) => { state.saved = e.target.checked; render(); });

  // ---- load ----
  function since(iso) {
    const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (mins < 90) return `${mins} min ago`;
    const h = Math.round(mins / 60);
    return h < 36 ? `${h} hours ago` : `${Math.round(h / 24)} days ago`;
  }
  const STANDALONE = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const IOS = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const INSTALL_TIP = IOS && !STANDALONE
    ? `<p class="install-tip">Use it like an app: tap the Share button in Safari, then <b>Add to Home Screen</b> (ホーム画面に追加).</p>` : "";

  function renderMeta(meta) {
    if (!meta) { $("#foot").innerHTML = INSTALL_TIP; return; }
    if (meta.sample) {
      $("#banner").insertAdjacentHTML("afterbegin", `<p class="banner">Showing sample listings. Real gigs appear after the first daily scan runs on GitHub.</p>`);
    }
    const src = Object.values(meta.sources || {});
    $("#foot").innerHTML = INSTALL_TIP + `<p>Gathered from these listings, updated every morning at 5:00 Japan time. Prices are advance unless marked; always check the venue before you go.</p>
      <ul>${src.map((s) => `<li class="${s.error || s.used_previous_results ? "bad" : ""}">${esc(s.name)}: ${s.gigs} gigs${s.error ? " (failed this morning)" : s.used_previous_results ? " (using yesterday's list)" : ""}</li>`).join("")}</ul>`;
  }

  function boot(data, meta, offline = false) {
    GIGS = (data.gigs || []).filter((g) => (g.end_date || g.date) >= TODAY);
    GIGS.forEach((g) => { g.genres = g.genres?.length ? g.genres : ["Other"]; g.sources = g.sources || []; });
    $("#updated").textContent = `${GIGS.length} upcoming gigs, updated ${since(data.generated)}`;
    if (offline) {
      $("#banner").insertAdjacentHTML("beforeend",
        `<p class="banner">You're offline. Showing the listings saved ${since(data.generated)}; ticket links need a connection.</p>`);
      addEventListener("online", () => location.reload(), { once: true });
    }
    const areas = [...new Set(GIGS.map((g) => g.area).filter(Boolean))].sort();
    $("#area").insertAdjacentHTML("beforeend", areas.map((a) => `<option>${esc(a)}</option>`).join(""));
    if (state.area && !areas.includes(state.area)) state.area = "";
    renderMeta(meta);
    render();
  }

  // ---- loading in the app: GitHub first, then the last copy kept on the phone, then the built-in copy ----
  function getJSON(url, ms = 9000) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), ms);
    return fetch(url, { cache: "no-store", signal: ctl.signal })
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .finally(() => clearTimeout(timer));
  }
  async function loadNative() {
    for (const base of DATA_URLS) {
      try {
        const d = await getJSON(base + "gigs.json");
        if (!d || !Array.isArray(d.gigs)) continue;
        const m = await getJSON(base + "meta.json").catch(() => null);
        store.set("cache", { d, m });
        return boot(d, m, false);
      } catch { /* try the next source */ }
    }
    const kept = store.get("cache", null);
    if (kept && kept.d) return boot(kept.d, kept.m, true);
    try {                                          // first launch with no connection
      const d = await getJSON("data/gigs.json", 4000);
      return boot(d, await getJSON("data/meta.json", 4000).catch(() => null), true);
    } catch {
      $("#updated").textContent = "Listings couldn't be loaded.";
      $("#list").innerHTML = `<div class="empty-state">Connect to the internet and reopen the app to load the gig listings.</div>`;
    }
  }

  // tell the app user when GitHub has built a newer version of the app
  async function checkAppUpdate() {
    try {
      const mine = await getJSON("app-version.json", 3000);
      const latest = await getJSON(`https://api.github.com/repos/${REPO}/releases/latest`, 6000);
      if (mine.tag && latest.tag_name && latest.tag_name !== mine.tag) {
        $("#banner").insertAdjacentHTML("beforeend",
          `<p class="banner">A new version of the app is ready. <a href="https://github.com/${REPO}/releases/latest/download/tokyo-gigs.apk">Download the update</a></p>`);
      }
    } catch { /* offline, or a web build without a version file */ }
  }

  if (window.__GIGS__) {                         // single-file preview build
    boot(window.__GIGS__, window.__META__);
  } else if (NATIVE) {
    loadNative().then(checkAppUpdate);
  } else {
    let offline = false;
    Promise.all([
      fetch("data/gigs.json", { cache: "no-cache" }).then((r) => {
        if (!r.ok) throw new Error(r.status);
        offline = r.headers.get("X-From-Cache") === "1";
        return r.json();
      }),
      fetch("data/meta.json", { cache: "no-cache" }).then((r) => r.ok ? r.json() : null).catch(() => null),
    ]).then(([d, m]) => boot(d, m, offline)).catch(() => {
      $("#updated").textContent = "Listings couldn't be loaded.";
      $("#list").innerHTML = navigator.onLine
        ? `<div class="empty-state">The gig list file is missing. Run the "Daily gig scan" workflow on GitHub to create it.</div>`
        : `<div class="empty-state">You're offline and no listings are saved yet. Open the app once with a connection and they'll be kept for offline use.</div>`;
    });
  }

  // ---- installed-app behaviour ----
  // An installed app can stay open for days: when it comes back to the front on a new
  // Tokyo day, reload so "Tonight" and the day strip move on (and fresh listings load).
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && tokyoToday() !== TODAY) location.reload();
  });

  if (!NATIVE && "serviceWorker" in navigator && location.protocol !== "file:") {
    addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
  }

  // Android/desktop Chrome offer an install prompt; show our own button for it.
  // (iPhone has no prompt: Share > Add to Home Screen, explained in the footer.)
  let installEvt = null;
  addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    installEvt = e;
    $("#installBtn").hidden = false;
  });
  $("#installBtn").addEventListener("click", async () => {
    if (!installEvt) return;
    installEvt.prompt();
    await installEvt.userChoice;
    installEvt = null;
    $("#installBtn").hidden = true;
  });
  addEventListener("appinstalled", () => { $("#installBtn").hidden = true; });

})();
