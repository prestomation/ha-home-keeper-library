// The styles of the tab. Every rule reads a `--hkl-*` token. Each token resolves
// to a Home Assistant theme variable, with the mock color as the fallback, so a
// dark theme works. Cover and spine colors are artwork and stay literal.

export const TOKENS = `
  --hkl-primary: var(--primary-color, #0277bd);
  --hkl-on-primary: var(--text-primary-color, #ffffff);
  --hkl-bg: var(--primary-background-color, #fafafa);
  --hkl-surface: var(--card-background-color, var(--ha-card-background, #ffffff));
  --hkl-text: var(--primary-text-color, #212121);
  --hkl-muted: var(--secondary-text-color, #616161);
  --hkl-divider: var(--divider-color, #e0e0e0);
  --hkl-outline: color-mix(in srgb, var(--hkl-text) 26%, transparent);
  --hkl-tonal: color-mix(in srgb, var(--hkl-primary) 13%, var(--hkl-surface));
  --hkl-tonal-ink: color-mix(in srgb, var(--hkl-primary) 72%, var(--hkl-text));
  --hkl-chip: color-mix(in srgb, var(--hkl-text) 7%, var(--hkl-surface));
  --hkl-warn: var(--warning-color, #ef8f00);
  --hkl-warn-soft: color-mix(in srgb, var(--hkl-warn) 15%, var(--hkl-surface));
  --hkl-warn-ink: color-mix(in srgb, var(--hkl-warn) 58%, var(--hkl-text));
  --hkl-error: var(--error-color, #d32f2f);
  --hkl-error-soft: color-mix(in srgb, var(--hkl-error) 13%, var(--hkl-surface));
  --hkl-error-ink: color-mix(in srgb, var(--hkl-error) 75%, var(--hkl-text));
  --hkl-ok: var(--success-color, #2e7d32);
  --hkl-ok-soft: color-mix(in srgb, var(--hkl-ok) 14%, var(--hkl-surface));
  --hkl-ok-ink: color-mix(in srgb, var(--hkl-ok) 75%, var(--hkl-text));
  --hkl-ring-read: #43a047;
  --hkl-ring-reading: #fb8c00;
  --hkl-star: #f9a825;
  --hkl-wood: color-mix(in srgb, #8d6e63 70%, var(--hkl-surface));
  --hkl-radius: 12px;
  --hkl-font: var(--ha-font-family-body, Roboto, 'Noto Sans', sans-serif);
`;

export const STYLES = `
:host { display: block; ${TOKENS} color: var(--hkl-text); font-family: var(--hkl-font); font-size: 14px; }
* { box-sizing: border-box; }
.hkl-root { padding: 12px 0 32px; display: flex; flex-direction: column; gap: 16px; max-width: 1240px; margin: 0 auto; }
a { color: var(--hkl-primary); }
h1 { font-size: 26px; font-weight: 500; margin: 0; line-height: 1.2; }
h2 { font-size: 17px; font-weight: 500; margin: 0; }
p { margin: 0; }
.hkl-muted { color: var(--hkl-muted); }
.small { font-size: 12px; }
.block { display: block; }
.hkl-spacer { flex: 1 1 8px; }
.hkl-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.hkl-eyebrow { font-size: 12px; font-weight: 500; letter-spacing: .6px; text-transform: uppercase; color: var(--hkl-muted); }
.hkl-loading, .hkl-empty { color: var(--hkl-muted); padding: 32px 0; text-align: center; }
.hkl-error { color: var(--hkl-error-ink); background: var(--hkl-error-soft); border-radius: 8px; padding: 8px 12px; }
.hkl-foot { color: var(--hkl-muted); font-size: 12px; text-align: right; }

/* Buttons */
button { font: inherit; color: inherit; }
.hkl-btn { height: 40px; padding: 0 20px; border: none; border-radius: 20px; font: 500 14px var(--hkl-font); display: inline-flex; align-items: center; justify-content: center; gap: 8px; cursor: pointer; white-space: nowrap; }
.hkl-btn.primary { background: var(--hkl-primary); color: var(--hkl-on-primary); }
.hkl-btn.tonal { background: var(--hkl-tonal); color: var(--hkl-tonal-ink); }
.hkl-btn.text { background: none; color: var(--hkl-tonal-ink); padding: 0 12px; }
.hkl-btn.outline { background: var(--hkl-surface); color: var(--hkl-tonal-ink); border: 1px solid var(--hkl-outline); }
.hkl-btn.danger { background: none; color: var(--hkl-error-ink); border: 1px solid color-mix(in srgb, var(--hkl-error) 40%, transparent); }
.hkl-btn.danger-primary { background: var(--hkl-error); color: #fff; }
.hkl-btn[disabled] { opacity: .5; cursor: default; }
.hkl-btn:focus-visible, .hkl-navchip:focus-visible, .hkl-seg:focus-visible, .hkl-tile:focus-visible, .hkl-row:focus-visible, .hkl-choice:focus-visible { outline: 2px solid var(--hkl-primary); outline-offset: 2px; }
.hkl-link { background: none; border: none; padding: 4px 6px; color: var(--hkl-primary); cursor: pointer; font-size: 13px; }
.hkl-link.danger { color: var(--hkl-error-ink); }
.hkl-link.plain { padding: 0; color: var(--hkl-text); font-size: inherit; text-align: left; }
.hkl-iconbtn { width: 40px; height: 40px; border: none; border-radius: 20px; background: none; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; color: var(--hkl-muted); }
.hkl-back { align-self: flex-start; display: inline-flex; align-items: center; gap: 4px; background: none; border: none; color: var(--hkl-primary); cursor: pointer; font-weight: 500; padding: 4px 0; }

/* Navigation */
.hkl-navrow { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.hkl-nav { display: flex; flex-wrap: wrap; gap: 8px; }
.hkl-actions { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.hkl-navchip { height: 36px; display: inline-flex; align-items: center; gap: 6px; padding: 0 16px; border-radius: 18px; background: var(--hkl-surface); border: 1px solid var(--hkl-outline); color: var(--hkl-text); font-weight: 500; cursor: pointer; white-space: nowrap; }
.hkl-navchip.on { background: var(--hkl-primary); border-color: var(--hkl-primary); color: var(--hkl-on-primary); }
.hkl-badge { background: var(--hkl-chip); color: var(--hkl-text); border-radius: 10px; padding: 1px 8px; font-size: 12px; font-weight: 500; }
.hkl-badge.warn { background: var(--hkl-warn-soft); color: var(--hkl-warn-ink); }

/* Filters */
.hkl-filterbar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.hkl-segs { display: inline-flex; flex-wrap: wrap; border: 1px solid var(--hkl-outline); border-radius: 18px; overflow: hidden; background: var(--hkl-surface); }
.hkl-seg { height: 34px; padding: 0 14px; border: none; border-left: 1px solid var(--hkl-divider); background: none; font: 500 13px var(--hkl-font); color: var(--hkl-text); cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.hkl-seg:first-child { border-left: none; }
.hkl-seg.on { background: var(--hkl-tonal); color: var(--hkl-tonal-ink); }
.hkl-seg-n { color: var(--hkl-muted); font-weight: 400; }
.hkl-seg.on .hkl-seg-n { color: inherit; opacity: .8; }
.hkl-search { flex: 1 1 260px; display: flex; align-items: center; gap: 8px; height: 36px; padding: 0 12px; border: 1px solid var(--hkl-outline); border-radius: 8px; background: var(--hkl-surface); color: var(--hkl-muted); }
.hkl-search input { border: none; outline: none; flex: 1; min-width: 0; font: 14px var(--hkl-font); background: transparent; color: var(--hkl-text); }
.hkl-menus { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.hkl-menu { position: relative; height: 32px; display: inline-flex; align-items: center; gap: 6px; padding: 0 10px 0 12px; border: 1px solid var(--hkl-outline); border-radius: 8px; background: var(--hkl-surface); }
.hkl-menu-label { font: 500 12px var(--hkl-font); letter-spacing: .4px; text-transform: uppercase; color: var(--hkl-muted); }
.hkl-menu select { border: none; background: transparent; font: 700 12px var(--hkl-font); color: var(--hkl-text); max-width: 180px; cursor: pointer; outline: none; }
.hkl-menu select option { color: #212121; }
.hkl-toggle { display: inline-flex; border: 1px solid var(--hkl-outline); border-radius: 8px; overflow: hidden; }
.hkl-toggle button { width: 40px; height: 32px; border: none; border-left: 1px solid var(--hkl-divider); background: var(--hkl-surface); display: flex; align-items: center; justify-content: center; color: var(--hkl-muted); cursor: pointer; }
.hkl-toggle button:first-child { border-left: none; }
.hkl-toggle button.on { background: var(--hkl-tonal); color: var(--hkl-tonal-ink); }
.hkl-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-height: 22px; }

/* Covers */
.hkl-cover { position: relative; display: flex; flex-direction: column; justify-content: space-between; aspect-ratio: 2 / 3; border-radius: 4px 8px 8px 4px; background: var(--c); color: var(--ink); box-shadow: 0 1px 2px rgba(0,0,0,.25), inset 6px 0 0 rgba(0,0,0,.12); padding: 14px 12px 12px 18px; overflow: hidden; }
.hkl-cover.has-img { padding: 0; background: var(--hkl-chip); }
.hkl-cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.hkl-cover-title { font-family: Fraunces, Georgia, 'Times New Roman', serif; font-weight: 700; font-size: 17px; line-height: 1.15; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 5; -webkit-box-orient: vertical; overflow: hidden; }
.hkl-cover-author { font-size: 11px; letter-spacing: .8px; text-transform: uppercase; opacity: .85; }
.hkl-cover-badge { position: absolute; bottom: 8px; right: 8px; background: rgba(255,255,255,.92); color: #01579b; font-size: 10px; font-weight: 500; padding: 2px 6px; border-radius: 8px; }
.hkl-cover-thumb { width: 40px; flex: 0 0 40px; padding: 4px 3px 3px 7px; border-radius: 2px 4px 4px 2px; box-shadow: 0 1px 2px rgba(0,0,0,.25), inset 3px 0 0 rgba(0,0,0,.12); }
.hkl-cover-thumb .hkl-cover-title { font-size: 6px; -webkit-line-clamp: 6; overflow-wrap: normal; word-break: normal; }
.hkl-cover-thumb.blank { background: var(--hkl-chip); box-shadow: none; }
.hkl-cover-large { width: 100%; max-width: 240px; padding: 22px 18px 18px 28px; }
.hkl-cover-large .hkl-cover-title { font-size: 26px; }
.hkl-cover-large .hkl-cover-author { font-size: 13px; }

/* Grid and rows */
.hkl-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 20px 16px; }
.hkl-tile { display: flex; flex-direction: column; gap: 6px; color: var(--hkl-text); text-decoration: none; border-radius: 8px; min-width: 0; }
.hkl-tile-title { font-weight: 500; font-size: 14px; line-height: 1.25; }
.hkl-tile-author { font-size: 12px; color: var(--hkl-muted); }
.hkl-tile-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.hkl-tile-meta:empty { display: none; }
.hkl-tile-readers { display: flex; align-items: center; gap: 8px; min-height: 24px; padding-left: 2px; }
.hkl-loc { font-size: 11px; color: var(--hkl-text); border: 1px solid var(--hkl-divider); border-radius: 10px; padding: 1px 8px; background: var(--hkl-surface); }
.hkl-dot { width: 20px; height: 20px; flex: 0 0 20px; border-radius: 10px; background: var(--p, #00695c); color: #fff; font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; }
.hkl-dot.ring-read { box-shadow: 0 0 0 2px var(--hkl-surface), 0 0 0 4px var(--hkl-ring-read); }
.hkl-dot.ring-reading { box-shadow: 0 0 0 2px var(--hkl-surface), 0 0 0 4px var(--hkl-ring-reading); }
.hkl-ring { width: 16px; height: 16px; flex: 0 0 16px; border-radius: 8px; border: 3px solid var(--hkl-ring-read); }
.hkl-ring.ring-reading { border-color: var(--hkl-ring-reading); }
.hkl-pill { align-self: flex-start; font-size: 11px; background: var(--hkl-chip); color: var(--hkl-text); border-radius: 10px; padding: 2px 8px; white-space: nowrap; }
.hkl-tile .hkl-pill { white-space: normal; max-width: 100%; }
.hkl-pill.loan, .hkl-pill.soon, .hkl-pill.warn, .hkl-pill.st-reading { background: var(--hkl-warn-soft); color: var(--hkl-warn-ink); }
.hkl-pill.late { background: var(--hkl-error-soft); color: var(--hkl-error-ink); }
.hkl-pill.ok, .hkl-pill.st-read { background: var(--hkl-ok-soft); color: var(--hkl-ok-ink); }
.hkl-pill.st-want { background: var(--hkl-tonal); color: var(--hkl-tonal-ink); }
.hkl-rows, .hkl-list { display: flex; flex-direction: column; }
.hkl-row, .hkl-listrow { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-bottom: 1px solid var(--hkl-divider); color: var(--hkl-text); text-decoration: none; background: var(--hkl-surface); }
.hkl-rows { border: 1px solid var(--hkl-divider); border-radius: var(--hkl-radius); overflow: hidden; }
.hkl-row:last-child, .hkl-listrow:last-child { border-bottom: none; }
.hkl-row-main { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.hkl-row-title { font-weight: 500; }
.hkl-row-sub { font-size: 13px; color: var(--hkl-muted); }
.hkl-row-loc { font-size: 12px; color: var(--hkl-muted); }
.hkl-row-dots { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.hkl-more { display: flex; justify-content: center; }
.hkl-legend { display: flex; gap: 16px; align-items: center; color: var(--hkl-muted); font-size: 12px; flex-wrap: wrap; border-top: 1px solid var(--hkl-divider); padding-top: 12px; }
.hkl-legend > span { display: inline-flex; align-items: center; gap: 6px; }

/* Cards and boxes */
.hkl-card { background: var(--hkl-surface); border: 1px solid var(--hkl-divider); border-radius: var(--hkl-radius); padding: 16px; display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.hkl-card > .hkl-btn, .hkl-copy .hkl-box-actions { align-self: flex-start; }
.hkl-banner .hkl-btn.tonal { background: var(--hkl-surface); }
.hkl-card-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.hkl-head-actions { display: inline-flex; align-items: center; gap: 12px; flex-wrap: nowrap; }
.hkl-banner { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 10px 14px; border-radius: 10px; background: var(--hkl-tonal); color: var(--hkl-tonal-ink); }
.hkl-banner.warn { background: var(--hkl-warn-soft); color: var(--hkl-warn-ink); }
.hkl-banner.info { background: var(--hkl-surface); color: var(--hkl-text); border: 1px solid var(--hkl-divider); }
.hkl-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.hkl-chip { font-size: 12px; background: var(--hkl-chip); border-radius: 12px; padding: 3px 10px; }
.hkl-kv { display: flex; justify-content: space-between; gap: 12px; padding: 4px 0; border-bottom: 1px dashed var(--hkl-divider); }
.hkl-kv > span:first-child { color: var(--hkl-muted); }
.hkl-two { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 16px; align-items: start; }

/* Detail */
.hkl-detail { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 24px; align-items: start; }
.hkl-detail-cover { display: flex; flex-direction: column; gap: 8px; }
.hkl-cover-actions { display: flex; flex-wrap: wrap; gap: 4px; }
.hkl-detail-info { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.hkl-subtitle { font-size: 16px; color: var(--hkl-muted); }
.hkl-byline { font-size: 15px; }
.hkl-desc { color: var(--hkl-muted); line-height: 1.5; max-width: 70ch; }
.hkl-boxes { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.hkl-box { border: 1px solid var(--hkl-divider); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 4px; background: var(--hkl-surface); }
.hkl-box.late { border-color: var(--hkl-error); }
.hkl-box-main { font-weight: 500; }
.hkl-box-sub { font-size: 13px; color: var(--hkl-muted); }
.hkl-box-actions { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.hkl-box-actions .hkl-btn { height: 32px; padding: 0 14px; font-size: 13px; }
.hkl-task { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; }
.hkl-reading { display: flex; flex-wrap: wrap; gap: 12px 20px; align-items: center; }
.hkl-stars { display: inline-flex; }
.hkl-star { width: 32px; height: 32px; border: none; background: none; padding: 4px; cursor: pointer; }
.hkl-star svg { fill: none; stroke: var(--hkl-muted); stroke-width: 1.5; }
.hkl-star.on svg { fill: var(--hkl-star); stroke: var(--hkl-star); }
.hkl-fields { display: flex; flex-wrap: wrap; gap: 12px; }
.hkl-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--hkl-muted); flex: 1 1 180px; min-width: 0; }
.hkl-field.small { flex: 0 1 140px; }
.hkl-field.wide { flex: 1 1 100%; }
.hkl-field input, .hkl-field select, .hkl-field textarea, .hkl-input, .hkl-notes-form textarea, .hkl-isbn input { height: 40px; padding: 0 10px; border: 1px solid var(--hkl-outline); border-radius: 8px; background: var(--hkl-surface); color: var(--hkl-text); font: 14px var(--hkl-font); width: 100%; min-width: 0; }
.hkl-field textarea, .hkl-notes-form textarea { height: auto; padding: 8px 10px; resize: vertical; }
.hkl-input.narrow { width: 90px; }
.hkl-inline { display: inline-flex; align-items: center; gap: 6px; color: var(--hkl-muted); }
.hkl-inline select { border: 1px solid var(--hkl-outline); border-radius: 8px; height: 32px; background: var(--hkl-surface); color: var(--hkl-text); padding: 0 6px; }
.hkl-check { display: flex; align-items: flex-start; gap: 8px; cursor: pointer; line-height: 1.35; }
.hkl-check input { width: 18px; height: 18px; margin: 1px 0 0; accent-color: var(--hkl-primary); flex: 0 0 auto; }
.hkl-check.big { font-size: 15px; padding: 8px 0; }
.hkl-household { display: flex; flex-direction: column; gap: 8px; }
.hkl-hh { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.hkl-hh-name { min-width: 60px; font-weight: 500; }
.hkl-bar { width: 120px; height: 6px; border-radius: 3px; background: var(--hkl-chip); overflow: hidden; display: inline-block; }
.hkl-bar > span { display: block; height: 100%; background: var(--hkl-warn); }
.hkl-subtabs { display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid var(--hkl-divider); }
.hkl-subtab { height: 40px; padding: 0 14px; border: none; border-bottom: 2px solid transparent; background: none; font-weight: 500; color: var(--hkl-muted); cursor: pointer; display: inline-flex; align-items: center; gap: 6px; }
.hkl-subtab.on { color: var(--hkl-primary); border-bottom-color: var(--hkl-primary); }
.hkl-md-plain { white-space: pre-wrap; line-height: 1.5; }
.hkl-notes-form { display: flex; flex-direction: column; gap: 8px; }
.hkl-copy { display: flex; flex-direction: column; gap: 2px; padding-bottom: 8px; }
.hkl-detail-actions { display: flex; flex-wrap: wrap; gap: 8px; }

/* Rooms and shelves */
.hkl-places { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 20px; align-items: start; }
.hkl-rooms { display: flex; flex-direction: column; gap: 4px; position: sticky; top: 8px; }
.hkl-roombtn { display: flex; justify-content: space-between; align-items: center; height: 40px; padding: 0 12px; border: none; border-radius: 8px; background: none; cursor: pointer; text-align: left; color: var(--hkl-text); font-weight: 500; }
.hkl-roombtn.on { background: var(--hkl-tonal); color: var(--hkl-tonal-ink); }
.hkl-room { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.hkl-case { background: var(--hkl-surface); border: 1px solid var(--hkl-divider); border-radius: var(--hkl-radius); padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.hkl-case-body { display: flex; flex-direction: column; gap: 14px; }
.hkl-shelf { display: flex; flex-direction: column; }
.hkl-shelf-books { display: flex; align-items: flex-end; gap: 2px; min-height: 84px; padding: 0 8px; overflow: hidden; }
.hkl-spine { display: block; flex: 0 0 auto; border-radius: 2px 2px 0 0; box-shadow: inset -2px 0 0 rgba(0,0,0,.18), inset 0 6px 0 rgba(255,255,255,.08); }
.hkl-spine:hover { transform: translateY(-3px); }
.hkl-board { height: 8px; border-radius: 2px; background: var(--hkl-wood); }
.hkl-shelf-label { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; padding-top: 6px; }
.hkl-shelf-name { font-weight: 500; }

/* Scan */
.hkl-scan { display: flex; flex-direction: column; gap: 0; max-width: 560px; width: 100%; margin: 0 auto; background: var(--hkl-surface); border: 1px solid var(--hkl-divider); border-radius: var(--hkl-radius); overflow: hidden; }
.hkl-scan-head { height: 56px; display: flex; align-items: center; gap: 8px; padding: 0 8px; border-bottom: 1px solid var(--hkl-divider); font-size: 18px; font-weight: 500; }
.hkl-scan-body { padding: 16px; display: flex; flex-direction: column; gap: 20px; }
.hkl-step { display: flex; flex-direction: column; gap: 8px; }
.hkl-sub { font-size: 13px; color: var(--hkl-muted); margin-top: 4px; }
.hkl-choices { display: flex; flex-wrap: wrap; gap: 8px; }
.hkl-choice { min-height: 44px; min-width: 44px; padding: 0 16px; border-radius: 10px; border: 1px solid var(--hkl-outline); background: var(--hkl-surface); cursor: pointer; font-weight: 500; color: var(--hkl-text); }
.hkl-choice.on { background: var(--hkl-primary); border-color: var(--hkl-primary); color: var(--hkl-on-primary); }
.hkl-radio { display: flex; gap: 12px; align-items: flex-start; padding: 12px; border: 1px solid var(--hkl-divider); border-radius: 10px; cursor: pointer; }
.hkl-radio.on { border-color: var(--hkl-primary); background: var(--hkl-tonal); }
.hkl-radio input { margin-top: 3px; accent-color: var(--hkl-primary); }
.hkl-radio > span { display: flex; flex-direction: column; gap: 2px; }
.hkl-scan-foot { padding: 12px 16px 16px; display: flex; gap: 8px; justify-content: flex-end; border-top: 1px solid var(--hkl-divider); flex-wrap: wrap; }
.hkl-scan-foot .hkl-btn { flex: 1 1 160px; }
.hkl-cam { position: relative; background: #111; aspect-ratio: 4 / 3; max-height: 52vh; width: 100%; overflow: hidden; }
.hkl-cam-video, .hkl-cam-video video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.hkl-frame { position: absolute; left: 12%; right: 12%; top: 30%; bottom: 30%; border: 3px solid rgba(255,255,255,.92); border-radius: 12px; box-shadow: 0 0 0 999px rgba(0,0,0,.35); }
.hkl-cam-hint { position: absolute; left: 0; right: 0; bottom: 12px; text-align: center; color: #fff; font-weight: 500; text-shadow: 0 1px 2px #000; }
.hkl-iconbtn.torch { position: absolute; top: 10px; right: 10px; background: rgba(0,0,0,.45); color: #fff; }
.hkl-iconbtn.torch.on { background: #fff; color: #111; }
.hkl-cam-msg { margin: 16px; padding: 12px 14px; border-radius: 10px; background: var(--hkl-warn-soft); color: var(--hkl-warn-ink); }
.hkl-tray { display: flex; flex-direction: column; gap: 8px; padding: 12px 16px 16px; }
.hkl-tray-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-weight: 500; }
.hkl-isbn { display: flex; gap: 8px; }
.hkl-results { display: flex; flex-direction: column; gap: 8px; }
.hkl-result { display: flex; align-items: center; gap: 10px; flex-wrap: nowrap; padding: 8px; border: 1px solid var(--hkl-divider); border-radius: 10px; }
.hkl-result.dup { border-color: var(--hkl-warn); flex-wrap: wrap; }
.hkl-result.warn { border-style: dashed; }
.hkl-result.late { border-color: var(--hkl-error); }
.hkl-dup { display: flex; flex-wrap: wrap; gap: 6px; width: 100%; padding-left: 50px; }
.hkl-dup .hkl-btn { height: 34px; padding: 0 12px; font-size: 13px; }
.hkl-tray-foot { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; padding-top: 8px; }
.hkl-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.hkl-stat { display: flex; flex-direction: column; align-items: center; padding: 12px 4px; border-radius: 10px; background: var(--hkl-tonal); color: var(--hkl-tonal-ink); }
.hkl-stat b { font-size: 26px; }

/* Loans and wishlist */
.hkl-listrow { position: relative; padding-left: 16px; flex-wrap: wrap; }
.hkl-edge { position: absolute; left: 0; top: 8px; bottom: 8px; width: 4px; border-radius: 2px; background: var(--hkl-divider); }
.hkl-listrow.late .hkl-edge { background: var(--hkl-error); }
.hkl-listrow.soon .hkl-edge { background: var(--hkl-warn); }
.hkl-listrow .hkl-pill, .hkl-result .hkl-pill { align-self: center; }
.hkl-who { display: inline-flex; align-items: center; gap: 6px; }
.hkl-todos { display: flex; flex-direction: column; gap: 6px; }
.hkl-todo { display: inline-flex; align-items: center; gap: 8px; }

/* Tables */
.hkl-tablewrap { overflow-x: auto; }
.hkl-table { width: 100%; border-collapse: collapse; }
.hkl-table th, .hkl-table td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--hkl-divider); vertical-align: middle; }
.hkl-table th { font-size: 12px; font-weight: 500; color: var(--hkl-muted); }
.hkl-table tbody th { color: var(--hkl-text); font-size: 14px; }
.hkl-table .num { text-align: right; }
.hkl-table.small td { font-size: 12px; }
.hkl-details summary { cursor: pointer; color: var(--hkl-primary); }

/* Dialogs */
.hkl-scrim { position: fixed; inset: 0; z-index: 10; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; padding: 16px; }
.hkl-dialog { width: min(560px, 100%); max-height: calc(100vh - 32px); overflow-y: auto; background: var(--hkl-surface); color: var(--hkl-text); border-radius: 16px; padding: 20px 24px; display: flex; flex-direction: column; gap: 14px; box-shadow: 0 12px 40px rgba(0,0,0,.3); }
.hkl-dialog.wide { width: min(760px, 100%); }
.hkl-dlg-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.hkl-dlg-body { display: flex; flex-direction: column; gap: 12px; }
.hkl-dlg-actions { display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.hkl-file { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 14px; border: 1px solid var(--hkl-divider); border-radius: 10px; flex-wrap: wrap; }
.hkl-file.empty { border-style: dashed; }
.hkl-pills { display: inline-flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; }
.hkl-inline-form { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px 12px; }
.hkl-checklist { display: flex; flex-direction: column; gap: 6px; max-height: 260px; overflow-y: auto; }

/* Phone layout */
@media (max-width: 700px) {
  .hkl-root { padding: 8px 0 24px; gap: 12px; }
  .hkl-navrow { flex-direction: column; flex-wrap: nowrap; align-items: stretch; }
  .hkl-navrow > .hkl-spacer { display: none; }
  .hkl-actions:empty { display: none; }
  .hkl-nav { flex-wrap: nowrap; overflow-x: auto; scrollbar-width: none; }
  .hkl-actions { justify-content: flex-start; }
  .hkl-actions .hkl-btn { flex: 1 1 auto; }
  .hkl-segs { flex-wrap: nowrap; overflow-x: auto; max-width: 100%; }
  .hkl-seg { flex: 0 0 auto; }
  .hkl-search { flex-basis: 100%; height: 44px; }
  .hkl-menus { flex-wrap: nowrap; overflow-x: auto; padding-bottom: 4px; }
  .hkl-menu { flex: 0 0 auto; }
  .hkl-grid { grid-template-columns: repeat(auto-fill, minmax(104px, 1fr)); gap: 16px 10px; }
  .hkl-cover { padding: 10px 8px 8px 12px; }
  .hkl-cover-title { font-size: 13px; }
  .hkl-cover-author { font-size: 9px; }
  .hkl-row .hkl-row-dots { display: none; }
  .hkl-detail { grid-template-columns: 1fr; }
  .hkl-reading .hkl-segs { display: grid; grid-template-columns: 1fr 1fr; border-radius: 12px; width: 100%; }
  .hkl-reading .hkl-seg { border-left: none; border-top: 1px solid var(--hkl-divider); justify-content: center; }
  .hkl-reading .hkl-seg:nth-child(-n+2) { border-top: none; }
  .hkl-reading .hkl-seg:nth-child(even) { border-left: 1px solid var(--hkl-divider); }
  .hkl-cover-large .hkl-cover-badge { display: none; }
  .hkl-detail-cover { flex-direction: row; align-items: flex-end; }
  .hkl-cover-large { max-width: 120px; padding: 12px 10px 10px 16px; }
  .hkl-cover-large .hkl-cover-title { font-size: 15px; }
  .hkl-cover-actions { flex-direction: column; align-items: flex-start; }
  h1 { font-size: 22px; }
  .hkl-two { grid-template-columns: 1fr; }
  .hkl-places { grid-template-columns: 1fr; }
  .hkl-rooms { position: static; flex-direction: row; flex-wrap: nowrap; overflow-x: auto; align-items: center; }
  .hkl-rooms .hkl-eyebrow, .hkl-rooms > .hkl-muted { display: none; }
  .hkl-roombtn { flex: 0 0 auto; gap: 8px; border: 1px solid var(--hkl-outline); }
  .hkl-scan { max-width: none; }
  .hkl-cam { aspect-ratio: 3 / 4; }
  .hkl-scrim { align-items: flex-end; padding: 0; }
  .hkl-dialog, .hkl-dialog.wide { width: 100%; border-radius: 16px 16px 0 0; max-height: 92vh; padding: 16px; }
  .hkl-listrow .hkl-btn { height: 36px; }
  .hkl-table th, .hkl-table td { padding: 6px; }
}
`;
