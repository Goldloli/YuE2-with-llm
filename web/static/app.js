/* YuE2 Studio frontend — Suno-replica interactions */
"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
const audio = $("#audio-el");

const state = {
  songs: [],
  view: "create",          // create | library | detail
  mode: "simple",          // simple | advanced
  cot: "full",
  vgender: null,           // null | male | female
  loras: [],               // installed adapters from /api/loras
  lora: null,              // selected adapter id | null
  backend: "torch",        // torch | mlx
  attachAbc: null,         // {name, text} score attached to the next create
  attachName: null,        // pending name while the attach modal is open
  examples: null,          // cached /api/examples
  feedTab: "all",          // all | liked | upload
  feedSearch: "",
  feedFilter: "all",       // all | active | complete | failed
  sort: "new",
  feedGrid: false,
  libTab: "song",
  libSearch: "",
  detailId: null,
  server: { transcribe_available: false },
  playlist: [],
  playIndex: -1,
  playing: false,
  shuffle: false,
  repeat: false,
  liked: new Set(JSON.parse(localStorage.getItem("yue2.liked") || "[]")),
  played: new Set(JSON.parse(localStorage.getItem("yue2.played") || "[]")),
};

function stageLabel(k, fb) {
  const v = t("stage." + k);
  return v === "stage." + k ? (fb ?? t("stage.working")) : v;
}

const STYLE_SUGGESTIONS = [
  ["cinematic", "orchestral", "slow burn", "emotive piano", "wide strings"],
  ["reggae", "chorus in minor", "woodwinds", "pop edm", "neomelodico"],
  ["early 2000s", "b major", "blue notes", "punk metal", "trumpet"],
  ["lo-fi", "dusty drums", "tape hiss", "jazz guitar", "rainy day"],
  ["synthwave", "analog pads", "night drive", "retro arps", "gated reverb"],
  ["folk", "fingerpicked acoustic", "close vocal", "harmonies", "field recording"],
  ["chinese documentary", "meditative", "sparse texture", "long reverb", "pipa"],
  ["hyperpop", "pitched vocals", "glitch", "bright synths", "140 bpm"],
  ["中国风", "古筝", "五声音阶", "抒情慢板", "唯美"],
  ["国风电子", "电子舞曲", "琵琶", "大气", "律动"],
  ["日系动漫", "钢琴", "清新", "青春", "治愈"],
  ["城市流行", "夜晚", "霓虹", "萨克斯", "复古"],
  ["纯音乐", "氛围", "舒缓", "钢琴", "阅读背景"],
];
let styleDeck = 0;

/* ---------------- helpers ---------------- */

function fmtTime(s) {
  if (s == null || !isFinite(s)) return "0:00";
  s = Math.max(0, Math.round(s));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function hashCode(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
  return h;
}

const COVER_PALETTES = [
  ["#2b3a55", "#c96f4a"], ["#3d2c4d", "#d4a24e"], ["#1e3d3a", "#7fb069"],
  ["#402e32", "#c46a82"], ["#2a3244", "#6a8eae"], ["#453423", "#d9a441"],
  ["#253342", "#8a7ec7"], ["#3a2e2e", "#b5754f"], ["#23352b", "#94b46a"],
  ["#33253f", "#c97b8d"], ["#1f2f45", "#5fa8a0"], ["#3c3229", "#cd9153"],
];

function coverFallback(id) {
  const h = hashCode(id);
  const [c1, c2] = COVER_PALETTES[h % COVER_PALETTES.length];
  return `background: linear-gradient(${100 + (h % 160)}deg, ${c1}, ${c2});`;
}

/* Deterministic per-song cover art: flow-field strokes + vignette + grain on a
   256px canvas, exported as a cached JPEG dataURL. Same id -> same cover. */
const COVER_SIZE = 256;
const coverCache = new Map();

function mulberry32(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function coverArt(id) {
  const size = COVER_SIZE;
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  const g = cv.getContext("2d");
  const rand = mulberry32(hashCode(id));
  const hue = Math.floor(rand() * 360);
  const bg = g.createLinearGradient(0, 0, size, size);
  bg.addColorStop(0, `hsl(${hue} 30% 9%)`);
  bg.addColorStop(1, `hsl(${(hue + 40) % 360} 26% 14%)`);
  g.fillStyle = bg;
  g.fillRect(0, 0, size, size);
  const colors = [0, 1, 2].map((i) =>
    `hsl(${(hue + i * 44 + Math.floor(rand() * 20)) % 360} ${58 + Math.floor(rand() * 22)}% ${44 + Math.floor(rand() * 16)}%)`);
  for (let i = 0; i < 420; i++) {
    let x = rand() * size, y = rand() * size;
    const steps = 14 + Math.floor(rand() * 26);
    g.beginPath();
    g.moveTo(x, y);
    for (let s = 0; s < steps; s++) {
      const a = (Math.sin(x * 0.018) + Math.cos(y * 0.021) + rand() * 0.5) * 1.6;
      x += Math.cos(a) * 2.6;
      y += Math.sin(a) * 2.6;
      g.lineTo(x, y);
    }
    g.strokeStyle = colors[Math.floor(rand() * 3)];
    g.globalAlpha = 0.05 + rand() * 0.09;
    g.lineWidth = 0.6 + rand() * 2.2;
    g.stroke();
  }
  g.globalAlpha = 1;
  const vg = g.createRadialGradient(size / 2, size / 2, size * 0.32, size / 2, size / 2, size * 0.78);
  vg.addColorStop(0, "rgba(0,0,0,0)");
  vg.addColorStop(1, "rgba(0,0,0,0.5)");
  g.fillStyle = vg;
  g.fillRect(0, 0, size, size);
  const px = g.getImageData(0, 0, size, size);
  for (let i = 0; i < px.data.length; i += 4) {
    const n = (rand() - 0.5) * 16;
    px.data[i] += n;
    px.data[i + 1] += n;
    px.data[i + 2] += n;
  }
  g.putImageData(px, 0, 0);
  return cv.toDataURL("image/jpeg", 0.85);
}

function coverStyle(id) {
  let url = coverCache.get(id);
  if (url === undefined) {
    try { url = coverArt(id); } catch { url = null; }
    coverCache.set(id, url);
  }
  if (url === null) return coverFallback(id);
  const base = COVER_PALETTES[hashCode(id) % COVER_PALETTES.length][0];
  return `background-color: ${base}; background-image: url(${url}); background-size: cover; background-position: center;`;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* Show the user's original prompt text when a translation exists; English tags go to the tooltip. */
function dispStyle(song) {
  return song.style_original || song.style || "";
}

function styleTitle(song) {
  return song.style_original && song.style ? ` title="${esc(song.style)}"` : "";
}

function toast(msg, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

async function api(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

const isActive = (s) => s.status === "queued" || s.status === "running";
const isPlayable = (s) => s.status === "complete" && !s.plan_only;

function dateGroup(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleDateString(currentLang === "zh" ? "zh-CN" : "en-US", { weekday: "long", month: "short", day: "numeric" });
}

function versionChip(song) {
  if (song.kind === "upload") return `<span class="ver">${t("row.upload")}</span>`;
  const label = { full: "YuE2·Full", melody: "YuE2·Melody", off: "YuE2·Free" }[song.cot] || "YuE2";
  return `<span class="ver">${label}</span>`;
}

function saveSets() {
  localStorage.setItem("yue2.liked", JSON.stringify([...state.liked]));
  localStorage.setItem("yue2.played", JSON.stringify([...state.played]));
}

/* ---------------- data ---------------- */

const prevStatus = new Map();

function handleCompletions(songs) {
  const s = state.server || {};
  for (const song of songs) {
    const prev = prevStatus.get(song.id);
    prevStatus.set(song.id, song.status);
    if (prev === undefined || prev === "complete" || song.status !== "complete" || !isPlayable(song)) continue;
    if (s.autoplay_on_complete) playSong(song.id);
    if (s.notify_on_complete && typeof Notification !== "undefined" && Notification.permission === "granted") {
      try { new Notification(song.title || "YuE2", { body: t("notify.done") }); } catch (e) { /* ignore */ }
    }
  }
}

async function refreshSongs() {
  try {
    const songs = await api("/api/songs");
    state.songs = songs;
    handleCompletions(songs);
    renderAll();
  } catch (e) { /* server restarting */ }
}

async function refreshState() {
  try {
    const s = await api("/api/state");
    state.server = s;
    const busy = s.current != null;
    const st = s.model === "ready" && busy ? "busy" : s.model;
    const pill = $("#status-pill");
    pill.dataset.state = st;
    pill.textContent =
      st === "ready" ? t("status.ready") :
      st === "busy" ? t("status.busy") :
      st === "loading" ? t("status.loading") :
      st === "failed" ? t("status.failed") : t("status.init");
    pill.title = `${t("settings.model")}: ${s.model} · ${t("settings.device")}: ${s.device}` +
      (s.queue ? ` · queue ${s.queue}` : "") +
      (s.transcribe_available ? ` · ${t("settings.trReady")}` : ` · ${t("settings.trMissing")}`);
    const active = state.songs.filter(isActive).length;
    const badge = $("#jobs-badge");
    badge.hidden = active === 0;
    badge.textContent = active;
  } catch (e) {}
}

/* ---------------- feed rendering ---------------- */

function feedItems() {
  let items = [...state.songs];
  if (state.feedTab === "liked") items = items.filter((s) => state.liked.has(s.id));
  else if (state.feedTab === "upload") items = items.filter((s) => s.kind === "upload");
  if (state.feedFilter === "active") items = items.filter(isActive);
  else if (state.feedFilter === "complete") items = items.filter(isPlayable);
  else if (state.feedFilter === "failed") items = items.filter((s) => s.status === "failed" || s.status === "cancelled");
  const q = state.feedSearch.trim().toLowerCase();
  if (q) items = items.filter((s) => (s.title + " " + (s.style || "") + " " + (s.style_original || "")).toLowerCase().includes(q));
  if (state.sort === "old") items.reverse();
  else if (state.sort === "title") items.sort((a, b) => a.title.localeCompare(b.title));
  return items;
}

function statusBlock(song) {
  if (song.status === "queued")
    return `<div class="row-status"><i class="ph ph-hourglass-medium spin"></i>${t("row.queued")}</div>
            <button class="row-cancel" data-action="cancel">${t("row.cancel")}</button>`;
  if (song.status === "running") {
    const p = song.progress || {};
    const bits = [];
    if (p.abc_tokens) bits.push(t("row.scoreTokens", { n: p.abc_tokens }));
    if (p.semantic_tokens) bits.push(t("row.songTokens", { n: p.semantic_tokens }));
    const det = song.stage === "planning" || song.stage === "composing";
    const pct = Math.min(95, (p.semantic_tokens || 0) / 90);
    return `<div class="row-status"><i class="ph ph-circle-notch spin"></i>${esc(stageLabel(song.stage))} ${bits.length ? "· " + esc(bits.join(" · ")) : ""}</div>
            <div class="row-progress"><div class="${det ? "" : "indet"}" style="width:${det ? pct : 30}%"></div></div>
            <button class="row-cancel" data-action="cancel">${t("row.cancel")}</button>`;
  }
  if (song.status === "failed")
    return `<div class="row-status error"><i class="ph ph-warning-circle"></i>${song.kind === "upload" ? t("row.transcribeFailed") : t("row.genFailed")}</div>
            <div class="row-status">${esc(song.error || t("row.unknownErr"))}</div>`;
  if (song.status === "cancelled")
    return `<div class="row-status"><i class="ph ph-prohibit"></i>${t("row.cancelled")}</div>`;
  if (song.status === "complete" && song.plan_only)
    return `<div class="row-status"><i class="ph ph-music-notes-simple"></i>${t("detail.planOnly")} · ${t("detail.renderScore")}</div>`;
  return "";
}

function songRow(song) {
  const playingThis = state.playlist[state.playIndex]?.id === song.id && state.playing;
  const playable = isPlayable(song);
  const fresh = !state.played.has(song.id) && playable;
  const style = song.kind === "upload" ? t("row.uploadedAudio") : dispStyle(song);
  const liked = state.liked.has(song.id);
  return `<div class="song-row ${playingThis ? "playing" : ""}" data-id="${song.id}">
    ${fresh ? '<span class="row-new"></span>' : ""}
    <div class="row-cover" style="${coverStyle(song.id)}" data-action="play">
      ${playable ? `<div class="cover-play"><span><i class="ph-fill ${playingThis ? "ph-pause" : "ph-play"}"></i></span></div>` : `<i class="ph ${song.kind === "upload" ? "ph-file-audio" : "ph-music-note"}"></i>`}
      ${song.audio_seconds ? `<span class="cover-dur">${fmtTime(song.audio_seconds)}</span>` : ""}
    </div>
    <div class="row-main" data-action="detail">
      <div class="row-title">${esc(song.title)} ${versionChip(song)}</div>
      ${playable
        ? `<div class="row-style"${styleTitle(song)}>${esc(style)}</div>
           <div class="row-actions">
             <button class="row-act ${liked ? "on" : ""}" data-action="like" title="${t("row.like")}"><i class="ph-${liked ? "fill" : "regular"} ph-thumbs-up"></i></button>
             <button class="row-act" data-action="dislike" title="${t("row.dislike")}"><i class="ph ph-thumbs-down"></i></button>
             <button class="row-act pill" data-action="download" title="${t("row.download")}"><i class="ph ph-download"></i>${t("row.download")}</button>
           </div>`
        : statusBlock(song)}
    </div>
    <div class="row-side">
      ${(playable || song.plan_only) && song.has_score ? `<button class="remix-pill" data-action="cover"><i class="ph ph-arrows-clockwise"></i>${t("row.remix")}</button>` : ""}
      ${playable && song.kind === "song" ? `<button class="remix-pill" data-action="edit"><i class="ph ph-pencil-simple"></i>${t("row.edit")}</button>` : ""}
      <button class="dots-btn" data-action="menu"><i class="ph ph-dots-three"></i></button>
    </div>
  </div>`;
}

function gridCard(song) {
  const playingThis = state.playlist[state.playIndex]?.id === song.id && state.playing;
  const playable = isPlayable(song);
  const style = song.kind === "upload" ? t("row.uploadedAudio") : dispStyle(song);
  return `<div class="grid-card" data-id="${song.id}">
    <div class="grid-cover" style="${coverStyle(song.id)}" data-action="play">
      ${playable ? `<div class="cover-play"><span><i class="ph-fill ${playingThis ? "ph-pause" : "ph-play"}"></i></span></div>` : `<i class="ph ph-music-note"></i>`}
      ${song.audio_seconds ? `<span class="cover-dur">${fmtTime(song.audio_seconds)}</span>` : ""}
    </div>
    <div class="row-title" data-action="detail">${esc(song.title)} ${versionChip(song)}</div>
    <div class="row-style" data-action="detail"${styleTitle(song)}>${esc(playable ? style : stageLabel(song.stage, song.status))}</div>
  </div>`;
}

function renderFeed() {
  const items = feedItems();
  const list = $("#feed-list");
  $("#feed-empty").hidden = items.length > 0;
  if (state.feedGrid) {
    list.innerHTML = `<div class="grid-wrap">${items.map(gridCard).join("")}</div>`;
    return;
  }
  const groups = new Map();
  for (const s of items) {
    const key = dateGroup(s.created_at || 0);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(s);
  }
  list.innerHTML = [...groups.entries()].map(([day, songs]) =>
    `<div class="feed-date">${day}</div>${songs.map(songRow).join("")}`).join("");
}

/* ---------------- library rendering ---------------- */

function libItems() {
  let items = state.songs.filter(isPlayable);
  if (state.libTab === "upload") items = state.songs.filter((s) => s.kind === "upload");
  else if (state.libTab === "liked") items = items.filter((s) => state.liked.has(s.id));
  else items = items.filter((s) => s.kind === "song");
  const q = state.libSearch.trim().toLowerCase();
  if (q) items = items.filter((s) => (s.title + " " + (s.style || "") + " " + (s.style_original || "")).toLowerCase().includes(q));
  return items;
}

function renderLibrary() {
  const items = libItems();
  $("#lib-list").innerHTML = `<div class="grid-wrap">${items.map(gridCard).join("")}</div>`;
  $("#library-empty").hidden = items.length > 0;
}

function renderAll() {
  renderFeed();
  renderLibrary();
  if (state.detailId) renderDetail(state.detailId, true);
}

/* ---------------- detail view ---------------- */

let detailSig = null;
async function renderDetail(id, soft = false) {
  let d;
  try { d = await api(`/api/songs/${id}`); }
  catch (e) { if (!soft) { toast(e.message, true); closeDetail(); } return; }
  const sig = JSON.stringify([d.status, d.stage, d.progress, d.audio_seconds, d.error,
                              d.has_latents, d.decoder || null, d.plan_only || false, d.sampling || null, d.lora || null]);
  if (soft && state.detailId === id && detailSig === sig) return;
  const keepTech = $(".tech") ? $(".tech").open : false;
  const keepReport = $("#score-report") && !$("#score-report").hidden
    ? { cls: $("#score-report").className, text: $("#score-report").textContent } : null;
  const sameSong = state.detailId === id;
  const detailScroller = $("#detail-content");
  const keepScroll = sameSong ? detailScroller.scrollTop : 0;
  state.detailId = id;
  detailSig = sig;
  $("#view-detail").classList.add("open");
  const playable = isPlayable(d);
  const score = d.edited_abc ?? d.abc;
  const hasScore = score != null;
  const liked = state.liked.has(d.id);
  const created = new Date((d.created_at || 0) * 1000);
  const dateStr = created.toLocaleDateString(currentLang === "zh" ? "zh-CN" : "en-US", { year: "numeric", month: currentLang === "zh" ? "long" : "short", day: "numeric" });
  const meta = [dateStr, d.audio_seconds ? fmtTime(d.audio_seconds) : null, d.cot ? "· " + d.cot : null,
                d.plan_only ? "· " + t("detail.planOnly") : null, d.lora ? "· LoRA: " + d.lora : null].filter(Boolean).join(" ");

  const tabs = [];
  if (d.has_lyrics) tabs.push(["lyrics", t("detail.lyrics")]);
  if (hasScore) tabs.push(["score", t("detail.score")]);

  const tech = (d.tech || {});
  const res = tech["result.json"] || {};
  const cfg = tech["config.json"] || {};
  const req = tech["request.json"] || {};
  const techRows = [];
  if (d.seed != null) techRows.push(["Seed", `${d.seed}`]);
  const resBackend = res.backend || "";
  techRows.push([t("tech.backend"),
    (d.backend || "torch") === "mlx"
      ? (resBackend.startsWith("mlx-") ? `MLX · ${variantText(resBackend.slice(4))}` : "MLX · 8-bit")
      : "PyTorch · MPS"]);
  const decoder = cfg.decoder_release || d.decoder;
  if (decoder) techRows.push([t("tech.decoder"), decoder]);
  if (d.lora) techRows.push(["LoRA", d.lora]);
  const cfgScale = d.cfg_scale ?? req.cfg_scale;
  if (cfgScale != null) techRows.push([t("tech.cfg"), `${cfgScale}`]);
  if (d.sampling && Object.keys(d.sampling).length) {
    techRows.push([t("tech.sampling"), Object.entries(d.sampling).map(([k, v]) => `${k}=${v}`).join(" · ")]);
  }
  if (d.realaudio && d.realaudio.frames) {
    techRows.push([t("tech.realaudioFrames"),
      `${d.realaudio.frames} @25Hz · ${Math.round(d.realaudio.seconds || 0)}s`]);
  }
  const transfer = d.transfer || tech["transfer.json"] || null;
  if (transfer) {
    techRows.push([t("tech.transfer"),
      `voc ${transfer.vocal_notes_before}→${transfer.vocal_notes_after ?? 0} · ins ${transfer.output_ins_notes}`
      + (transfer.unaltered_ins_notes != null ? ` (${transfer.unaltered_ins_notes} ${t("tech.transferKept")})` : "")]);
  }
  if (res.sample_rate) techRows.push([t("tech.sampleRate"), `${res.sample_rate} Hz`]);
  const tm = res.timing || {};
  const timeBits = [];
  for (const [label, value] of [["ABC", tm.abc?.seconds], ["NAR", tm.nar_seconds], ["VAE", tm.vae_seconds],
                                [t("tech.e2e"), tm.e2e_seconds || tm.total]]) {
    if (value) timeBits.push(`${label} ${Math.round(value)}s`);
  }
  if (timeBits.length) techRows.push([t("tech.timing"), timeBits.join(" · ")]);
  if (res.identity) techRows.push([t("tech.identity"), `${String(res.identity).slice(0, 20)}…`]);
  const trunc = res.truncated || d.truncated;
  if (trunc != null) {
    const label = typeof trunc === "object"
      ? [trunc.abc ? "abc" : null, trunc.semantic ? "semantic" : null].filter(Boolean).join(", ") || "—"
      : `${trunc}`;
    techRows.push([t("tech.truncated"), label]);
  }
  const techBlock = techRows.length ? `<details class="tech"><summary><i class="ph ph-info"></i>${t("tech.title")}</summary>
      <dl class="tech-grid">${techRows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl></details>` : "";

  detailScroller.innerHTML = `
    <div class="detail-hero">
      <div class="detail-cover" style="${coverStyle(d.id)}">
        ${playable ? "" : `<i class="ph ph-music-note"></i>`}
        ${d.kind === "song" && playable ? `<button class="dc-edit" data-d="edit"><i class="ph ph-pencil-simple"></i>${t("detail.edit")}</button>` : ""}
      </div>
      <div class="detail-info">
        <div class="detail-title">${esc(d.title)}</div>
        <div class="detail-artist"><span class="sb-avatar"><i class="ph ph-user"></i></span>${t("detail.artist")}</div>
        ${d.kind === "upload" ? `<div class="detail-style" id="detail-style">${t("detail.uploadDesc")}</div>` : ""}
        <div class="detail-meta">${meta}${d.truncated && (d.truncated.abc || d.truncated.semantic) ? ` · <span style="color:var(--danger)">${t("detail.truncated")}</span>` : ""}</div>
        <div class="detail-actions">
          ${playable ? `<button class="dact primary" data-d="play"><i class="ph-fill ph-play"></i>${t("detail.play")}</button>` : ""}
          ${!playable && d.plan_only && hasScore ? `<button class="dact primary" data-d="edit"><i class="ph ph-music-notes"></i>${t("detail.renderScore")}</button>` : ""}
          ${(playable || d.plan_only) && hasScore ? `<button class="dact" data-d="cover"><i class="ph ph-arrows-clockwise"></i>${t("detail.remix")}</button>` : ""}
          ${d.kind === "song" && playable ? `<button class="dact" data-d="edit"><i class="ph ph-pencil-simple"></i>${t("detail.edit")}</button>` : ""}
          ${playable && d.has_latents ? `<button class="dact icon" data-d="redecode" title="${t("detail.redecode")}"><i class="ph ph-swap"></i></button>` : ""}
          ${playable ? `<button class="dact icon ${liked ? "on" : ""}" data-d="like" title="${t("detail.like")}"><i class="ph-${liked ? "fill" : "regular"} ph-thumbs-up"></i></button>` : ""}
          ${playable ? `<button class="dact icon" data-d="download" title="${t("detail.download")}"><i class="ph ph-download"></i></button>` : ""}
          ${d.kind === "upload" ? `<button class="dact" data-d="rebuild"><i class="ph ph-waveform"></i>${t("detail.rebuild")}</button>` : ""}
          ${isActive(d) ? `<button class="dact" data-d="cancel"><i class="ph ph-stop"></i>${t("detail.cancel")}</button>` : ""}
          <button class="dact icon danger" data-d="delete" title="${t("detail.delete")}"><i class="ph ph-trash"></i></button>
        </div>
        ${!playable ? `<div class="detail-status">${statusBlock(d)}</div>` : ""}
      </div>
    </div>
    ${d.kind === "song" ? `
    <div class="detail-style-card">
      <div class="dsc-head"><span>${t("detail.stylesTitle")}</span>
        <button class="cp-tool" data-d="copy-style" title="${t("detail.copyStyle")}"><i class="ph ph-copy"></i></button>
      </div>
      <div class="dsc-text"${styleTitle(d)}>${esc(dispStyle(d))}</div>
    </div>` : ""}
    ${techBlock}
    ${tabs.length ? `
      <div class="detail-tabs">${tabs.map(([k, l], i) => `<button class="dtab ${i === 0 ? "active" : ""}" data-tab="${k}">${l}</button>`).join("")}</div>
      <div class="detail-pane" data-pane="lyrics" ${tabs[0][0] === "lyrics" ? "" : "hidden"}><div class="lyrics-box">${esc(d.lyrics)}</div></div>
      <div class="detail-pane" data-pane="score" ${tabs[0][0] === "score" ? "" : "hidden"}>
        <textarea class="score-editor" id="score-editor" spellcheck="false">${esc(score)}</textarea>
        <p class="score-note">${t("detail.scoreNote")}</p>
        <div class="score-actions">
          <button class="ghost-btn" data-d="save-score"><i class="ph ph-floppy-disk"></i>${t("detail.saveScore")}</button>
          <button class="ghost-btn" data-d="check-score"><i class="ph ph-check-circle"></i>${t("detail.check")}</button>
          ${d.kind === "song" ? `<button class="ghost-btn primary" data-d="edit"><i class="ph ph-arrows-clockwise"></i>${t("detail.renderEdit")}</button>` : `<button class="ghost-btn primary" data-d="cover"><i class="ph ph-arrows-clockwise"></i>${t("detail.remixWithScore")}</button>`}
        </div>
        <div class="score-report" id="score-report" hidden></div>
      </div>` : ""}
  `;
  if (keepScroll) detailScroller.scrollTop = keepScroll;
  if (keepTech) { const techEl = $(".tech"); if (techEl) techEl.open = true; }
  if (keepReport) {
    const box = $("#score-report");
    if (box) { box.className = keepReport.cls; box.textContent = keepReport.text; box.hidden = false; }
  }
}

/* ---------------- views ---------------- */

function showView(v) {
  state.view = v;
  $("#view-create").hidden = v !== "create";
  $("#view-library").hidden = v !== "library";
  $("#view-models").hidden = v !== "models";
  $("#view-llm").hidden = v !== "llm";
  $("#create-panel").hidden = v !== "create";
  $$(".sb-item[data-nav]").forEach((b) => b.classList.toggle("active",
    (v === "create" && b.dataset.nav === "create") ||
    (v === "library" && b.dataset.nav === "library") ||
    (v === "models" && b.dataset.nav === "models") ||
    (v === "llm" && b.dataset.nav === "llm")));
  if (v === "library") renderLibrary();
  if (v === "models") openModels(); else stopModelsPolling();
  if (v === "llm") openLlm();
  else if (chatData.streaming) stopChat();
}

function openDetail(id) {
  state.detailId = id;
  renderDetail(id);
}

function closeDetail() {
  state.detailId = null;
  detailSig = null;
  $("#view-detail").classList.remove("open");
}

$$(".sb-item[data-nav]").forEach((btn) =>
  btn.addEventListener("click", () => {
    const nav = btn.dataset.nav;
    if (nav === "create") showView("create");
    else if (nav === "library" || nav === "user") showView("library");
    else if (nav === "models") showView("models");
    else if (nav === "llm") showView("llm");
    else if (nav === "notifications") toast(t("toast.activeJobs", { n: state.songs.filter(isActive).length }));
    else if (nav === "settings") openSettings();
  })
);

$("#detail-close").addEventListener("click", () => closeDetail());
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && state.detailId) closeDetail();
});

/* ---------------- create panel ---------------- */

function refreshCreateBtn() {
  const simple = state.mode === "simple";
  const val = (simple ? $("#simple-desc").value : $("#adv-style").value + " " + $("#adv-lyrics").value).trim();
  $("#create-btn").disabled = !val;
}

$$("#mode-toggle .cp-mode-btn").forEach((btn) =>
  btn.addEventListener("click", () => setMode(btn.dataset.mode))
);

$("#attach-audio").addEventListener("click", openUpload);
$("#simple-plus").addEventListener("click", openUpload);

/* attach an ABC score to the next create */
function updateAttachChip() {
  const chip = $("#attach-chip");
  if (!state.attachAbc) { chip.hidden = true; return; }
  chip.hidden = false;
  $("#attach-chip-name").textContent = `${t("score.attached")} · ${state.attachAbc.name}`;
}
$("#attach-chip-clear").addEventListener("click", () => { state.attachAbc = null; updateAttachChip(); });

async function openScoreAttach() {
  if (state.examples === null) {
    try { state.examples = await api("/api/examples"); } catch (e) { state.examples = {}; }
  }
  openModal(modalShell(t("score.attachTitle"), `
    <div class="input-shell"><label class="input-label">${t("score.label")}</label>
      <textarea id="score-text" rows="10" spellcheck="false" placeholder="${esc(t("score.ph"))}">${state.attachAbc ? esc(state.attachAbc.text) : ""}</textarea></div>
    <div class="score-attach-tools">
      <button class="ghost-btn" id="score-file"><i class="ph ph-upload-simple"></i>${t("score.file")}</button>
      <button class="ghost-btn" id="score-example"><i class="ph ph-book-open"></i>${t("score.example")}</button>
    </div>
    <button class="create-btn" data-m="attach-score"><i class="ph-fill ph-check"></i>${t("score.attach")}</button>
  `));
  $("#score-file").addEventListener("click", () => $("#abc-input").click());
  $("#score-example").addEventListener("click", (e) => {
    e.stopPropagation();
    const scores = (state.examples && state.examples.scores) || {};
    const names = Object.keys(scores);
    if (!names.length) { toast(t("score.ph"), true); return; }
    const rect = e.currentTarget.getBoundingClientRect();
    openDrop(rect.left, rect.bottom + 6, names.map((n) => ({
      label: n, run: () => { $("#score-text").value = scores[n]; state.attachName = n; },
    })));
  });
}
$("#attach-score").addEventListener("click", openScoreAttach);
$("#abc-input").addEventListener("change", () => {
  const f = $("#abc-input").files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = () => {
    const area = $("#score-text");
    if (area) area.value = String(reader.result);
    state.attachName = f.name;
  };
  reader.readAsText(f);
  $("#abc-input").value = "";
});

$$(".cp-collapse[data-collapse]").forEach((btn) =>
  btn.addEventListener("click", () => {
    const body = document.querySelector(`[data-body="${btn.dataset.collapse}"]`);
    body.hidden = !body.hidden;
    btn.classList.toggle("closed", body.hidden);
  })
);

$("#more-toggle").addEventListener("click", () => {
  const body = $("#more-body");
  body.hidden = !body.hidden;
  $("#more-toggle").classList.toggle("closed", body.hidden);
  $("#more-toggle").querySelector("i").className = body.hidden ? "ph ph-caret-right" : "ph ph-caret-down";
});

function resetMoreOptions() {
  state.vgender = null;
  $$("#vgender-opts button").forEach((b) => b.classList.remove("active"));
  ["adv-title", "adv-seed", "adv-cfg"].forEach((id) => { $("#" + id).value = ""; });
  $("#adv-instrumental").checked = false;
  $("#adv-planonly").checked = false;
  ["sam-temperature", "sam-topp", "sam-topk", "adv-maxsec", "sam-odesteps"].forEach((id) => { $("#" + id).value = ""; });
  applyFormDefaults();
}
$("#more-reset").addEventListener("click", () => { resetMoreOptions(); toast(t("toast.optionsReset")); });
$("#style-clear").addEventListener("click", () => {
  const el = $("#adv-style");
  el.value = "";
  el.dispatchEvent(new Event("input", { bubbles: true }));
});

/* LoRA style adapters */
function loraLabel() {
  if (!state.lora) return t("cp.loraNone");
  const item = state.loras.find((l) => l.id === state.lora);
  return item ? item.label : state.lora;
}

function loraSub(l) {
  return [l.rank ? `Rank ${l.rank}` : null, l.branch ? l.branch.toUpperCase() : null, "LoRA"].filter(Boolean).join(" · ");
}

function refreshModelPill() {
  const pill = $("#model-pill-label");
  const base = state.backend === "mlx" ? "YuE2-3B · MLX" : COT_LABELS()[state.cot];
  pill.textContent = state.lora ? `${base} + ${loraLabel()}` : base;
  pill.title = pill.textContent;
}

function setLora(id) {
  if (state.backend === "mlx" && id !== null) { toast(t("model.mlxNoLora"), true); return; }
  state.lora = id;
  $("#lora-label").textContent = loraLabel();
  refreshModelPill();
}

function setBackend(b) {
  if (b === state.backend) return;
  state.backend = b;
  if (b === "mlx" && state.lora) {
    state.lora = null;
    $("#lora-label").textContent = loraLabel();
    toast(t("model.mlxNoLora"));
  }
  refreshModelPill();
}

async function refreshLoras() {
  try {
    state.loras = await api("/api/loras");
    if (!state.loras.some((l) => l.id === state.lora)) state.lora = null;
    $("#lora-row").hidden = state.loras.length === 0;
    $("#lora-label").textContent = loraLabel();
    refreshModelPill();
  } catch (e) { /* server restarting */ }
}

$("#lora-pick").addEventListener("click", (e) => {
  const rect = e.currentTarget.getBoundingClientRect();
  openDrop(rect.right - 220, rect.bottom + 6, [
    { label: t("cp.loraNone"), active: state.lora === null, run: () => setLora(null) },
    ...state.loras.map((l) => ({
      label: l.label, sub: loraSub(l), active: state.lora === l.id,
      run: () => setLora(l.id),
    })),
  ]);
});

$$("#vgender-opts button").forEach((btn) =>
  btn.addEventListener("click", () => {
    const v = btn.dataset.vg;
    state.vgender = state.vgender === v ? null : v;
    $$("#vgender-opts button").forEach((b) => b.classList.toggle("active", b.dataset.vg === state.vgender));
  })
);

function renderStyleChips() {
  const deck = STYLE_SUGGESTIONS[styleDeck % STYLE_SUGGESTIONS.length];
  $$("#style-chips .cp-chip.sugg").forEach((c) => c.remove());
  for (const s of deck) {
    const b = document.createElement("button");
    b.className = "cp-chip sugg";
    b.textContent = s;
    b.addEventListener("click", () => {
      const ta = $("#adv-style");
      ta.value = ta.value ? ta.value.replace(/,\s*$/, "") + ", " + s : s;
      refreshCreateBtn();
    });
    $("#style-chips").appendChild(b);
  }
}
$("#style-shuffle").addEventListener("click", () => { styleDeck++; renderStyleChips(); });
$("#style-magic").addEventListener("click", async () => {
  const ta = $("#adv-style");
  if (!llmConfigured()) {
    const next = (styleDeck + 1) % STYLE_SUGGESTIONS.length;
    const apply = () => {
      styleDeck = next;
      ta.value = STYLE_SUGGESTIONS[next].join(", ");
      renderStyleChips();
      refreshCreateBtn();
    };
    if (ta.value.trim()) confirmDialog(t("cp.replaceStyleTitle"), t("cp.replaceStyleMsg"), t("cp.replace"), apply);
    else apply();
    return;
  }
  const text = ta.value.trim();
  if (!text) { toast(t("llm.enhanceEmpty")); return; }
  const btn = $("#style-magic");
  if (btn.disabled) return;
  btn.disabled = true;
  try {
    const res = await api("/api/llm/enhance", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ style: text }) });
    if (res.style === text) { toast(t("llm.enhanceSame")); return; }
    confirmDialog(t("llm.enhanceTitle"), res.style, t("cp.replace"), () => {
      ta.value = res.style;
      ta.dispatchEvent(new Event("input", { bubbles: true }));
      refreshCreateBtn();
    });
  } catch (err) { toast(err.message, true); }
  finally { btn.disabled = false; }
});

const EXAMPLE_LYRICS = [
  "[Verse]\nMoonlight spills across the quiet harbor\nPaper lanterns drifting with the tide\n[Chorus]\nAnd we sail, and we sing\nTill the morning paints the water gold",
  "[Verse]\nCity hums in electric blue\nEvery window tells a story\n[Chorus]\nTurn it up, let it shake the walls\nWe were born for the noise",
];
$("#lyrics-sparkle").addEventListener("click", async () => {
  if (state.examples === null) {
    try { state.examples = await api("/api/examples"); } catch (e) { state.examples = {}; }
  }
  const bank = [...((state.examples && state.examples.lyrics) || []).map((l) => l.lyrics), ...EXAMPLE_LYRICS];
  const pick = bank[Math.floor(Math.random() * bank.length)];
  const ta = $("#adv-lyrics");
  const apply = () => { ta.value = pick; refreshCreateBtn(); };
  if (ta.value.trim()) confirmDialog(t("cp.replaceLyricsTitle"), t("cp.replaceLyricsMsg"), t("cp.replace"), apply);
  else apply();
});
$("#lyrics-expand").addEventListener("click", () => {
  const ta = $("#adv-lyrics");
  ta.style.minHeight = ta.style.minHeight === "420px" ? "" : "420px";
});
$("#lyrics-focus").addEventListener("click", () => $("#adv-lyrics").focus());

["simple-desc", "adv-style", "adv-lyrics"].forEach((id) =>
  $("#" + id).addEventListener("input", refreshCreateBtn));

/* model pill -> cot dropdown */
const COT_LABELS = () => ({ full: "YuE2-3B", melody: "YuE2·Melody", off: "YuE2·Free" });
$("#model-pill").addEventListener("click", (e) => {
  const rect = e.currentTarget.getBoundingClientRect();
  const items = [
    { header: t("model.scoreMode") },
    ...[["full", t("model.full"), t("model.fullSub")],
        ["melody", t("model.melody"), t("model.melodySub")],
        ["off", t("model.off"), t("model.offSub")]].map(([v, label, sub]) => ({
      label, sub, active: state.cot === v,
      run: () => { state.cot = v; refreshModelPill(); },
    })),
  ];
  if (state.loras.length) {
    items.push({ sep: true }, { header: t("cp.lora") });
    items.push({ label: t("model.loraNone"), sub: t("model.loraNoneSub"), active: state.lora === null, run: () => setLora(null) });
    for (const l of state.loras) {
      items.push({ label: l.label, sub: loraSub(l), active: state.lora === l.id, run: () => setLora(l.id) });
    }
  }
  items.push({ sep: true }, { header: t("model.engine") });
  items.push({ label: t("model.engineTorch"), sub: t("model.engineTorchSub"),
               active: state.backend === "torch", run: () => setBackend("torch") });
  const mlxOk = !!state.server.mlx_available;
  const variantLabel = variantText(state.server.mlx_variant || "8bit");
  items.push({ label: t("model.engineMlx", { v: variantLabel }), sub: mlxOk ? t("model.engineMlxSub") : t("model.engineMlxMissing"),
               active: state.backend === "mlx",
               run: () => { if (!mlxOk) { toast(t("model.engineMlxMissing"), true); return; } setBackend("mlx"); } });
  openDrop(rect.left, rect.bottom + 6, items);
});

async function createSong() {
  const simple = state.mode === "simple";
  const style = (simple ? $("#simple-desc") : $("#adv-style")).value.trim();
  const lyrics = simple ? "" : $("#adv-lyrics").value;
  if (!style && !lyrics.trim()) { toast(t("toast.needStyle"), true); return; }
  const instrumental = !simple && $("#adv-instrumental").checked;
  const body = {
    style: style || "song",
    lyrics,
    cot: state.cot,
    instrumental,
    backend: state.backend,
  };
  if (!simple && state.vgender && !instrumental) body.vocal_gender = state.vgender;
  if (!simple) {
    body.title = $("#adv-title").value.trim() || undefined;
    if ($("#adv-seed").value !== "") body.seed = Number($("#adv-seed").value);
    if ($("#adv-cfg").value !== "") body.cfg_scale = Number($("#adv-cfg").value);
    if ($("#adv-planonly").checked) body.plan_only = true;
    for (const [id, key] of [["#sam-temperature", "temperature"], ["#sam-topp", "top_p"], ["#sam-topk", "top_k"],
                             ["#adv-maxsec", "max_seconds"], ["#sam-odesteps", "ode_steps"]]) {
      const v = $(id).value.trim();
      if (v !== "") body[key] = Number(v);
    }
  }
  if (state.attachAbc) {
    body.abc = state.attachAbc.text;
    if (body.cot === "off") body.cot = "full";
  }
  if (state.lora) body.lora = state.lora;
  const btn = $("#create-btn");
  btn.disabled = true;
  try {
    await api("/api/songs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    toast(t("toast.queued"));
    await refreshSongs();
  } catch (e) { toast(e.message, true); }
  finally { refreshCreateBtn(); }
}
$("#create-btn").addEventListener("click", createSong);
$("#clear-form").addEventListener("click", () => {
  ["simple-desc", "adv-style", "adv-lyrics", "adv-title", "adv-seed", "adv-cfg"].forEach((id) => { $("#" + id).value = ""; });
  state.vgender = null;
  $$("#vgender-opts button").forEach((b) => b.classList.remove("active"));
  $("#adv-instrumental").checked = false;
  $("#adv-planonly").checked = false;
  ["sam-temperature", "sam-topp", "sam-topk", "adv-maxsec", "sam-odesteps"].forEach((id) => { $("#" + id).value = ""; });
  applyFormDefaults();
  state.attachAbc = null;
  updateAttachChip();
  refreshCreateBtn();
  toast(t("toast.cleared"));
});

/* ---------------- feed tools ---------------- */

$("#feed-search").addEventListener("input", (e) => { state.feedSearch = e.target.value; renderFeed(); });
$("#lib-search").addEventListener("input", (e) => { state.libSearch = e.target.value; renderLibrary(); });

$$("[data-feedtab]").forEach((btn) =>
  btn.addEventListener("click", () => {
    state.feedTab = btn.dataset.feedtab;
    $$("[data-feedtab]").forEach((b) => b.classList.toggle("active", b === btn));
    renderFeed();
  })
);

$("#filters-pill").addEventListener("click", (e) => {
  const rect = e.currentTarget.getBoundingClientRect();
  openDrop(rect.left, rect.bottom + 6, [
    ["all", t("filter.all")], ["active", t("filter.active")], ["complete", t("filter.complete")], ["failed", t("filter.failed")],
  ].map(([v, label]) => ({
    label, active: state.feedFilter === v,
    run: () => {
      state.feedFilter = v;
      const c = $("#filters-count");
      c.hidden = v === "all";
      c.textContent = v === "all" ? "" : "(1)";
      $("#filters-pill").classList.toggle("white", v !== "all");
      renderFeed();
    },
  })));
});

const SORT_SHORT = { new: "sort.newShort", old: "sort.oldShort", title: "sort.titleShort" };
$("#sort-pill").addEventListener("click", (e) => {
  const rect = e.currentTarget.getBoundingClientRect();
  openDrop(rect.left, rect.bottom + 6, [
    ["new", t("sort.new")], ["old", t("sort.old")], ["title", t("sort.title")],
  ].map(([v, label]) => ({
    label, active: state.sort === v,
    run: () => { state.sort = v; $("#sort-label").textContent = t(SORT_SHORT[v]); renderFeed(); },
  })));
});

$("#view-pill").addEventListener("click", (e) => {
  const rect = e.currentTarget.getBoundingClientRect();
  openDrop(rect.left, rect.bottom + 6, [
    { label: t("view.list"), active: !state.feedGrid, run: () => { state.feedGrid = false; $("#view-label").textContent = t("view.list"); renderFeed(); } },
    { label: t("view.grid"), active: state.feedGrid, run: () => { state.feedGrid = true; $("#view-label").textContent = t("view.grid"); renderFeed(); } },
  ]);
});

$$("#lib-tabs .lib-tab").forEach((btn) =>
  btn.addEventListener("click", () => {
    state.libTab = btn.dataset.lib;
    $$("#lib-tabs .lib-tab").forEach((b) => b.classList.toggle("active", b === btn));
    renderLibrary();
  })
);

/* ---------------- player ---------------- */

function currentSong() { return state.playlist[state.playIndex] || null; }

function playSong(id) {
  state.playlist = state.songs.filter(isPlayable);
  const idx = state.playlist.findIndex((s) => s.id === id);
  if (idx < 0) return;
  state.playIndex = idx;
  const song = state.playlist[idx];
  state.played.add(song.id);
  saveSets();
  audio.src = `/api/songs/${song.id}/audio`;
  audio.play();
  state.playing = true;
  renderPlayer();
  renderAll();
}

function togglePlay() {
  if (!currentSong()) return;
  if (audio.paused) { audio.play(); state.playing = true; }
  else { audio.pause(); state.playing = false; }
  renderPlayer();
  renderAll();
}

function step(d) {
  if (!state.playlist.length) return;
  let next = state.playIndex;
  if (state.shuffle) {
    for (let i = 0; i < 8 && next === state.playIndex; i++)
      next = Math.floor(Math.random() * state.playlist.length);
  } else {
    next = (state.playIndex + d + state.playlist.length) % state.playlist.length;
  }
  playSong(state.playlist[next].id);
}

function renderPlayer() {
  const song = currentSong();
  const bar = $("#player");
  bar.hidden = false;
  if (!song) {
    $(".pl-left").style.visibility = "hidden";
    $("#btn-play").innerHTML = `<i class="ph-fill ph-play"></i>`;
    $("#time-cur").textContent = "0:00";
    $("#time-total").textContent = "0:00";
    return;
  }
  $(".pl-left").style.visibility = "visible";
  $("#player-cover").style.cssText = coverStyle(song.id);
  $("#player-title").textContent = song.title;
  $("#player-artist").textContent = song.kind === "upload" ? t("row.upload") : "YuE2 Studio";
  $("#btn-play").innerHTML = `<i class="ph-fill ${state.playing ? "ph-pause" : "ph-play"}"></i>`;
  $("#time-total").textContent = fmtTime(song.audio_seconds);
  $("#pl-like").classList.toggle("on", state.liked.has(song.id));
}

audio.addEventListener("timeupdate", () => {
  if (audio.duration) {
    const pct = (audio.currentTime / audio.duration) * 100;
    $("#player-progress-fill").style.width = pct + "%";
    $("#player-dot").style.left = pct + "%";
    $("#time-cur").textContent = fmtTime(audio.currentTime);
    $("#time-total").textContent = fmtTime(audio.duration);
  }
});
audio.addEventListener("ended", () => { if (state.repeat) { audio.currentTime = 0; audio.play(); } else step(1); });
audio.addEventListener("pause", () => { state.playing = false; renderPlayer(); renderAll(); });
audio.addEventListener("play", () => { state.playing = true; renderPlayer(); renderAll(); });

$("#player-progress").addEventListener("click", (e) => {
  if (!audio.duration) return;
  const rect = e.currentTarget.getBoundingClientRect();
  audio.currentTime = ((e.clientX - rect.left) / rect.width) * audio.duration;
});
$("#btn-play").addEventListener("click", togglePlay);
$("#btn-prev").addEventListener("click", () => step(-1));
$("#btn-next").addEventListener("click", () => step(1));
$("#btn-shuffle").addEventListener("click", (e) => { state.shuffle = !state.shuffle; e.currentTarget.classList.toggle("on", state.shuffle); });
$("#btn-repeat").addEventListener("click", (e) => { state.repeat = !state.repeat; e.currentTarget.classList.toggle("on", state.repeat); });
$("#volume").addEventListener("input", (e) => { audio.volume = Number(e.target.value); });
$("#pl-queue").addEventListener("click", () => toast(t("toast.queueCount", { n: state.playlist.length })));
$("#pl-like").addEventListener("click", () => { const s = currentSong(); if (s) toggleLike(s.id); });
$("#pl-share").addEventListener("click", () => { const s = currentSong(); if (s) window.location = `/api/songs/${s.id}/audio`; });
audio.volume = 0.9;

function toggleLike(id) {
  if (state.liked.has(id)) state.liked.delete(id); else state.liked.add(id);
  saveSets();
  renderAll();
  renderPlayer();
}

/* ---------------- dropdown & context menu ---------------- */

function openDrop(x, y, items) {
  const menu = $("#drop-menu");
  menu.innerHTML = items.map((it, i) => {
    if (it.sep) return `<div class="ctx-sep"></div>`;
    if (it.header) return `<div class="ctx-head">${esc(it.header)}</div>`;
    return `<button class="ctx-item" data-i="${i}">${it.active ? '<i class="ph ph-check"></i>' : "<i></i>"}<span>${esc(it.label)}${it.sub ? `<div style="font-size:12px;color:var(--text-3);font-weight:400">${esc(it.sub)}</div>` : ""}</span></button>`;
  }).join("");
  menu.hidden = false;
  const rect = menu.getBoundingClientRect();
  menu.style.left = Math.min(x, innerWidth - rect.width - 8) + "px";
  menu.style.top = Math.min(y, innerHeight - rect.height - 8) + "px";
  menu.onclick = (e) => {
    const b = e.target.closest("[data-i]");
    if (!b) return;
    menu.hidden = true;
    items[Number(b.dataset.i)].run();
  };
}

function openMenu(x, y, song) {
  const menu = $("#ctx-menu");
  const items = [];
  if (isPlayable(song)) items.push(["play", "ph-play", t("menu.play")]);
  if ((isPlayable(song) || song.plan_only) && song.has_score) items.push(["cover", "ph-arrows-clockwise", t("menu.remix")]);
  if (song.kind === "song" && isPlayable(song)) items.push(["edit", "ph-pencil-simple", t("menu.edit")]);
  if (isPlayable(song)) items.push(["like", "ph-thumbs-up", state.liked.has(song.id) ? t("menu.unlike") : t("menu.like")]);
  if (isPlayable(song)) items.push(["download", "ph-download", t("menu.download")]);
  if (song.kind === "song" && (isPlayable(song) || (song.status === "complete" && song.has_score))) {
    items.push(["variant", "ph-copy", t("menu.variant")]);
  }
  if (song.kind === "song" && isPlayable(song)) items.push(["allmodes", "ph-stack", t("menu.allmodes")]);
  items.push(["detail", "ph-info", t("menu.details")]);
  if (isActive(song)) items.push(["cancel", "ph-stop", t("menu.cancel")]);
  items.push(["sep"]);
  items.push(["delete", "ph-trash", t("menu.trash"), true]);
  menu.innerHTML = items.map((it) => it[0] === "sep"
    ? `<div class="ctx-sep"></div>`
    : `<button class="ctx-item ${it[3] ? "danger" : ""}" data-ctx="${it[0]}"><i class="ph ${it[1]}"></i>${it[2]}</button>`).join("");
  menu.hidden = false;
  const rect = menu.getBoundingClientRect();
  menu.style.left = Math.min(x, innerWidth - rect.width - 8) + "px";
  menu.style.top = Math.min(y, innerHeight - rect.height - 8) + "px";
  menu.dataset.id = song.id;
}

document.addEventListener("click", (e) => {
  if (!e.target.closest("#ctx-menu")) $("#ctx-menu").hidden = true;
  if (!e.target.closest("#drop-menu") && !e.target.closest("[data-drop-opener]") && !e.target.closest("#model-pill") && !e.target.closest("#lora-pick") && !e.target.closest(".feed-pill")) $("#drop-menu").hidden = true;
});

$("#ctx-menu").addEventListener("click", (e) => {
  const item = e.target.closest("[data-ctx]");
  if (!item) return;
  const id = $("#ctx-menu").dataset.id;
  $("#ctx-menu").hidden = true;
  runAction(item.dataset.ctx, id);
});

function runAction(action, id) {
  const song = state.songs.find((s) => s.id === id);
  if (!song) return;
  if (action === "play") playSong(id);
  else if (action === "detail") openDetail(id);
  else if (action === "cover") openCover(id);
  else if (action === "edit") openEdit(id);
  else if (action === "like") toggleLike(id);
  else if (action === "download") window.location = `/api/songs/${id}/audio`;
  else if (action === "variant") loadVariant(id);
  else if (action === "allmodes") queueAllModes(id);
  else if (action === "delete") deleteSong(id);
  else if (action === "cancel")
    api(`/api/songs/${id}/cancel`, { method: "POST" }).then(refreshSongs).catch((e) => toast(e.message, true));
}

async function deleteSong(id) {
  try {
    await api(`/api/songs/${id}`, { method: "DELETE" });
    if (state.detailId === id) closeDetail();
    if (currentSong()?.id === id) { audio.pause(); state.playIndex = -1; renderPlayer(); }
    await refreshSongs();
    toast(t("toast.trashed"));
  } catch (e) { toast(e.message, true); }
}

/* ---------------- list clicks ---------------- */

function handleListClick(e) {
  const row = e.target.closest("[data-id]");
  if (!row) return;
  const id = row.dataset.id;
  const song = state.songs.find((s) => s.id === id);
  if (!song) return;
  const actionEl = e.target.closest("[data-action]");
  const action = actionEl?.dataset.action || "detail";
  if (action === "play") {
    if (isPlayable(song)) {
      if (state.playlist[state.playIndex]?.id === id) togglePlay(); else playSong(id);
    }
  }
  else if (action === "like") toggleLike(id);
  else if (action === "dislike") { state.played.add(id); saveSets(); toast(t("toast.disliked")); }
  else if (action === "menu") {
    const rect = actionEl.getBoundingClientRect();
    openMenu(rect.left - 190, rect.bottom + 4, song);
    e.stopPropagation();
  }
  else runAction(action, id);
}

$("#feed-list").addEventListener("click", handleListClick);
$("#lib-list").addEventListener("click", handleListClick);

/* detail view clicks */
$("#detail-content").addEventListener("click", async (e) => {
  const tab = e.target.closest("[data-tab]");
  if (tab) {
    $$("#detail-content .dtab").forEach((t) => t.classList.toggle("active", t === tab));
    $$("#detail-content [data-pane]").forEach((p) => { p.hidden = p.dataset.pane !== tab.dataset.tab; });
    return;
  }
  const el = e.target.closest("[data-d]");
  if (!el) return;
  const id = state.detailId;
  const action = el.dataset.d;
  try {
    if (action === "play") playSong(id);
    else if (action === "cover") openCover(id);
    else if (action === "redecode") {
      e.stopPropagation();
      const rect = el.getBoundingClientRect();
      openDrop(rect.left - 220, rect.bottom + 6, [
        { label: t("detail.redecodeDefault"), run: () => doRedecode(id, "default") },
        { label: t("detail.redecodeLegacy"), run: () => doRedecode(id, "legacy") },
      ]);
    }
    else if (action === "check-score") {
      const res = await api(`/api/songs/${id}/score-check`);
      const box = $("#score-report");
      if (!box) return;
      if (res.ok) {
        const r = res.report || {};
        const voices = Object.values(r.voices || {});
        const measures = voices.reduce((m, v) => Math.max(m, v.measures || 0), 0);
        const notes = voices.reduce((m, v) => Math.max(m, v.sounding_notes || 0), 0);
        box.className = "score-report ok";
        box.textContent = `✓ ${t("detail.checkOk")} · ${r.bpm ?? "?"} BPM · ${measures} ${t("detail.measures")} · ${notes} ${t("detail.notes")} · ~${Math.round(r.nominal_duration_seconds || 0)}s`;
      } else {
        box.className = "score-report err";
        box.textContent = `✗ ${t("detail.checkFail", { err: res.error || "" })}`;
      }
      box.hidden = false;
    }
    else if (action === "edit") {
      const editor = $("#score-editor");
      if (editor) await api(`/api/songs/${id}/score`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ abc: editor.value }) });
      openEdit(id);
    }
    else if (action === "save-score") {
      const res = await api(`/api/songs/${id}/score`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ abc: $("#score-editor").value }) });
      const box = $("#score-report");
      if (box) {
        if (res.error) { box.className = "score-report err"; box.textContent = `✗ ${t("detail.saveBroken", { err: res.error })}`; }
        else if (res.diff && res.diff.match === false) { box.className = "score-report err"; box.textContent = `${t("detail.saveDiffChanged", { detail: (res.diff.differences || []).join("; ") })}`; }
        else { box.className = "score-report ok"; box.textContent = `✓ ${t("detail.saveDiffOk")}`; }
        box.hidden = false;
      }
      toast(t("toast.scoreSaved"));
    }
    else if (action === "copy-style") {
      const text = $("#detail-content .dsc-text")?.textContent ?? "";
      try { await navigator.clipboard.writeText(text); toast(t("toast.copied")); }
      catch { toast(t("toast.copyFailed"), true); }
    }
    else if (action === "rebuild") {
      await api(`/api/songs/${id}/rebuild`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
      toast(t("toast.rebuildQueued"));
      await refreshSongs();
    }
    else if (action === "like") toggleLike(id);
    else if (action === "download") window.location = `/api/songs/${id}/audio`;
    else if (action === "cancel") { await api(`/api/songs/${id}/cancel`, { method: "POST" }); await refreshSongs(); }
    else if (action === "delete") deleteSong(id);
  } catch (err) { toast(err.message, true); }
});

/* ---------------- modals ---------------- */

function openModal(html, narrow = true) {
  const m = $("#modal");
  m.classList.toggle("narrow", narrow);
  m.innerHTML = html;
  $("#overlay").hidden = false;
}
let doctorTimer = null;
function closeModal() {
  $("#overlay").hidden = true;
  $("#modal").innerHTML = "";
  if (doctorTimer) { clearInterval(doctorTimer); doctorTimer = null; }
}
$("#overlay").addEventListener("click", (e) => { if (e.target === $("#overlay")) closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { closeModal(); $("#ctx-menu").hidden = true; $("#drop-menu").hidden = true; } });

function modalShell(title, body) {
  return `<div class="modal-head"><div class="modal-title">${esc(title)}</div>
    <button class="modal-close" data-m="close"><i class="ph ph-x"></i></button></div>
    <div class="modal-body">${body}</div>`;
}

/* ---------------- model rows shared by the remix / edit modals ---------------- */

const coverSel = { backend: "torch", lora: null };
const editSel = { backend: "torch", lora: null };

function selFromSource(sel, d) {
  sel.backend = d.backend || "torch";
  sel.lora = d.lora || null;
}

function modelRowsHtml(prefix, sel) {
  const mlxOk = !!state.server.mlx_available;
  const loraName = sel.lora
    ? (state.loras.find((l) => l.id === sel.lora)?.label || sel.lora)
    : t("cp.loraNone");
  return `
    <div class="modal-rows">
      <div class="cp-vgender">
        <span class="cp-vgender-label">${t("cp.lora")}</span>
        <button type="button" class="cp-lorapill" id="${prefix}-lora"><span id="${prefix}-lora-label">${esc(loraName)}</span><i class="ph ph-caret-down"></i></button>
      </div>
      <div class="cp-vgender">
        <span class="cp-vgender-label">${t("model.engine")}</span>
        <span class="set-seg" id="${prefix}-engine">
          <button type="button" data-engine="torch" class="${sel.backend === "torch" ? "active" : ""}">PyTorch</button>
          <button type="button" data-engine="mlx" class="${sel.backend === "mlx" ? "active" : ""}" ${mlxOk ? "" : "disabled"} title="${mlxOk ? "" : t("model.engineMlxMissing")}">MLX</button>
        </span>
      </div>
    </div>`;
}

function bindModelRows(prefix, sel) {
  const loraBtn = $("#" + prefix + "-lora");
  if (loraBtn) loraBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const rect = e.currentTarget.getBoundingClientRect();
    const choose = (id) => {
      if (sel.backend === "mlx" && id !== null) { toast(t("model.mlxNoLora"), true); return; }
      sel.lora = id;
      $("#" + prefix + "-lora-label").textContent = id
        ? (state.loras.find((l) => l.id === id)?.label || id) : t("cp.loraNone");
    };
    openDrop(rect.right - 220, rect.bottom + 6, [
      { label: t("cp.loraNone"), active: sel.lora === null, run: () => choose(null) },
      ...state.loras.map((l) => ({ label: l.label, sub: loraSub(l), active: sel.lora === l.id, run: () => choose(l.id) })),
    ]);
  });
  const seg = $("#" + prefix + "-engine");
  if (seg) seg.addEventListener("click", (e) => {
    const b = e.target.closest("[data-engine]");
    if (!b || b.disabled) return;
    sel.backend = b.dataset.engine;
    seg.querySelectorAll("[data-engine]").forEach((x) => x.classList.toggle("active", x === b));
    if (sel.backend === "mlx" && sel.lora !== null) {
      sel.lora = null;
      $("#" + prefix + "-lora-label").textContent = t("cp.loraNone");
      toast(t("model.mlxNoLora"));
    }
  });
}

async function openCover(id) {
  let d;
  try { d = await api(`/api/songs/${id}`); }
  catch (e) { toast(e.message, true); return; }
  selFromSource(coverSel, d);
  const lyrics = d.lyrics || "";
  openModal(modalShell(t("cover.title"), `
    <div class="modal-from">${t("cover.from", { title: esc(d.title) })}</div>
    <div class="input-shell"><label class="input-label">${t("cover.newStyle")}</label>
      <textarea id="cover-style" rows="3" placeholder="${esc(t("cover.stylePh"))}">${esc(d.kind === "song" ? dispStyle(d) : "")}</textarea></div>
    <div class="input-shell"><label class="input-label">${t("cover.lyrics")}</label>
      <textarea id="cover-lyrics" rows="5" placeholder="${esc(t("cover.lyricsPh"))}">${esc(lyrics)}</textarea></div>
    <div class="radio-cards" id="cover-mode">
      <button class="radio-card active" data-value="melody"><div class="rc-title">${t("cover.melodyOnly")}</div>
        <div class="rc-sub">${t("cover.melodyOnlySub")}</div></button>
      <button class="radio-card" data-value="full"><div class="rc-title">${t("cover.full")}</div>
        <div class="rc-sub">${t("cover.fullSub")}</div></button>
    </div>
    ${modelRowsHtml("cover", coverSel)}
    <label class="cp-instr"><span>${t("cp.instrumental")}</span><span class="switch"><input type="checkbox" id="cover-instrumental" ${lyrics ? "" : "checked"} /><span class="switch-ui"></span></span></label>
    <button class="create-btn" data-m="do-cover" data-id="${id}"><i class="ph-fill ph-arrows-clockwise"></i>${t("cover.create")}</button>
  `));
  bindModelRows("cover", coverSel);
}

async function openEdit(id) {
  let d;
  try { d = await api(`/api/songs/${id}`); }
  catch (e) { toast(e.message, true); return; }
  selFromSource(editSel, d);
  const score = d.edited_abc ?? d.abc;
  openModal(modalShell(t("edit.title"), `
    <div class="modal-from">${t("edit.desc")}</div>
    <div class="input-shell"><label class="input-label">${t("edit.fieldTitle")}</label>
      <input type="text" id="edit-title" value="${esc(d.title)}" /></div>
    <div class="input-shell"><label class="input-label">${t("edit.style")}</label>
      <textarea id="edit-style" rows="3">${esc(dispStyle(d))}</textarea></div>
    <div class="input-shell"><label class="input-label">${t("edit.lyrics")}</label>
      <textarea id="edit-lyrics" rows="6">${esc(d.lyrics)}</textarea></div>
    ${score != null ? `<div class="input-shell"><label class="input-label">${t("edit.score")}</label>
      <textarea class="score-editor" id="edit-abc" spellcheck="false">${esc(score)}</textarea></div>` : ""}
    ${modelRowsHtml("edit", editSel)}
    <button class="create-btn" data-m="do-edit" data-id="${id}"><i class="ph-fill ph-arrows-clockwise"></i>${t("edit.render")}</button>
  `));
  bindModelRows("edit", editSel);
}

/* ---------------- model manager ---------------- */

const MODEL_GROUPS = [
  ["core", "models.groupCore"],
  ["decoders", "models.groupDecoders"],
  ["extras", "models.groupExtras"],
  ["lora", "models.groupLora"],
  ["transcribe", "models.groupTranscribe"],
  ["mlx", "models.groupMlx"],
];

let modelsTimer = null;
let modelsData = null;
let modelsSig = null;

function stopModelsPolling() {
  if (modelsTimer) { clearInterval(modelsTimer); modelsTimer = null; }
}

async function openModels() {
  await refreshLoras();
  await refreshModels();
  stopModelsPolling();
  modelsTimer = setInterval(() => {
    if (state.view !== "models") { stopModelsPolling(); return; }
    refreshModels();
  }, 1500);
}

async function refreshModels() {
  try {
    const fresh = await api("/api/models");
    if (modelsData) {
      for (const c of fresh.components) {
        const prev = modelsData.components.find((x) => x.id === c.id);
        if (prev && prev.downloading && c.installed) toast(t("models.downloadDone", { name: c.label }));
      }
    }
    modelsData = fresh;
    renderModelsPage();
  } catch (e) { /* server restarting */ }
}

function fmtSize(bytes) {
  if (bytes >= 2 ** 30) return (bytes / 2 ** 30).toFixed(2) + " GB";
  return (bytes / 2 ** 20).toFixed(0) + " MB";
}

function modelRowHtml(c) {
  const pct = c.bytes ? Math.min(100, Math.round((c.downloaded_bytes / c.bytes) * 100)) : 0;
  const status = c.installed
    ? `<span class="mdl-badge ok">${t("models.installed")}</span>`
    : c.downloading
      ? `<span class="mdl-badge busy">${pct}%</span>`
      : `<span class="mdl-badge">${t("models.notInstalled")}</span>`;
  const action = c.downloading
    ? `<button class="ghost-btn" data-mdl-cancel="${c.id}">${t("models.cancel")}</button>`
    : c.installed ? ""
      : `<button class="ghost-btn primary" data-mdl-download="${c.id}">${t("models.download")}</button>`;
  return `<div class="mdl-row">
    <div class="mdl-info">
      <div class="mdl-name">${esc(c.label)}${c.required ? ` <span class="mdl-req">${t("models.required")}</span>` : ""}</div>
      <div class="mdl-sub">${fmtSize(c.bytes)}${c.error ? ` · <span class="mdl-err">${esc(c.error)}</span>` : ""}</div>
      ${c.downloading ? `<div class="mdl-bar"><div style="width:${pct}%"></div></div>` : ""}
    </div>
    <div class="mdl-side">${status}${action}</div>
  </div>`;
}

function renderModelsPage() {
  const view = $("#view-models");
  const s = state.server || {};
  const source = s.download_source || "mirror";
  const d = modelsData || { components: [] };
  const variants = s.mlx_variants || [];
  const loras = state.loras || [];
  const sig = JSON.stringify([d, source, s.default_backend, s.mlx_variant, s.default_lora,
                              loras.map((l) => l.id), !!s.mlx_available]);
  if (sig === modelsSig && view.querySelector(".mdl-scroll")) return;  // nothing changed
  modelsSig = sig;
  const keepScroll = view.querySelector(".mdl-scroll")?.scrollTop || 0;
  view.innerHTML = `
    <div class="lib-head"><div class="lib-title">${t("models.title")}</div></div>
    <div class="mdl-scroll">
      <div class="mdl-card">
        <div class="set-row">
          <span class="set-label">${t("models.source")}</span>
          <span class="set-seg" id="mdl-source-seg">
            <button type="button" data-source="mirror" class="${source === "mirror" ? "active" : ""}">${t("models.sourceMirror")}</button>
            <button type="button" data-source="huggingface" class="${source === "huggingface" ? "active" : ""}">${t("models.sourceHf")}</button>
          </span>
        </div>
        <p class="set-note">${t("models.sourceNote")}</p>
        <div class="set-row">
          <span class="set-label">${t("models.defaultEngine")}</span>
          <span class="set-seg" id="mdl-engine-seg">
            <button type="button" data-engine="torch" class="${(s.default_backend || "torch") !== "mlx" ? "active" : ""}">PyTorch</button>
            <button type="button" data-engine="mlx" class="${s.default_backend === "mlx" ? "active" : ""}" ${s.mlx_available ? "" : "disabled"}>MLX</button>
          </span>
        </div>
        ${variants.length ? `
        <div class="set-row">
          <span class="set-label">${t("models.defaultVariant")}</span>
          <span class="set-seg" id="mdl-variant-seg">
            ${variants.map((v) => `<button type="button" data-variant="${v}" class="${s.mlx_variant === v ? "active" : ""}">${variantText(v)}</button>`).join("")}
          </span>
        </div>` : ""}
        <div class="set-row">
          <span class="set-label">${t("models.defaultLora")}</span>
          <span class="set-seg" id="mdl-lora-seg">
            <button type="button" data-lora="" class="${!s.default_lora ? "active" : ""}">${t("cp.loraNone")}</button>
            ${loras.map((l) => `<button type="button" data-lora="${esc(l.id)}" class="${s.default_lora === l.id ? "active" : ""}">${esc(l.label)}</button>`).join("")}
          </span>
        </div>
      </div>
      ${MODEL_GROUPS.map(([g, key]) => {
        const items = d.components.filter((c) => c.group === g);
        if (!items.length) return "";
        return `<div class="mdl-group">${t(key)}</div>${items.map(modelRowHtml).join("")}`;
      }).join("")}
    </div>`;
  if (keepScroll) view.querySelector(".mdl-scroll").scrollTop = keepScroll;
  $("#mdl-source-seg")?.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-source]");
    if (!b) return;
    try {
      state.server = await saveSetting({ download_source: b.dataset.source }, { refresh: false });
      renderModelsPage();
    } catch (err) { toast(err.message, true); }
  });
  $("#mdl-engine-seg")?.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-engine]");
    if (!b || b.disabled) return;
    try {
      state.server = await saveSetting({ default_backend: b.dataset.engine }, { refresh: false });
      setBackend(b.dataset.engine);
      renderModelsPage();
    } catch (err) { toast(err.message, true); }
  });
  $("#mdl-variant-seg")?.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-variant]");
    if (!b) return;
    try {
      state.server = await saveSetting({ mlx_variant: b.dataset.variant }, { refresh: false });
      renderModelsPage();
    } catch (err) { toast(err.message, true); }
  });
  $("#mdl-lora-seg")?.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-lora]");
    if (!b) return;
    try {
      state.server = await saveSetting({ default_lora: b.dataset.lora || null }, { refresh: false });
      renderModelsPage();
    } catch (err) { toast(err.message, true); }
  });
  view.querySelectorAll("[data-mdl-download]").forEach((btn) => btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      modelsData = await api("/api/models/download", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ component: btn.dataset.mdlDownload }) });
      renderModelsPage();
    } catch (err) { toast(err.message, true); btn.disabled = false; }
  }));
  view.querySelectorAll("[data-mdl-cancel]").forEach((btn) => btn.addEventListener("click", async () => {
    try {
      modelsData = await api("/api/models/cancel", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ component: btn.dataset.mdlCancel }) });
      renderModelsPage();
    } catch (err) { toast(err.message, true); }
  }));
}

/* ---------------- LLM config & playground ---------------- */

let llmData = { items: [], active: null };
let llmPresets = [];
const chatData = { conversations: [], activeId: null, messages: [], streaming: false, abort: null };

function llmConfigured() {
  const s = state.server || {};
  return !!s.llm_active;
}

function llmProviderById(id) {
  return llmData.items.find((p) => p.id === id) || null;
}

function presetName(id) {
  const preset = llmPresets.find((p) => p.id === id);
  return preset ? preset.name : (id || "");
}

async function refreshLlmData() {
  try {
    const [presets, providers] = await Promise.all([api("/api/llm/presets"), api("/api/llm/providers")]);
    llmPresets = presets.items || [];
    llmData = { items: providers.items || [], active: providers.active || null };
  } catch (e) { /* server restarting */ }
}

async function openLlm() {
  await refreshLlmData();
  await refreshChats();
  renderLlmPage();
}

function providerRowHtml(p) {
  const active = llmData.active === p.id;
  const sub = [presetName(p.preset), p.default_model || t("llm.modelPh"),
               p.api_key_masked || "—"].map(esc).join(" · ");
  return `<div class="mdl-row">
    <div class="mdl-info">
      <div class="mdl-name">${esc(p.name || t("llm.unnamed"))}${p.id === "legacy" ? ` <span class="mdl-req">${t("llm.legacyBadge")}</span>` : ""}</div>
      <div class="mdl-sub">${sub}</div>
    </div>
    <div class="mdl-side">
      ${active ? `<span class="mdl-badge ok">${t("llm.active")}</span>` : ""}
      <button class="ghost-btn" data-llm-toggle="${esc(p.id)}">${p.enabled ? t("settings.on") : t("settings.off")}</button>
      <button class="ghost-btn" data-llm-test="${esc(p.id)}">${t("llm.test")}</button>
      <button class="ghost-btn" data-llm-edit="${esc(p.id)}">${t("menu.edit")}</button>
      <button class="ghost-btn" data-llm-del="${esc(p.id)}">${t("llm.delete")}</button>
    </div>
  </div>`;
}

function renderLlmPage() {
  const view = $("#view-llm");
  if (!view) return;
  const s = state.server || {};
  const output = s.llm_enhance_output || "zh";
  const active = llmProviderById(llmData.active);
  const activeLabel = active ? `${active.name || active.default_model}` : t("llm.activeNone");
  view.innerHTML = `
    <div class="lib-head"><div class="lib-title">${t("llm.title")}</div></div>
    <div class="mdl-scroll">
      <div class="mdl-card">
        <div class="set-row">
          <span class="set-label">${t("llm.active")}</span>
          <button class="ghost-btn" id="llm-active-pick" data-drop-opener>${esc(activeLabel)} <i class="ph ph-caret-down"></i></button>
        </div>
        <div class="set-row">
          <span class="set-label">${t("llm.output")}</span>
          <span class="set-seg" id="llm-output-seg">
            <button type="button" data-out="zh" class="${output === "zh" ? "active" : ""}">${t("llm.outputZh")}</button>
            <button type="button" data-out="en" class="${output === "en" ? "active" : ""}">${t("llm.outputEn")}</button>
          </span>
        </div>
        <div class="set-row">
          <span class="set-label">${t("llm.timeout")}</span>
          <input type="number" class="set-input" id="llm-timeout" min="1" max="60" step="1" value="${esc(String(s.llm_timeout ?? 10))}" />
        </div>
        <p class="set-note">${t("llm.note")}</p>
      </div>
      <div class="mdl-card">
        <div class="set-row">
          <span class="set-label">${t("llm.providers")}</span>
          <button class="ghost-btn primary" id="llm-new">${t("llm.newProvider")}</button>
        </div>
        ${llmData.items.map(providerRowHtml).join("")}
      </div>
      <div class="mdl-card" style="padding:12px">
        <div class="set-row" style="padding-bottom:10px">
          <span class="set-label">${t("chat.title")}</span>
        </div>
        <div class="llm-chat" id="llm-chat"></div>
      </div>
    </div>`;
  bindLlmPage();
  renderChatPanel();
}

function bindLlmPage() {
  $("#llm-output-seg")?.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-out]");
    if (!b) return;
    $$("#llm-output-seg button").forEach((x) => x.classList.toggle("active", x === b));
    try { state.server = await saveSetting({ llm_enhance_output: b.dataset.out }, { refresh: false }); }
    catch (err) { toast(err.message, true); }
  });
  $("#llm-timeout")?.addEventListener("change", async (e) => {
    const value = Number(e.target.value || 10);
    try { state.server = await saveSetting({ llm_timeout: value }, { refresh: false }); }
    catch (err) { toast(err.message, true); }
  });
  $("#llm-active-pick")?.addEventListener("click", (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const items = [{ label: t("llm.activeNone"), active: !llmData.active,
                     run: () => setActiveProvider(null) }];
    for (const p of llmData.items) {
      if (!p.enabled) continue;
      items.push({ label: p.name || p.default_model, sub: p.default_model || undefined,
                   active: llmData.active === p.id, run: () => setActiveProvider(p.id) });
    }
    openDrop(rect.left, rect.bottom + 6, items);
  });
  $("#llm-new")?.addEventListener("click", () => openProviderForm(null));
  $("#view-llm").querySelectorAll("[data-llm-toggle]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const p = llmProviderById(btn.dataset.llmToggle);
      if (!p) return;
      try {
        llmData = await api(`/api/llm/providers/${p.id}`, { method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: !p.enabled }) });
        renderLlmPage();
      } catch (err) { toast(err.message, true); }
    }));
  $("#view-llm").querySelectorAll("[data-llm-test]").forEach((btn) =>
    btn.addEventListener("click", async (e) => {
      const id = btn.dataset.llmTest;
      if (btn.disabled) return;
      btn.disabled = true;
      try {
        const res = await api("/api/llm/test", { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider_id: id }) });
        if (res.ok) toast(t("llm.testOk", { ms: res.latency_ms }));
        else toast(t("llm.testFail", { msg: res.error || "" }), true);
      } catch (err) { toast(err.message, true); }
      finally { btn.disabled = false; }
    }));
  $("#view-llm").querySelectorAll("[data-llm-edit]").forEach((btn) =>
    btn.addEventListener("click", () => openProviderForm(llmProviderById(btn.dataset.llmEdit))));
  $("#view-llm").querySelectorAll("[data-llm-del]").forEach((btn) =>
    btn.addEventListener("click", () => deleteProvider(btn.dataset.llmDel)));
}

async function setActiveProvider(id) {
  try {
    llmData = await api("/api/llm/active", { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider_id: id }) });
    renderLlmPage();
  } catch (err) { toast(err.message, true); }
}

function deleteProvider(id) {
  const p = llmProviderById(id);
  if (!p) return;
  confirmDialog(t("llm.deleteTitle"), t("llm.deleteMsg", { name: p.name || p.default_model }),
    t("llm.delete"), async () => {
      try {
        llmData = await api(`/api/llm/providers/${id}`, { method: "DELETE" });
        renderLlmPage();
        toast(t("llm.deleted"));
      } catch (err) { toast(err.message, true); }
    });
}

function openProviderForm(provider) {
  const editing = !!provider;
  const form = {
    name: provider ? provider.name : "",
    preset: provider ? provider.preset || "custom" : "custom",
    base_url: provider ? provider.base_url : "",
    default_model: provider ? provider.default_model : "",
    enabled: provider ? provider.enabled : true,
  };
  const masked = provider ? provider.api_key_masked : "";
  const legacyNote = provider && provider.id === "legacy"
    ? `<p class="set-note llm-form-note">${t("llm.legacyNote")}</p>` : "";
  openModal(modalShell(editing ? t("llm.editTitle") : t("llm.newProvider"), `
    <div class="llm-form">
      <div class="llm-form-field">
        <span class="llm-form-label">${t("llm.preset")}</span>
        <div class="llm-form-control">
          <button class="ghost-btn llm-form-select" id="lpf-preset" data-drop-opener>
            <span id="lpf-preset-label">${esc(presetName(form.preset))}</span><i class="ph ph-caret-down"></i>
          </button>
        </div>
      </div>
      <div class="llm-form-field">
        <span class="llm-form-label">${t("llm.name")}</span>
        <div class="llm-form-control">
          <input class="set-input llm-form-input" id="lpf-name" placeholder="${t("llm.namePh")}" value="${esc(form.name)}" />
        </div>
      </div>
      <div class="llm-form-field">
        <span class="llm-form-label">${t("llm.baseUrl")}</span>
        <div class="llm-form-control">
          <input class="set-input llm-form-input" id="lpf-url" placeholder="${t("llm.baseUrlPh")}" value="${esc(form.base_url)}" />
        </div>
      </div>
      <div class="llm-form-field">
        <span class="llm-form-label">${t("llm.apiKey")}</span>
        <div class="llm-form-control">
          <input class="set-input llm-form-input" type="password" id="lpf-key"
                 placeholder="${masked ? esc(masked) : t("llm.apiKeyPh")}" />
          ${editing ? `<button class="ghost-btn" id="lpf-clear-key">${t("llm.clearKey")}</button>` : ""}
        </div>
      </div>
      <p class="set-note llm-form-note">${t("llm.apiKeyHint")}</p>
      <div class="llm-form-field">
        <span class="llm-form-label">${t("llm.modelLabel")}</span>
        <div class="llm-form-control">
          <input class="set-input llm-form-input" id="lpf-model" placeholder="${t("llm.modelPh")}" value="${esc(form.default_model)}" />
          <button class="ghost-btn" id="lpf-fetch">${t("llm.fetchModels")}</button>
        </div>
      </div>
      <div class="llm-form-field" id="lpf-models-field" hidden>
        <span class="llm-form-label">${t("llm.fetchedModels")}</span>
        <div class="llm-form-control">
          <button class="ghost-btn llm-form-select" id="lpf-models-pick" data-drop-opener>
            <span id="lpf-models-label">${t("chat.chooseModel")}</span><i class="ph ph-caret-down"></i>
          </button>
        </div>
      </div>
      <p class="set-note llm-form-note" id="lpf-fetch-note" hidden></p>
      <div class="llm-form-field llm-form-field-last">
        <span class="llm-form-label">${t("llm.enabled")}</span>
        <div class="llm-form-control">
          <label class="switch"><input type="checkbox" id="lpf-enabled" ${form.enabled ? "checked" : ""} /><span class="switch-ui"></span></label>
        </div>
      </div>
      ${legacyNote}
      <div class="llm-form-footer">
        <button class="ghost-btn" id="lpf-cancel">${t("common.cancel")}</button>
        <button class="ghost-btn primary" id="lpf-save">${t("llm.save")}</button>
      </div>
    </div>`));
  let fetchedModels = [];
  $("#lpf-preset")?.addEventListener("click", (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    openDrop(rect.left, rect.bottom + 6, llmPresets.map((p) => ({
      label: p.name, active: form.preset === p.id,
      run: () => {
        const currentName = $("#lpf-name").value.trim();
        const presetNames = llmPresets.map((x) => x.name);
        // 自动名（空或仍是某个预设名）跟随切换，手改过的名称保持
        form.name = (!currentName || presetNames.includes(currentName)) ? p.name : currentName;
        form.preset = p.id;
        form.base_url = p.base_url || "";
        $("#lpf-preset-label").textContent = presetName(p.id);
        $("#lpf-name").value = form.name;
        $("#lpf-url").value = form.base_url;
      },
    })));
  });
  $("#lpf-fetch")?.addEventListener("click", async () => {
    const btn = $("#lpf-fetch");
    if (btn.disabled) return;
    btn.disabled = true;
    const note = $("#lpf-fetch-note");
    try {
      const res = await api("/api/llm/models", { method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preset: form.preset,
          base_url: $("#lpf-url").value.trim(),
          api_key: $("#lpf-key").value.trim() || undefined,
          provider_id: provider ? provider.id : undefined,
        }) });
      if (res.ok && res.items.length) {
        fetchedModels = res.items;
        note.hidden = true;
        $("#lpf-models-field").hidden = false;
        if (!$("#lpf-model").value.trim()) $("#lpf-model").value = res.items[0];
        $("#lpf-models-label").textContent = $("#lpf-model").value.trim();
        toast(t("llm.fetchOk", { n: res.items.length }));
      } else {
        $("#lpf-models-field").hidden = true;
        note.hidden = false;
        note.textContent = res.ok ? t("llm.fetchEmpty")
          : (res.message || t("llm.testFail", { msg: "" }));
      }
    } catch (err) {
      note.hidden = false;
      note.textContent = err.message;
    } finally { btn.disabled = false; }
  });
  $("#lpf-models-pick")?.addEventListener("click", (e) => {
    if (!fetchedModels.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    openDrop(rect.left, rect.bottom + 6, fetchedModels.map((m) => ({
      label: m, active: $("#lpf-model").value.trim() === m,
      run: () => {
        $("#lpf-model").value = m;
        $("#lpf-models-label").textContent = m;
      },
    })));
  });
  $("#lpf-clear-key")?.addEventListener("click", async () => {
    if (!provider) return;
    try {
      llmData = await api(`/api/llm/providers/${provider.id}`, { method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: "" }) });
      $("#lpf-key").placeholder = t("llm.apiKeyPh");
      toast(t("llm.keyCleared"));
    } catch (err) { toast(err.message, true); }
  });
  $("#lpf-cancel")?.addEventListener("click", () => closeModal());
  $("#lpf-save")?.addEventListener("click", async () => {
    const name = $("#lpf-name").value.trim();
    if (!name) { toast(t("llm.needName"), true); return; }
    const payload = {
      name, preset: form.preset,
      base_url: $("#lpf-url").value.trim(),
      default_model: $("#lpf-model").value.trim(),
      enabled: $("#lpf-enabled").checked,
    };
    const key = $("#lpf-key").value.trim();
    if (key) payload.api_key = key;
    try {
      const before = new Set(llmData.items.map((p) => p.id));
      llmData = editing
        ? await api(`/api/llm/providers/${provider.id}`, { method: "PUT",
            headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
        : await api("/api/llm/providers", { method: "POST",
            headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      const created = llmData.items.find((p) => !before.has(p.id));
      if (created && !llmData.active && created.enabled) {
        llmData = await api("/api/llm/active", { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider_id: created.id }) });
      }
      closeModal();
      renderLlmPage();
      toast(t("llm.saved"));
    } catch (err) { toast(err.message, true); }
  });
}

/* ---- chat playground ---- */

function chatMeta() {
  return chatData.conversations.find((c) => c.id === chatData.activeId) || null;
}

async function refreshChats() {
  try {
    const res = await api("/api/llm/conversations");
    chatData.conversations = res.items || [];
  } catch (e) { /* server restarting */ }
  if (chatData.activeId && !chatMeta()) { chatData.activeId = null; chatData.messages = []; }
}

function fmtChatTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  const locale = currentLang === "zh" ? "zh-CN" : "en-US";
  if (d.toDateString() === new Date().toDateString()) {
    return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString(locale, { month: "short", day: "numeric" });
}

function chatBubbleHtml(message) {
  const cls = message.role === "user" ? "llm-msg user" : "llm-msg assistant";
  return `<div class="${cls}"><div class="bubble">${esc(message.content)}</div></div>`;
}

function chatModelLabel() {
  const conv = chatMeta();
  const providerId = (conv && conv.provider_id) || llmData.active;
  const provider = providerId ? llmProviderById(providerId) : null;
  const model = (conv && conv.model) || (provider && provider.default_model) || "";
  const name = provider ? (provider.name || provider.default_model) : "";
  if (!name && !model) return t("chat.chooseModel");
  return `${name}${model && model !== name ? " · " + model : ""}`;
}

function renderChatPanel() {
  const box = $("#llm-chat");
  if (!box) return;
  const usable = llmData.items.some((p) => p.enabled);
  box.innerHTML = `
    <div class="conv-panel">
      <button class="conv-new" id="llm-chat-new"><i class="ph ph-plus"></i>${t("chat.new")}</button>
      <div class="conv-label">${t("chat.recent")}</div>
      <div class="conv-list">
        ${chatData.conversations.map((c) => `
          <div class="conv-item ${c.id === chatData.activeId ? "active" : ""}" data-conv="${esc(c.id)}">
            <button class="conv-open">
              <span class="conv-title">${esc(c.title || t("chat.untitled"))}</span>
              <span class="conv-meta">${fmtChatTime(c.updated_at)}</span>
            </button>
            <button class="conv-del" title="${t("chat.deleteTitle")}"><i class="ph ph-trash"></i></button>
          </div>`).join("") || `<div class="conv-empty">${t("chat.empty")}</div>`}
      </div>
    </div>
    <div class="llm-chat-main">
      <div class="llm-msgs" id="llm-msgs">
        ${chatData.messages.length
          ? chatData.messages.map(chatBubbleHtml).join("")
          : `<div class="llm-msg assistant"><div class="bubble" style="color:var(--text-3)">${t("chat.greeting")}</div></div>`}
        <div class="llm-msg assistant" id="llm-stream" hidden><div class="bubble"></div></div>
      </div>
      <div class="llm-composer">
        <div class="llm-composer-card">
          <textarea class="llm-input" id="llm-chat-input" rows="1" placeholder="${t("chat.placeholder")}"></textarea>
          <div class="llm-bar">
            <span class="spacer"></span>
            <button class="llm-model-btn" id="llm-model-btn"><i class="ph ph-cpu"></i><span>${esc(chatModelLabel())}</span><i class="ph ph-caret-down"></i></button>
            <button class="ghost-btn primary llm-send" id="llm-send" title="${t("chat.send")}"><i class="ph ph-arrow-up"></i></button>
          </div>
        </div>
        <div class="llm-hint"><span>${t("chat.hintKeys")}</span><span>${t("chat.hintLocal")}</span></div>
      </div>
    </div>`;
  bindChatPanel(usable);
  scrollMsgs();
}

function scrollMsgs() {
  const msgs = $("#llm-msgs");
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

function bindChatPanel(usable) {
  $("#llm-chat-new")?.addEventListener("click", () => newConversation());
  $("#llm-chat").querySelectorAll(".conv-item").forEach((item) => {
    item.querySelector(".conv-open").addEventListener("click", () => {
      if (item.dataset.conv !== chatData.activeId) openConversation(item.dataset.conv);
    });
    item.querySelector(".conv-del").addEventListener("click", () => deleteConversation(item.dataset.conv));
  });
  const input = $("#llm-chat-input");
  const send = $("#llm-send");
  const refreshSend = () => {
    if (!send) return;
    send.disabled = !chatData.streaming && !(input.value || "").trim();
    if (!usable && !chatData.streaming) send.disabled = true;
  };
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      if (!chatData.streaming && (input.value || "").trim()) sendChat();
    }
  });
  input?.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 180) + "px";
    refreshSend();
  });
  send?.addEventListener("click", () => { chatData.streaming ? stopChat() : sendChat(); });
  $("#llm-model-btn")?.addEventListener("click", (e) => openModelPop(e.currentTarget));
  if (!usable && !llmData.items.length) input?.setAttribute("disabled", "disabled");
  refreshSend();
}

async function openConversation(id) {
  chatData.activeId = id;
  try {
    const res = await api(`/api/llm/conversations/${id}`);
    chatData.messages = res.messages || [];
  } catch (e) { chatData.messages = []; }
  renderChatPanel();
}

async function newConversation() {
  try {
    const res = await api("/api/llm/conversations", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
    chatData.conversations.unshift(res.conversation);
    chatData.activeId = res.conversation.id;
    chatData.messages = [];
    renderChatPanel();
    $("#llm-chat-input")?.focus();
  } catch (err) { toast(err.message, true); }
}

async function deleteConversation(id) {
  const conv = chatData.conversations.find((c) => c.id === id);
  const title = (conv && conv.title) || t("chat.untitled");
  confirmDialog(t("chat.deleteTitle"), t("chat.deleteMsg", { title }), t("llm.delete"), async () => {
    try {
      await api(`/api/llm/conversations/${id}`, { method: "DELETE" });
      if (chatData.activeId === id) { chatData.activeId = null; chatData.messages = []; }
      await refreshChats();
      renderChatPanel();
      toast(t("chat.deleted"));
    } catch (err) { toast(err.message, true); }
  });
}

function setChatBusy(busy) {
  chatData.streaming = busy;
  const send = $("#llm-send");
  const input = $("#llm-chat-input");
  if (send) {
    send.innerHTML = busy ? `<i class="ph-fill ph-stop"></i>` : `<i class="ph ph-arrow-up"></i>`;
    send.title = busy ? t("chat.stop") : t("chat.send");
    send.disabled = !busy && !(input && (input.value || "").trim());
  }
}

function stopChat() {
  if (chatData.abort) chatData.abort.abort();
}

async function sendChat() {
  if (chatData.streaming) return;
  const input = $("#llm-chat-input");
  const text = (input?.value || "").trim();
  if (!text) return;
  if (!chatData.activeId) {
    await newConversation();
    if (!chatData.activeId) return;
  }
  const msgs = $("#llm-msgs");
  const stream = $("#llm-stream");
  if (!msgs || !stream) return;
  const conv = chatMeta() || {};
  if (!chatData.messages.length) {
    msgs.querySelector(".llm-msg.assistant:not(#llm-stream)")?.remove();
  }
  const userEl = document.createElement("div");
  userEl.className = "llm-msg user";
  userEl.innerHTML = `<div class="bubble"></div>`;
  userEl.querySelector(".bubble").textContent = text;
  msgs.appendChild(userEl);
  chatData.messages.push({ role: "user", content: text });
  stream.hidden = false;
  const bubble = stream.querySelector(".bubble");
  bubble.textContent = "";
  bubble.classList.remove("error");
  input.value = "";
  input.style.height = "auto";
  scrollMsgs();
  setChatBusy(true);
  const ctrl = new AbortController();
  chatData.abort = ctrl;
  try {
    const res = await fetch("/api/llm/chat", { method: "POST", signal: ctrl.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: chatData.activeId,
        provider_id: conv.provider_id || undefined, model: conv.model || undefined, text }) });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (e) { /* keep statusText */ }
      throw new Error(detail);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        for (const line of block.split("\n")) {
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (!payload || payload === "[DONE]") continue;
          let ev;
          try { ev = JSON.parse(payload); } catch (e) { continue; }
          if (ev.delta) { bubble.textContent += ev.delta; scrollMsgs(); }
          else if (ev.error) {
            bubble.classList.add("error");
            bubble.textContent += (bubble.textContent ? "\n" : "") + ev.error;
            scrollMsgs();
          }
        }
      }
    }
  } catch (err) {
    if (err.name !== "AbortError") {
      bubble.classList.add("error");
      bubble.textContent += (bubble.textContent ? "\n" : "") + err.message;
    }
  } finally {
    const finalText = bubble.textContent.trim();
    const isError = bubble.classList.contains("error");
    stream.hidden = true;
    bubble.textContent = "";
    bubble.classList.remove("error");
    setChatBusy(false);
    if (finalText) {
      chatData.messages.push({ role: "assistant", content: finalText });
      if (isError) chatData.messages[chatData.messages.length - 1].error = true;
    }
    await refreshChats();
    renderChatPanel();
  }
}

function closeModelPop() {
  document.querySelectorAll(".llm-model-pop").forEach((el) => el.remove());
}

document.addEventListener("click", (e) => {
  // 重渲染会让事件目标脱离文档（如弹层里的选项）：此时不视作「点击外部」
  if (!e.target.isConnected) return;
  if (!e.target.closest(".llm-model-pop") && !e.target.closest("#llm-model-btn")) closeModelPop();
});

function openModelPop(anchor) {
  closeModelPop();
  const conv = chatMeta();
  let providerId = (conv && conv.provider_id) || llmData.active || null;
  let modelValue = (conv && conv.model) || "";
  const pop = document.createElement("div");
  pop.className = "llm-model-pop";
  document.body.appendChild(pop);
  const renderPop = () => {
    const provider = providerId ? llmProviderById(providerId) : null;
    pop.innerHTML = `
      <label>${t("chat.provider")}</label>
      <div class="llm-model-list">
        ${llmData.items.filter((p) => p.enabled).map((p) => `
          <button class="llm-prov-opt ${p.id === providerId ? "selected" : ""}" data-prov="${esc(p.id)}">
            <span>${esc(p.name || p.default_model)}</span>${p.id === providerId ? `<i class="ph ph-check"></i>` : ""}
          </button>`).join("") || `<div class="conv-empty">${t("chat.needProvider")}</div>`}
      </div>
      <label>${t("chat.model")}</label>
      <div class="llm-model-list" id="llm-pop-models">
        ${(provider ? [provider.default_model] : []).filter(Boolean).map((m) => `
          <button class="llm-model-opt ${m === modelValue ? "selected" : ""}" data-model="${esc(m)}">
            <span>${esc(m)}</span>${m === modelValue ? `<i class="ph ph-check"></i>` : ""}
          </button>`).join("") || `<div class="conv-empty">${t("chat.chooseModel")}</div>`}
      </div>
      <div class="llm-model-row">
        <input class="set-input" id="llm-pop-input" placeholder="${esc((provider && provider.default_model) || t("llm.modelPh"))}" value="${esc(modelValue)}" />
        <button class="ghost-btn" id="llm-pop-fetch">${t("llm.fetchModels")}</button>
      </div>
      <div class="llm-model-row">
        <button class="ghost-btn primary" id="llm-pop-apply">${t("common.confirm")}</button>
      </div>
      <div class="llm-model-note" id="llm-pop-note" hidden></div>`;
    pop.querySelectorAll("[data-prov]").forEach((b) =>
      b.addEventListener("click", () => {
        providerId = b.dataset.prov;
        const provider = llmProviderById(providerId);
        modelValue = (provider && provider.default_model) || "";
        renderPop();
      }));
    pop.querySelectorAll("[data-model]").forEach((b) =>
      b.addEventListener("click", () => {
        modelValue = b.dataset.model;
        $("#llm-pop-input").value = modelValue;
        renderPop();
      }));
    $("#llm-pop-fetch")?.addEventListener("click", async () => {
      const provider = llmProviderById(providerId);
      if (!provider) return;
      const btn = $("#llm-pop-fetch");
      btn.disabled = true;
      try {
        const res = await api("/api/llm/models", { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ preset: provider.preset, base_url: provider.base_url,
            provider_id: provider.id }) });
        const box = $("#llm-pop-models");
        if (res.ok && res.items.length) {
          box.innerHTML = res.items.map((m) => `
            <button class="llm-model-opt ${m === modelValue ? "selected" : ""}" data-model="${esc(m)}">
              <span>${esc(m)}</span>${m === modelValue ? `<i class="ph ph-check"></i>` : ""}
            </button>`).join("");
          box.querySelectorAll("[data-model]").forEach((b) =>
            b.addEventListener("click", () => {
              modelValue = b.dataset.model;
              $("#llm-pop-input").value = modelValue;
              renderPop();
            }));
        } else {
          const note = $("#llm-pop-note");
          note.hidden = false;
          note.textContent = res.message || t("llm.fetchEmpty");
        }
      } catch (err) {
        const note = $("#llm-pop-note");
        note.hidden = false;
        note.textContent = err.message;
      } finally { btn.disabled = false; }
    });
    $("#llm-pop-apply")?.addEventListener("click", async () => {
      const value = ($("#llm-pop-input").value || "").trim() || modelValue;
      if (!chatData.activeId) await newConversation();
      if (!chatData.activeId) return;
      try {
        const res = await api(`/api/llm/conversations/${chatData.activeId}`, { method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider_id: providerId, model: value || null }) });
        const idx = chatData.conversations.findIndex((c) => c.id === res.conversation.id);
        if (idx >= 0) chatData.conversations[idx] = res.conversation;
        const btnLabel = $("#llm-model-btn span");
        if (btnLabel) btnLabel.textContent = chatModelLabel();
        closeModelPop();
      } catch (err) { toast(err.message, true); }
    });
  };
  renderPop();
  const rect = anchor.getBoundingClientRect();
  pop.style.left = Math.max(8, Math.min(rect.right - pop.offsetWidth, innerWidth - pop.offsetWidth - 8)) + "px";
  pop.style.top = Math.max(8, rect.top - pop.offsetHeight - 8) + "px";
}

let pollTimer = null;

function startPolling(sec) {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(refreshSongs, Math.max(500, Math.round(Number(sec || 1.5) * 1000)));
}

function applyFormDefaults() {
  const s = state.server || {};
  $("#adv-maxsec").value = s.default_max_seconds ?? "";
  $("#adv-cfg").value = s.default_cfg ?? "";
}

function fmtBytes(n) {
  if (n == null) return "\u2013";
  if (n >= 2 ** 30) return (n / 2 ** 30).toFixed(2) + " GB";
  if (n >= 2 ** 20) return (n / 2 ** 20).toFixed(1) + " MB";
  return Math.round(n / 1024) + " KB";
}

async function ensureNotifyPermission() {
  if (typeof Notification === "undefined") return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  try { return (await Notification.requestPermission()) === "granted"; } catch { return false; }
}

let pendingConfirm = null;
function confirmDialog(title, message, confirmLabel, onYes) {
  pendingConfirm = onYes;
  openModal(modalShell(title, `
    <div class="modal-from">${esc(message)}</div>
    <div class="confirm-row">
      <button class="ghost-btn" data-m="confirm-no">${t("common.cancel")}</button>
      <button class="ghost-btn primary" data-m="confirm-yes">${esc(confirmLabel)}</button>
    </div>`));
}

function applyLiveSetting(key, value) {
  if (key === "reduce_motion") document.body.classList.toggle("no-motion", !!value);
  else if (key === "poll_interval") startPolling(value);
}

async function saveSetting(payload, { refresh = true } = {}) {
  state.server = await api("/api/settings", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload) });
  if (refresh) openSettings();
  return state.server;
}

function setMode(mode) {
  state.mode = mode;
  $$("#mode-toggle .cp-mode-btn").forEach((b) => b.classList.toggle("active", b.dataset.mode === mode));
  $("#create-panel").dataset.mode = mode;
  $("#pane-simple").hidden = mode !== "simple";
  $("#pane-advanced").hidden = mode !== "advanced";
  refreshCreateBtn();
}

function applyPreferences(s) {
  state.backend = s.default_backend || "torch";
  state.lora = (s.default_lora && state.backend !== "mlx") ? s.default_lora : null;
  state.sort = s.default_sort || "new";
  $("#sort-label").textContent = t(SORT_SHORT[state.sort]);
  setMode(s.default_mode || "simple");
  document.body.classList.toggle("no-motion", !!s.reduce_motion);
  startPolling(s.poll_interval);
  applyFormDefaults();
  refreshModelPill();
  renderFeed();
  showView(s.start_view === "library" ? "library" : "create");
}

/* Generic settings row builders: every option is a .set-row + .set-seg pair. */
function variantText(v) { return v === "8bit" ? "8-bit" : v; }

function segRow(key, label, entries, current, { num = false, loadtime = false } = {}) {
  return `<div class="set-row"><span class="set-label">${label}</span>
    <span class="set-seg" id="${key}-seg">${entries.map(([value, text, ok = true, tip = ""]) =>
      `<button type="button" data-key="${key}" data-value="${value}"${num ? ' data-num="1"' : ""}${loadtime ? ' data-loadtime="1"' : ""} class="${String(current) === String(value) ? "active" : ""}"${ok ? "" : " disabled"}${tip ? ` title="${esc(tip)}"` : ""}>${text}</button>`).join("")}</span></div>`;
}

function numRow(key, label, value, { min = "", max = "", step = "" } = {}) {
  return `<div class="set-row"><span class="set-label">${label}</span>
    <input type="number" class="set-input" id="${key}-input" ${min !== "" ? `min="${min}"` : ""} ${max !== "" ? `max="${max}"` : ""} ${step !== "" ? `step="${step}"` : ""} placeholder="${t("settings.autoPh")}" value="${value ?? ""}" /></div>`;
}

function groupTitle(label) { return `<div class="set-group">${label}</div>`; }

function openSettings() {
  const s = state.server;
  const modal = $("#modal");
  const keepScroll = modal.querySelector("#lang-seg") ? modal.scrollTop : 0;
  const legacyOk = !!s.decoder_legacy_available;
  const mergeOk = !!s.decoder_merge_available;
  const mlxOk = !!s.mlx_available;
  const variants = s.mlx_variants || [];
  const onOff = [[ "true", t("settings.on")], ["false", t("settings.off")]];
  openModal(modalShell(t("settings.title"), `
    ${groupTitle(t("settings.grpCreate"))}
    ${segRow("default_backend", t("settings.defaultBackend"),
        [["mlx", "MLX · " + variantText(s.mlx_variant), mlxOk, mlxOk ? "" : "tools/download_mlx.sh"],
         ["torch", "PyTorch · MPS"]], s.default_backend)}
    ${segRow("default_mode", t("settings.defaultMode"),
        [["simple", t("settings.modeSimple")], ["advanced", t("settings.modeAdvanced")]], s.default_mode)}
    ${numRow("def-maxsec", t("settings.defaultMaxSec"), s.default_max_seconds, { min: 5, max: 360 })}
    ${numRow("def-cfg", t("settings.defaultCfg"), s.default_cfg, { min: 0, max: 20, step: 0.5 })}
    ${segRow("style_language", t("settings.styleLang"),
        [["auto", t("settings.styleAuto")], ["en", t("settings.styleEn")], ["off", t("settings.styleOff")]], s.style_language)}
    ${groupTitle(t("settings.grpGen"))}
    ${segRow("autoplay_on_complete", t("settings.autoplay"), onOff, s.autoplay_on_complete)}
    ${segRow("notify_on_complete", t("settings.notify"), onOff, s.notify_on_complete)}
    ${segRow("poll_interval", t("settings.poll"),
        [["1.5", "1.5s"], ["3", "3s"], ["5", "5s"], ["10", "10s"]], s.poll_interval, { num: true })}
    ${groupTitle(t("settings.grpModel"))}
    ${segRow("decoder", t("settings.decoder"),
        [["default", t("settings.decoderDefault")],
         ["legacy", t("settings.decoderLegacy"), legacyOk, legacyOk ? "" : "tools/download_extras.sh"],
         ["merge", t("settings.decoderMerge"), mergeOk, mergeOk ? "" : "tools/download_extras.sh"]], s.decoder)}
    <p class="set-note">${t("settings.decoderNote")}</p>
    ${variants.length ? segRow("mlx_variant", t("settings.mlxVariant"),
        variants.map((v) => [v, variantText(v)]), s.mlx_variant) : ""}
    <p class="set-note">${t("settings.mlxVariantNote")}</p>
    ${s.device === "cuda" ? `
    ${segRow("backend", t("settings.backend"),
        [["torch", "PyTorch"], ["vllm", "vLLM", s.vllm_available, s.vllm_available ? "" : "pip install vllm"]], s.backend, { loadtime: true })}
    ${segRow("quantization", t("settings.quantization"),
        [["none", t("settings.off")], ["fp8", "FP8"]], s.quantization, { loadtime: true })}
    ${segRow("offload_ar", t("settings.offload"), onOff, s.offload_ar, { loadtime: true })}` : ""}
    ${s.device === "cuda" ? numRow("budget", t("settings.budget"), esc(String(s.budget ?? 24)), { min: 4, max: 1024, step: 1 }) :
      `<div class="set-row"><span class="set-label">${t("settings.budget")}</span>
      <input type="number" class="set-input" id="budget-input" min="4" max="1024" step="1" value="${esc(String(s.budget ?? 24))}" /></div>`}
    <p class="set-note">${t("settings.perfNote")}</p>
    <div class="set-row"><span class="set-label">${t("settings.doctor")}</span>
      <button class="ghost-btn" id="run-doctor">${t("settings.doctorRun")}</button></div>
    <div class="doctor-box" id="doctor-box" hidden></div>
    ${groupTitle(t("settings.grpUi"))}
    <div class="set-row">
      <span class="set-label">${t("settings.language")}</span>
      <span class="set-seg" id="lang-seg">
        <button type="button" data-lang="en" class="${currentLang === "en" ? "active" : ""}">English</button>
        <button type="button" data-lang="zh" class="${currentLang === "zh" ? "active" : ""}">中文</button>
      </span>
    </div>
    ${segRow("start_view", t("settings.startView"),
        [["create", t("nav.create")], ["library", t("nav.library")]], s.start_view)}
    ${segRow("default_sort", t("settings.defaultSort"),
        [["new", t("sort.newShort")], ["old", t("sort.oldShort")], ["title", t("sort.titleShort")]], s.default_sort)}
    ${segRow("reduce_motion", t("settings.reduceMotion"), onOff, s.reduce_motion)}
    ${groupTitle(t("settings.grpMaint"))}
    <div class="set-row"><span class="set-label">${t("settings.storage")}</span>
      <span class="set-value" id="storage-line">\u2026</span></div>
    <div class="set-row"><span class="set-label"></span>
      <button class="ghost-btn" id="cleanup-btn"><i class="ph ph-broom"></i>${t("settings.cleanup")}</button></div>
    <div class="set-row"><span class="set-label">${t("settings.reset")}</span>
      <button class="ghost-btn" id="reset-btn"><i class="ph ph-arrow-counter-clockwise"></i>${t("settings.resetBtn")}</button></div>
    ${groupTitle(t("settings.grpStatus"))}
    <div class="set-row"><span class="set-label">${t("settings.model")}</span><span class="set-value">YuE2-3B · ${esc(s.model || "\u2026")}</span></div>
    <div class="set-row"><span class="set-label">${t("settings.device")}</span><span class="set-value">${esc(s.device || "\u2026")}</span></div>
    <div class="set-row"><span class="set-label">${t("settings.transcription")}</span><span class="set-value">${s.transcribe_available ? t("settings.trReady") : t("settings.trMissing")}</span></div>
  `));
  if (keepScroll) modal.scrollTop = keepScroll;

  $("#lang-seg").addEventListener("click", (e) => {
    const b = e.target.closest("[data-lang]");
    if (!b) return;
    setLang(b.dataset.lang);
    openSettings();
  });

  $$("#modal .set-seg").forEach((seg) => {
    if (seg.id === "lang-seg") return;
    seg.addEventListener("click", async (e) => {
      const b = e.target.closest("button[data-key]");
      if (!b || b.disabled) return;
      const key = b.dataset.key;
      let value = b.dataset.value;
      if (b.dataset.num === "1") value = Number(value);
      else if (value === "true") value = true;
      else if (value === "false") value = false;
      if (b.dataset.loadtime === "1" && state.server.current) { toast(t("toast.settingsBusy"), true); return; }
      if (key === "notify_on_complete" && value === true) {
        const ok = await ensureNotifyPermission();
        if (!ok) { toast(t("toast.notifyDenied"), true); return; }
      }
      try {
        await saveSetting({ [key]: value });
        if (key === "default_backend") setBackend(value);
        applyLiveSetting(key, value);
      } catch (err) { toast(err.message, true); }
    });
  });

  const bindOptionalNumber = (key) => {
    const el = $("#" + key + "-input");
    el.addEventListener("change", async () => {
      const raw = el.value.trim();
      try { await saveSetting({ [key]: raw === "" ? null : Number(raw) }); }
      catch (err) { toast(err.message, true); openSettings(); }
    });
  };
  bindOptionalNumber("def-maxsec");
  bindOptionalNumber("def-cfg");

  const budgetInput = $("#budget-input");
  if (budgetInput) budgetInput.addEventListener("change", async () => {
    if (state.server.current) { toast(t("toast.settingsBusy"), true); openSettings(); return; }
    try { await saveSetting({ budget: Number(budgetInput.value) }); }
    catch (err) { toast(err.message, true); openSettings(); }
  });

  const runDoctorBtn = $("#run-doctor");
  if (runDoctorBtn) runDoctorBtn.addEventListener("click", async () => {
    try {
      const data = await api("/api/doctor");
      renderDoctor(data);
    } catch (err) { toast(err.message, true); }
  });

  const storageLine = $("#storage-line");
  api("/api/storage").then((st) => {
    storageLine.textContent = t("settings.storageLine", {
      out: fmtBytes(st.outputs.bytes), up: fmtBytes(st.uploads.bytes),
      lat: fmtBytes(st.outputs.latent_bytes) });
  }).catch(() => { storageLine.textContent = "\u2013"; });

  $("#cleanup-btn").addEventListener("click", () => {
    confirmDialog(t("settings.cleanup"), t("settings.cleanupConfirm"), t("settings.cleanup"), async () => {
      try {
        const res = await api("/api/storage/cleanup", { method: "POST" });
        toast(t("toast.cleaned", { n: fmtBytes(res.freed_bytes) }));
        await refreshSongs();
        openSettings();
      } catch (err) { toast(err.message, true); }
    });
  });
  $("#reset-btn").addEventListener("click", () => {
    confirmDialog(t("settings.reset"), t("settings.resetConfirm"), t("settings.resetBtn"), async () => {
      try {
        await saveSetting({ reset_defaults: true }, { refresh: false });
        applyPreferences(state.server);
        openSettings();
        toast(t("toast.resetDone"));
      } catch (err) { toast(err.message, true); }
    });
  });
}

function renderDoctor(data) {
  const box = $("#doctor-box");
  if (!box) return;
  const groups = [["files", t("doctor.files")], ["env", t("doctor.env")], ["lora", t("doctor.lora")]];
  let html = "";
  for (const [key, label] of groups) {
    const rows = (data.checks || []).filter((c) => c.group === key);
    if (!rows.length) continue;
    html += `<div class="doctor-group">${label}</div>`;
    html += rows.map((c) => `<div class="doctor-row"><i class="ph ${c.ok ? "ph-check-circle ok" : "ph-x-circle bad"}"></i><span>${esc(c.name)}</span><span class="dr-detail">${esc(c.detail)}</span></div>`).join("");
  }
  const v = data.verify || {};
  if (v.state === "running") {
    html += `<div class="doctor-row" style="margin-top:10px"><i class="ph ph-circle-notch spin ok"></i><span>${t("settings.hashRunning")}</span></div>`;
  } else {
    if (v.state === "done" && v.results) {
      html += v.results.map((r) => `<div class="doctor-row"><i class="ph ${r.ok ? "ph-check-circle ok" : "ph-x-circle bad"}"></i><span>${esc(r.name)}</span><span class="dr-detail">${r.ok ? t("doctor.verifyOk") : t("doctor.verifyBad")} · ${r.seconds}s</span></div>`).join("");
    } else {
      html += `<button class="ghost-btn" id="hash-verify" style="margin-top:10px"><i class="ph ph-shield-check"></i>${t("settings.hashVerify")}</button>`;
    }
  }
  html += `<p class="set-note" style="margin:8px 2px 2px">${t("doctor.verifyNote")}</p>`;
  box.innerHTML = html;
  box.hidden = false;
  const vbtn = $("#hash-verify");
  if (vbtn) vbtn.addEventListener("click", async () => {
    try {
      await api("/api/doctor/verify", { method: "POST" });
      renderDoctor({ ...data, verify: { state: "running" } });
      clearInterval(doctorTimer);
      doctorTimer = setInterval(async () => {
        if ($("#overlay").hidden) { clearInterval(doctorTimer); doctorTimer = null; return; }
        try {
          const st = await api("/api/doctor/verify");
          renderDoctor({ ...data, verify: st });
          if (st.state === "done") { clearInterval(doctorTimer); doctorTimer = null; }
        } catch (err) { /* keep polling */ }
      }, 2500);
    } catch (err) { toast(err.message, true); }
  });
}

/* ---------------- batch create & listening comparison ---------------- */

function formSnapshot() {
  const simple = state.mode === "simple";
  const snap = {
    style: (simple ? $("#simple-desc") : $("#adv-style")).value.trim(),
    lyrics: simple ? "" : $("#adv-lyrics").value,
    cot: state.cot,
    backend: state.backend,
  };
  if (!simple) {
    if ($("#adv-instrumental").checked) snap.instrumental = true;
    if ($("#adv-planonly").checked) snap.plan_only = true;
    if ($("#adv-title").value.trim()) snap.title = $("#adv-title").value.trim();
    if ($("#adv-seed").value !== "") snap.seed = Number($("#adv-seed").value);
    if ($("#adv-cfg").value !== "") snap.cfg_scale = Number($("#adv-cfg").value);
    for (const [id, key] of [["#sam-temperature", "temperature"], ["#sam-topp", "top_p"], ["#sam-topk", "top_k"],
                             ["#adv-maxsec", "max_seconds"], ["#sam-odesteps", "ode_steps"]]) {
      const v = $(id).value.trim();
      if (v !== "") snap[key] = Number(v);
    }
  }
  if (state.lora) snap.lora = state.lora;
  if (state.attachAbc) snap.abc = state.attachAbc.text;
  return snap;
}

function openBatch() {
  openModal(modalShell(t("batch.title"), `
    <div class="modal-from">${t("batch.desc")}</div>
    <div class="input-shell"><textarea id="batch-text" rows="10" spellcheck="false" placeholder="${esc(t("batch.ph"))}"></textarea></div>
    <div class="score-attach-tools">
      <button class="ghost-btn" id="batch-export"><i class="ph ph-download-simple"></i>${t("batch.export")}</button>
    </div>
    <button class="create-btn" data-m="do-batch"><i class="ph-fill ph-stack"></i>${t("batch.create")}</button>
  `));
  $("#batch-export").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(formSnapshot(), null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "request.json";
    a.click();
    URL.revokeObjectURL(a.href);
  });
}
$("#open-batch").addEventListener("click", openBatch);

function openCompare() {
  const items = state.songs.filter((s) => isPlayable(s) && s.kind === "song");
  if (items.length < 2) { toast(t("compare.need2"), true); return; }
  openModal(modalShell(t("compare.title"), `
    <div class="modal-from">${t("compare.desc")}</div>
    <div class="compare-list" id="compare-list">
      ${items.map((s) => `<label class="compare-row"><input type="checkbox" value="${s.id}" /><span class="cr-title">${esc(s.title)}</span><span class="cr-dur">${fmtTime(s.audio_seconds)}</span></label>`).join("")}
    </div>
    <button class="create-btn" data-m="do-compare"><i class="ph-fill ph-arrows-left-right"></i>${t("compare.create")}</button>
  `));
}
$("#compare-pill").addEventListener("click", openCompare);

async function loadVariant(id) {
  try {
    const d = await api(`/api/songs/${id}`);
    closeDetail();
    showView("create");
    state.mode = "advanced";
    $$("#mode-toggle .cp-mode-btn").forEach((b) => b.classList.toggle("active", b.dataset.mode === "advanced"));
    $("#create-panel").dataset.mode = "advanced";
    $("#pane-simple").hidden = true;
    $("#pane-advanced").hidden = false;
    $("#adv-style").value = dispStyle(d);
    $("#adv-lyrics").value = d.lyrics || "";
    $("#adv-title").value = d.title ? `${d.title} v2` : "";
    if (d.seed != null) $("#adv-seed").value = d.seed;
    state.cot = d.cot || "full";
    state.backend = d.backend || "torch";
    state.lora = d.lora || null;
    $("#lora-label").textContent = loraLabel();
    refreshModelPill();
    refreshCreateBtn();
    toast(t("variant.loaded"));
  } catch (e) { toast(e.message, true); }
}

async function queueAllModes(id) {
  try {
    const d = await api(`/api/songs/${id}`);
    const requests = ["full", "melody", "off"].map((cot) => ({
      title: `${d.title} · ${cot}`, style: d.style, lyrics: d.lyrics || "", cot,
      seed: d.seed, instrumental: !!d.instrumental,
      lora: d.lora || undefined, backend: d.backend || "torch",
    }));
    await api("/api/songs/batch", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ requests }) });
    toast(t("allmodes.queued"));
    await refreshSongs();
  } catch (e) { toast(e.message, true); }
}

async function doRedecode(id, decoder) {
  try {
    await api(`/api/songs/${id}/redecode`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decoder }) });
    toast(t("detail.recodeQueued"));
    await refreshSongs();
  } catch (e) { toast(e.message, true); }
}

let uploadFile = null;

function openUpload() {
  if (!state.server.transcribe_available) { toast(t("upload.noTranscribe"), true); return; }
  openModal(modalShell(t("upload.title"), `
    <div class="drop-zone" id="drop-zone">
      <i class="ph ph-cloud-arrow-up"></i>
      <p><span class="dz-name" id="dz-name">${t("upload.choose")}</span><br/>${t("upload.formats")}</p>
    </div>
    <div class="input-shell"><label class="input-label">${t("upload.fieldTitle")}</label>
      <input type="text" id="upload-title" maxlength="80" placeholder="${esc(t("upload.optional"))}" /></div>
    <p class="score-note">${t("upload.note")}</p>
    <button class="create-btn" id="do-upload" disabled><i class="ph-fill ph-upload-simple"></i>${t("upload.transcribe")}</button>
  `));
  const dz = $("#drop-zone");
  dz.addEventListener("dragover", (e) => { e.preventDefault(); dz.classList.add("drag"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("drag"));
  dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("drag");
    const f = e.dataTransfer.files[0];
    if (f) setUploadFile(f);
  });
}

function setUploadFile(f) {
  uploadFile = f;
  const name = $("#dz-name");
  if (name) name.textContent = f.name;
  const btn = $("#do-upload");
  if (btn) btn.disabled = false;
}

$("#file-input").addEventListener("change", () => {
  const f = $("#file-input").files[0];
  if (f) setUploadFile(f);
});

$("#modal").addEventListener("click", async (e) => {
  if (e.target.closest("#drop-zone")) { $("#file-input").click(); return; }
  const radio = e.target.closest(".radio-card");
  if (radio) { radio.parentElement.querySelectorAll(".radio-card").forEach((c) => c.classList.toggle("active", c === radio)); return; }
  const el = e.target.closest("[data-m]");
  if (!el) return;
  const action = el.dataset.m;
  const id = el.dataset.id;
  try {
    if (action === "close") closeModal();
    else if (action === "confirm-no") { pendingConfirm = null; closeModal(); }
    else if (action === "confirm-yes") { const fn = pendingConfirm; pendingConfirm = null; closeModal(); if (fn) await fn(); }
    else if (action === "attach-score") {
      const text = $("#score-text").value.trim();
      if (!text) { toast(t("score.ph"), true); return; }
      state.attachAbc = { name: state.attachName || "ABC", text };
      state.attachName = null;
      updateAttachChip();
      closeModal();
    }
    else if (action === "do-batch") {
      const raw = $("#batch-text").value.trim();
      if (!raw) { toast(t("batch.empty"), true); return; }
      let requests = null;
      try {
        const parsed = JSON.parse(raw);
        requests = Array.isArray(parsed) ? parsed : [parsed];
      } catch (err) {
        const lines = raw.split("\n").map((s) => s.trim()).filter(Boolean);
        if (lines.length) requests = lines.map((style) => ({ ...formSnapshot(), style }));
      }
      if (!requests || !requests.length) { toast(t("batch.bad"), true); return; }
      el.disabled = true;
      const created = await api("/api/songs/batch", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requests }) });
      closeModal();
      await refreshSongs();
      toast(t("batch.queued", { n: created.length }));
    }
    else if (action === "do-compare") {
      const ids = [...document.querySelectorAll("#compare-list input:checked")].map((i) => i.value);
      if (ids.length < 2) { toast(t("compare.need2"), true); return; }
      el.disabled = true;
      const res = await api("/api/compare", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids }) });
      window.open(res.url, "_blank");
      toast(t("compare.done"));
      closeModal();
    }
    else if (action === "do-cover") {
      const style = $("#cover-style").value.trim();
      if (!style) { toast(t("toast.needRemixStyle"), true); return; }
      el.disabled = true;
      await api(`/api/songs/${id}/cover`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ style, lyrics: $("#cover-lyrics").value, mode: $("#cover-mode .radio-card.active").dataset.value,
                               instrumental: $("#cover-instrumental").checked,
                               backend: coverSel.backend, lora: coverSel.lora }) });
      closeModal(); await refreshSongs();
      toast(t("toast.remixQueued"));
    }
    else if (action === "do-edit") {
      const abcEl = $("#edit-abc");
      el.disabled = true;
      await api(`/api/songs/${id}/edit`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: $("#edit-title").value, style: $("#edit-style").value, lyrics: $("#edit-lyrics").value,
                               abc: abcEl ? abcEl.value : null,
                               backend: editSel.backend, lora: editSel.lora }) });
      closeModal(); await refreshSongs();
      toast(t("toast.editQueued"));
    }
  } catch (err) { el.disabled = false; toast(err.message, true); }
});

$("#modal").addEventListener("click", async (e) => {
  if (!e.target.closest("#do-upload")) return;
  if (!uploadFile) return;
  const btn = e.target.closest("#do-upload");
  btn.disabled = true;
  const form = new FormData();
  form.append("file", uploadFile);
  form.append("title", $("#upload-title").value);
  try {
    await api("/api/uploads", { method: "POST", body: form });
    uploadFile = null;
    $("#file-input").value = "";
    closeModal();
    await refreshSongs();
    toast(t("toast.uploadQueued"));
  } catch (err) { btn.disabled = false; toast(err.message, true); }
});

/* ---------------- language ---------------- */

document.addEventListener("lang-changed", () => {
  $("#sort-label").textContent = t(SORT_SHORT[state.sort]);
  $("#view-label").textContent = t(state.feedGrid ? "view.grid" : "view.list");
  $("#lora-label").textContent = loraLabel();
  refreshModelPill();
  renderAll();
  renderPlayer();
  refreshState();
});

/* ---------------- boot ---------------- */

renderStyleChips();
refreshCreateBtn();
refreshLoras();
refreshModelPill();
$("#sort-label").textContent = t(SORT_SHORT[state.sort]);
$("#view-label").textContent = t(state.feedGrid ? "view.grid" : "view.list");
renderPlayer();
refreshSongs();
startPolling(1.5);
refreshState().then(() => applyPreferences(state.server)).catch(() => {});
setInterval(refreshState, 3000);
