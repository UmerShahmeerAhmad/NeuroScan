/* ==========================================================================
   NeuroScan AI design system
   Idea: a radiology reading room. Dark, quiet surfaces so the scan and the
   result are the brightest things on screen. One signal teal for actions,
   amber only for "look closer", and a serif voice for headings.
   ========================================================================== */

:root {
  --ink: #070d1a;
  --panel: #0d1729;
  --film: #132038;
  --film-hi: #1a2b4a;
  --line: #22324f;
  --line-soft: #19273f;

  --text: #e7eef9;
  --muted: #8d9cb8;
  --faint: #62718e;

  --signal: #36d1c4;
  --signal-ink: #04211f;
  --amber: #f2b84b;
  --danger: #ff7a7a;
  --ok: #4ade9a;
  --sky: #6ab7ff;

  --serif: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;

  --r-panel: 14px;
  --r-ctl: 9px;
}

/* ---------- base ---------- */
*, *::before, *::after { box-sizing: border-box; }
html { color-scheme: dark; -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--ink);
  color: var(--text);
  font-family: var(--sans);
  font-size: 16px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
body.modal-open { overflow: hidden; }
[hidden] { display: none !important; }
img { max-width: 100%; }
a { color: var(--signal); }
a:hover { text-decoration: underline; }
h1, h2, h3, p { margin-top: 0; }
:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }

.container { width: min(1120px, 100% - 48px); margin-inline: auto; }
.muted { color: var(--muted); }
.nowrap { white-space: nowrap; }
.sr-only {
  position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}

/* ---------- class colors (used by chips, bars, result headline) ---------- */
.c-glioma     { --c: #ff8a7a; }
.c-meningioma { --c: #f2b84b; }
.c-pituitary  { --c: #6ab7ff; }
.c-notumor    { --c: #4ade9a; }
.c-other      { --c: #b69cff; }

/* ---------- buttons ---------- */
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 10px;
  height: 44px; padding: 0 20px;
  border: 1px solid transparent; border-radius: var(--r-ctl);
  font: inherit; font-weight: 600; font-size: .95rem; line-height: 1;
  text-decoration: none; cursor: pointer;
  transition: background-color .15s, border-color .15s, filter .15s, transform .08s;
}
.btn:hover { text-decoration: none; }
.btn:active:not([disabled]) { transform: translateY(1px); }
.btn[disabled] { opacity: .5; cursor: not-allowed; }
.btn-sm { height: 34px; padding: 0 13px; font-size: .86rem; }
.btn-block { width: 100%; }

.btn-primary { background: var(--signal); color: var(--signal-ink); }
.btn-primary:hover:not([disabled]) { filter: brightness(1.08); }

.btn-ghost { background: transparent; color: var(--text); border-color: var(--line); }
.btn-ghost:hover:not([disabled]) { background: var(--film); border-color: #2f456b; }

.btn-ok { background: rgba(74, 222, 154, .12); color: var(--ok); border-color: rgba(74, 222, 154, .38); }
.btn-ok:hover:not([disabled]) { background: rgba(74, 222, 154, .2); }

.btn-danger { background: transparent; color: var(--danger); border-color: rgba(255, 122, 122, .4); }
.btn-danger:hover:not([disabled]) { background: rgba(255, 122, 122, .12); }

.spinner {
  display: inline-block; width: 16px; height: 16px; flex: none;
  border: 2px solid currentColor; border-right-color: transparent; border-radius: 50%;
  animation: spin .7s linear infinite;
}
.spinner.big { width: 34px; height: 34px; border-width: 3px; color: var(--signal); }
@keyframes spin { to { transform: rotate(360deg); } }

/* ---------- forms ---------- */
.field { margin-bottom: 18px; }
label { display: block; margin-bottom: 7px; font-size: .88rem; font-weight: 600; color: #c3cfe3; }
.optional { font-weight: 400; color: var(--faint); }

.input {
  width: 100%; height: 46px; padding: 0 14px;
  background: var(--film); color: var(--text);
  border: 1px solid var(--line); border-radius: var(--r-ctl);
  font: inherit;
  transition: border-color .15s, box-shadow .15s;
}
.input::placeholder { color: var(--faint); }
.input:focus { outline: none; border-color: var(--signal); box-shadow: 0 0 0 3px rgba(54, 209, 196, .18); }
.input[aria-invalid="true"] { border-color: var(--danger); }
.textarea { height: auto; padding: 12px 14px; resize: vertical; line-height: 1.5; }
select.input { cursor: pointer; }

.input-wrap { position: relative; }
.input-wrap .input { padding-right: 76px; }
.toggle {
  position: absolute; right: 6px; top: 6px; height: 34px; padding: 0 12px;
  background: transparent; border: 0; border-radius: 7px;
  color: var(--muted); font: inherit; font-size: .85rem; font-weight: 600; cursor: pointer;
}
.toggle:hover { color: var(--text); }

.hint { margin: 6px 0 0; font-size: .84rem; color: var(--faint); }
.field-error { margin: 6px 0 0; font-size: .84rem; color: var(--danger); }

.alert {
  margin-bottom: 18px; padding: 12px 14px;
  border: 1px solid var(--line); border-left-width: 3px; border-radius: var(--r-ctl);
  background: var(--film); font-size: .95rem;
}
.alert-error { border-color: rgba(255, 122, 122, .35); border-left-color: var(--danger); background: rgba(255, 122, 122, .07); }
.alert-warn  { border-color: rgba(242, 184, 75, .35); border-left-color: var(--amber); background: rgba(242, 184, 75, .07); }
.alert-info  { border-color: rgba(106, 183, 255, .3); border-left-color: var(--sky); background: rgba(106, 183, 255, .07); }
.alert-success { border-color: rgba(74, 222, 154, .3); border-left-color: var(--ok); background: rgba(74, 222, 154, .07); }
.alert .btn { margin-left: 10px; vertical-align: middle; }

/* ---------- badges and chips ---------- */
.badge {
  display: inline-block; padding: 2px 10px; border: 1px solid var(--line); border-radius: 99px;
  font-size: .8rem; font-weight: 600; white-space: nowrap;
}
.badge-pending  { color: var(--amber);  border-color: rgba(242, 184, 75, .4);  background: rgba(242, 184, 75, .1); }
.badge-approved { color: var(--ok);     border-color: rgba(74, 222, 154, .4);  background: rgba(74, 222, 154, .1); }
.badge-rejected { color: var(--danger); border-color: rgba(255, 122, 122, .4); background: rgba(255, 122, 122, .1); }
.badge-review   { color: var(--amber);  border-color: rgba(242, 184, 75, .4);  background: rgba(242, 184, 75, .1); margin-left: 8px; }

.chip {
  display: inline-flex; align-items: center; gap: 8px; padding: 3px 12px 3px 10px;
  border: 1px solid var(--line); border-radius: 99px; background: rgba(255, 255, 255, .05);
  font-size: .86rem; font-weight: 600; white-space: nowrap;
}
.chip i { width: 8px; height: 8px; border-radius: 50%; background: var(--c, var(--signal)); }
@supports (background: color-mix(in srgb, red, blue)) {
  .chip {
    background: color-mix(in srgb, var(--c, var(--signal)) 13%, transparent);
    border-color: color-mix(in srgb, var(--c, var(--signal)) 40%, transparent);
  }
}

/* ---------- brand and top bar ---------- */
.brand {
  display: inline-flex; align-items: center; gap: 10px;
  color: var(--text); text-decoration: none; font-weight: 700; font-size: 1.05rem;
}
.brand:hover { text-decoration: none; }
.brand-mark { width: 30px; height: 30px; color: var(--signal); flex: none; }

.topbar {
  position: sticky; top: 0; z-index: 50;
  background: rgba(7, 13, 26, .9); backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line-soft);
}
.topbar-inner { display: flex; align-items: center; gap: 16px; height: 64px; }
.role-tag {
  padding: 3px 10px; border: 1px solid var(--line); border-radius: 99px;
  color: var(--muted); font-size: .8rem; font-weight: 600;
}
.topbar-user { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.avatar {
  display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%;
  background: var(--film-hi); color: var(--signal); font-size: .85rem; font-weight: 700;
}
.user-name { font-size: .92rem; font-weight: 600; }

/* ---------- dashboard layout ---------- */
.page { padding: 36px 0 80px; }
.page-head { margin-bottom: 26px; }
.page-head h1 { margin-bottom: 6px; font-family: var(--serif); font-size: 2rem; font-weight: 600; line-height: 1.2; }
.page-head p { max-width: 64ch; margin: 0; color: var(--muted); }

.panel {
  margin-bottom: 24px; padding: 24px;
  background: var(--panel); border: 1px solid var(--line-soft); border-radius: var(--r-panel);
}
.panel h2 { margin: 0; font-family: var(--serif); font-size: 1.35rem; font-weight: 600; }
.panel-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 18px; }
.panel-note { margin: 4px 0 0; color: var(--muted); font-size: .92rem; max-width: 70ch; }

.ledger {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  margin-bottom: 24px; overflow: hidden;
  background: var(--panel); border: 1px solid var(--line-soft); border-radius: var(--r-panel);
}
.ledger-item { padding: 20px 24px; border-left: 1px solid var(--line-soft); }
.ledger-item:first-child { border-left: 0; }
.ledger-value { font-family: var(--serif); font-size: 2.2rem; line-height: 1.1; }
.ledger-label { margin-top: 4px; color: var(--muted); font-size: .9rem; }
.ledger-item[class*="c-"] .ledger-value { color: var(--c); }

.tabs { display: flex; gap: 4px; margin-bottom: 24px; overflow-x: auto; border-bottom: 1px solid var(--line); }
.tab {
  display: inline-flex; align-items: center; gap: 8px; margin-bottom: -1px; padding: 12px 16px;
  background: none; border: 0; border-bottom: 2px solid transparent;
  color: var(--muted); font: inherit; font-weight: 600; white-space: nowrap; cursor: pointer;
}
.tab:hover { color: var(--text); }
.tab[aria-selected="true"] { color: var(--signal); border-bottom-color: var(--signal); }
.count {
  display: inline-grid; place-items: center; min-width: 20px; height: 20px; padding: 0 6px;
  border-radius: 99px; background: var(--amber); color: #2a1d00; font-size: .75rem; font-weight: 700;
}

.toolbar { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.toolbar .input { width: auto; min-width: 180px; height: 40px; }
.toolbar .grow { flex: 1; min-width: 220px; }

/* ---------- tables ---------- */
.table-wrap { margin: 0 -8px; overflow-x: auto; }
.data-table { width: 100%; min-width: 680px; border-collapse: collapse; }
.data-table th {
  padding: 10px 12px; border-bottom: 1px solid var(--line);
  color: var(--muted); font-size: .85rem; font-weight: 600; text-align: left;
}
.data-table td { padding: 14px 12px; border-bottom: 1px solid var(--line-soft); vertical-align: middle; }
.data-table tbody tr:last-child td { border-bottom: 0; }
.data-table tbody tr:hover { background: rgba(255, 255, 255, .02); }
.data-table .right { text-align: right; }
.cell-title { font-weight: 600; }
.cell-sub { margin-top: 2px; color: var(--muted); font-size: .88rem; }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
.empty { padding: 36px 12px; text-align: center; color: var(--muted); }
.empty strong { display: block; margin-bottom: 4px; color: var(--text); font-size: 1.05rem; }

.mini {
  display: inline-block; width: 64px; height: 6px; margin-left: 10px; overflow: hidden;
  border-radius: 99px; background: var(--film); vertical-align: middle;
}
.mini > i { display: block; width: var(--w); height: 100%; background: var(--c, var(--signal)); }

/* ---------- probability bars ---------- */
.dist { display: grid; gap: 12px; }
.dist-row { display: grid; grid-template-columns: minmax(110px, 160px) 1fr 58px; align-items: center; gap: 14px; }
.dist-label { display: flex; align-items: center; gap: 9px; font-size: .94rem; }
.dist-label i { width: 9px; height: 9px; flex: none; border-radius: 50%; background: var(--c, var(--signal)); }
.dist-track { height: 8px; overflow: hidden; border-radius: 99px; background: var(--film); }
.dist-fill {
  width: var(--w, 0%); height: 100%; border-radius: 99px; background: var(--c, var(--signal));
  transition: width .8s cubic-bezier(.2, .8, .2, 1);
}
.dist-row:not(.is-top) .dist-fill { opacity: .5; }
.dist-value { text-align: right; font-variant-numeric: tabular-nums; color: var(--muted); }
.dist-row.is-top .dist-value { color: var(--text); font-weight: 600; }

/* ---------- scan workspace (doctor) ---------- */
.workspace { display: grid; grid-template-columns: minmax(300px, 420px) 1fr; gap: 24px; align-items: start; }
.workspace .panel { margin-bottom: 0; }

.viewer {
  position: relative; display: grid; place-items: center; overflow: hidden;
  aspect-ratio: 1 / 1; margin-bottom: 14px;
  background: #02050b; border: 1px solid var(--line); border-radius: 12px;
  cursor: pointer; transition: border-color .15s;
}
.viewer:hover, .viewer.drag { border-color: var(--signal); }
.viewer-static { cursor: default; }
.viewer-static:hover { border-color: var(--line); }
/* corner brackets, like the frame of a film viewer */
.viewer::before, .viewer::after {
  content: ""; position: absolute; width: 22px; height: 22px; opacity: .75; pointer-events: none;
  border: 0 solid var(--signal);
}
.viewer::before { top: 10px; left: 10px; border-top-width: 2px; border-left-width: 2px; }
.viewer::after { right: 10px; bottom: 10px; border-right-width: 2px; border-bottom-width: 2px; }
.viewer-img { width: 100%; height: 100%; object-fit: contain; }
.viewer-empty { padding: 24px; text-align: center; color: var(--muted); }
.viewer-empty strong { display: block; margin-bottom: 4px; color: var(--text); font-size: 1.05rem; }
.file-line { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 18px; font-size: .9rem; color: var(--muted); }
.file-line span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.result-state { display: grid; justify-items: center; gap: 14px; padding: 56px 12px; text-align: center; color: var(--muted); }
.result-state p { margin: 0; }
.result-state strong { color: var(--text); font-size: 1.05rem; }
.result-enter { animation: reveal .4s cubic-bezier(.2, .8, .2, 1); }
@keyframes reveal { from { opacity: 0; transform: translateY(8px); } }

.result-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; margin-bottom: 22px; }
.result-label { margin-bottom: 2px; color: var(--muted); font-size: .88rem; }
.result-class { font-family: var(--serif); font-size: clamp(2rem, 4vw, 2.8rem); font-weight: 600; line-height: 1.1; color: var(--c, var(--text)); }
.result-conf { text-align: right; }
.result-conf-value { display: block; font-family: var(--serif); font-size: 2.4rem; line-height: 1; }
.disclaimer { margin: 22px 0 0; padding-top: 16px; border-top: 1px solid var(--line-soft); color: var(--faint); font-size: .88rem; }
.result-meta { margin: 8px 0 0; color: var(--faint); font-size: .86rem; }

.detail-list { display: grid; grid-template-columns: auto 1fr; gap: 6px 18px; margin: 0 0 22px; font-size: .92rem; }
.detail-list dt { color: var(--muted); }
.detail-list dd { margin: 0; word-break: break-word; }

/* ---------- modal and toasts ---------- */
.modal-backdrop {
  position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; padding: 20px;
  background: rgba(3, 7, 14, .74); backdrop-filter: blur(3px);
  opacity: 0; transition: opacity .18s;
}
.modal-backdrop.show { opacity: 1; }
.modal {
  width: min(480px, 100%); max-height: calc(100vh - 40px); overflow: auto; padding: 24px;
  background: var(--panel); border: 1px solid var(--line); border-radius: var(--r-panel);
  transform: translateY(8px); transition: transform .18s;
}
.modal-backdrop.show .modal { transform: none; }
.modal-wide { width: min(780px, 100%); }
.modal h3 { margin: 0 0 6px; font-family: var(--serif); font-size: 1.35rem; font-weight: 600; }
.modal-msg { margin: 0 0 16px; color: var(--muted); }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.modal-split { display: grid; grid-template-columns: minmax(200px, 300px) 1fr; gap: 24px; align-items: start; }
.modal-split .viewer { margin-bottom: 0; }

.toast-stack { position: fixed; right: 20px; bottom: 20px; z-index: 200; display: grid; gap: 10px; width: min(360px, 100% - 40px); }
.toast {
  padding: 12px 14px; background: var(--film-hi);
  border: 1px solid var(--line); border-left: 3px solid var(--signal); border-radius: var(--r-ctl);
  box-shadow: 0 8px 24px rgba(0, 0, 0, .4); font-size: .94rem;
  animation: reveal .25s;
}
.toast-error { border-left-color: var(--danger); }
.toast-success { border-left-color: var(--ok); }

/* ==========================================================================
   Landing page
   ========================================================================== */
.site-nav { display: flex; align-items: center; justify-content: space-between; height: 76px; }
.site-links { display: flex; align-items: center; gap: 22px; }
.site-links a:not(.btn) { color: var(--muted); font-size: .95rem; text-decoration: none; }
.site-links a:not(.btn):hover { color: var(--text); }

.hero { display: grid; grid-template-columns: 1.05fr .95fr; gap: 56px; align-items: center; padding: 48px 0 88px; }
.hero h1 {
  margin-bottom: 22px; font-family: var(--serif); font-weight: 600;
  font-size: clamp(2.5rem, 5.4vw, 4.1rem); line-height: 1.04; letter-spacing: -.015em;
}
.lead { max-width: 46ch; margin-bottom: 30px; color: #b6c3da; font-size: 1.15rem; }
.hero-actions { display: flex; flex-wrap: wrap; gap: 12px; }
.fine { max-width: 46ch; margin: 22px 0 0; color: var(--faint); font-size: .88rem; }

.hero-art { position: relative; width: 100%; max-width: 480px; margin-left: auto; }
.scan-svg { display: block; width: 100%; height: auto; }
.scan-line { animation: sweep 6.5s cubic-bezier(.45, 0, .55, 1) infinite alternate; }
@keyframes sweep { from { transform: translateY(-30px); } to { transform: translateY(400px); } }
.ring { transform-box: fill-box; transform-origin: center; animation: spin 26s linear infinite; }

.readout {
  position: absolute; right: -6px; bottom: 5%; width: min(256px, 64%); padding: 14px 16px;
  background: rgba(13, 23, 41, .94); border: 1px solid var(--line); border-radius: 12px;
  backdrop-filter: blur(6px);
}
.readout-title { color: var(--muted); font-size: .8rem; }
.readout-class { font-family: var(--serif); font-size: 1.55rem; line-height: 1.2; color: var(--c); }
.readout-conf { margin-bottom: 12px; color: var(--muted); font-size: .86rem; }
.readout .dist { gap: 8px; }
.readout .dist-row { grid-template-columns: 82px 1fr 44px; gap: 10px; font-size: .82rem; }
.readout .dist-label { font-size: .82rem; }
.readout .dist-fill { transition: none; animation: grow 1.6s .5s cubic-bezier(.2, .8, .2, 1) both; }
@keyframes grow { from { width: 0; } }

.band { padding: 72px 0; border-top: 1px solid var(--line-soft); }
.band h2 { margin-bottom: 12px; font-family: var(--serif); font-size: clamp(1.7rem, 3vw, 2.2rem); font-weight: 600; line-height: 1.2; }
.band-head { max-width: 56ch; margin-bottom: 36px; }
.band-head p { margin: 0; color: var(--muted); }

.steps { max-width: 720px; margin: 0; padding: 0; list-style: none; counter-reset: step; }
.steps li { position: relative; padding: 0 0 32px 64px; counter-increment: step; }
.steps li::before {
  content: counter(step); position: absolute; left: 0; top: 0;
  display: grid; place-items: center; width: 40px; height: 40px;
  border: 1px solid var(--signal); border-radius: 50%;
  color: var(--signal); font-family: var(--serif); font-size: 1.1rem;
}
.steps li::after { content: ""; position: absolute; left: 20px; top: 48px; bottom: 8px; width: 1px; background: var(--line); }
.steps li:last-child { padding-bottom: 0; }
.steps li:last-child::after { display: none; }
.steps h3 { margin-bottom: 4px; font-size: 1.1rem; }
.steps p { margin: 0; color: var(--muted); max-width: 56ch; }

.reports { display: grid; grid-template-columns: 1fr 1fr; gap: 64px; }
.report-list { margin: 0; padding: 0; }
.report-list > div { padding: 16px 0; border-top: 1px solid var(--line-soft); }
.report-list dt { display: flex; align-items: center; gap: 10px; margin-bottom: 2px; font-weight: 600; }
.report-list dt i { width: 9px; height: 9px; border-radius: 50%; background: var(--c); }
.report-list dd { margin: 0 0 0 19px; color: var(--muted); }
.safeguards h3 { margin-bottom: 4px; font-size: 1.05rem; }
.safeguards p { margin: 0 0 24px; color: var(--muted); max-width: 52ch; }

.site-footer { padding: 32px 0 40px; border-top: 1px solid var(--line-soft); color: var(--faint); font-size: .9rem; }
.site-footer p { max-width: 70ch; margin: 0; }

/* ==========================================================================
   Login and signup
   ========================================================================== */
.auth { display: grid; grid-template-columns: minmax(320px, .85fr) 1.15fr; min-height: 100vh; }
.auth-aside {
  position: relative; display: flex; flex-direction: column; justify-content: space-between; gap: 40px;
  padding: 44px 48px; overflow: hidden;
  background-color: var(--panel); border-right: 1px solid var(--line-soft);
  background-image: repeating-radial-gradient(circle at 18% 88%, transparent 0 26px, rgba(54, 209, 196, .07) 27px 28px);
}
.auth-aside h2 { max-width: 13em; margin-bottom: 12px; font-family: var(--serif); font-size: 2.1rem; font-weight: 600; line-height: 1.15; }
.auth-aside p { max-width: 38ch; margin: 0; color: var(--muted); }
.auth-main { display: grid; place-items: center; padding: 40px 24px; }
.auth-card { width: min(440px, 100%); }
.auth-card.wide { width: min(580px, 100%); }
.auth-mobile-brand { display: none; margin-bottom: 28px; }
.auth-title { margin-bottom: 6px; font-family: var(--serif); font-size: 2rem; font-weight: 600; line-height: 1.2; }
.auth-sub { margin-bottom: 26px; color: var(--muted); }
.auth-foot { margin: 22px 0 0; color: var(--muted); font-size: .95rem; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; column-gap: 16px; }
.form-grid .span-2 { grid-column: 1 / -1; }

.success-mark {
  display: grid; place-items: center; width: 48px; height: 48px; margin-bottom: 18px;
  border: 1px solid rgba(74, 222, 154, .5); border-radius: 50%; background: rgba(74, 222, 154, .1); color: var(--ok);
}
.success-mark svg { width: 24px; height: 24px; }

/* ==========================================================================
   Responsive and accessibility
   ========================================================================== */
@media (max-width: 960px) {
  .hero { grid-template-columns: 1fr; gap: 40px; padding-bottom: 64px; }
  .hero-art { max-width: 420px; margin-inline: auto; }
  .reports { grid-template-columns: 1fr; gap: 40px; }
  .workspace { grid-template-columns: 1fr; }
  .auth { grid-template-columns: 1fr; }
  .auth-aside { display: none; }
  .auth-mobile-brand { display: block; }
}
@media (max-width: 640px) {
  .container { width: min(1120px, 100% - 32px); }
  .site-links a:not(.btn) { display: none; }
  .form-grid { grid-template-columns: 1fr; }
  .user-name, .role-tag { display: none; }
  .ledger-item { padding: 16px 18px; }
  .panel { padding: 18px; }
  .dist-row { grid-template-columns: minmax(90px, 120px) 1fr 52px; gap: 10px; }
  .modal-split { grid-template-columns: 1fr; }
  .readout { position: static; width: 100%; margin-top: 14px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
