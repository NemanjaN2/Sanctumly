/* ═══════════════════════════════════════════
   Sanctumly — Aurora Indigo
   Depth, glow, and quiet precision.
   ═══════════════════════════════════════════ */

:root {
  /* Surfaces — near-black with a faint cool cast, layered for depth */
  --bg: #07070a;
  --bg-raised: #0c0c11;
  --bg-surface: #121219;
  --bg-hover: #1a1a23;
  --bg-elevated: #1e1e28;

  /* Accent system — periwinkle anchor + teal counter-note */
  --accent: #8b8bf5;
  --accent-bright: #a5a5ff;
  --accent-deep: #6e6ee0;
  --accent-dim: rgba(139, 139, 245, 0.12);
  --accent-faint: rgba(139, 139, 245, 0.06);
  --accent-text: #b4b4ff;
  --accent-2: #5eead8;
  --accent-2-dim: rgba(94, 234, 216, 0.12);

  /* Glow */
  --glow-accent: 0 0 24px rgba(139, 139, 245, 0.35);
  --glow-soft: 0 0 0 1px rgba(139, 139, 245, 0.15), 0 4px 24px rgba(139, 139, 245, 0.08);

  /* Text */
  --text-1: #ecedf2;
  --text-2: #9a9aa6;
  --text-3: #56565f;

  /* Borders — slightly cool, layered */
  --border: rgba(255, 255, 255, 0.07);
  --border-soft: rgba(255, 255, 255, 0.04);
  --border-focus: rgba(139, 139, 245, 0.5);

  /* Status */
  --red: #ff5a4f;
  --green: #5eead8;
  --gold: #ffd60a;

  /* Shadows — real depth */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 8px 28px rgba(0, 0, 0, 0.45);
  --shadow-lg: 0 20px 60px rgba(0, 0, 0, 0.6);

  --radius-sm: 7px;
  --radius-md: 11px;
  --radius-lg: 18px;

  --ease: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}

*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

html, body, #root {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', 'Helvetica Neue', sans-serif;
  background: var(--bg);
  color: var(--text-1);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  letter-spacing: -0.011em;
}

/* Ambient atmosphere — a faint aurora behind everything */
body::before {
  content: '';
  position: fixed;
  top: -20%;
  left: 50%;
  transform: translateX(-50%);
  width: 900px;
  height: 600px;
  background: radial-gradient(ellipse at center, rgba(139, 139, 245, 0.08) 0%, transparent 65%);
  pointer-events: none;
  z-index: 0;
}

body.no-scroll { overflow: hidden; }

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--text-3); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-2); }
* { scrollbar-width: thin; scrollbar-color: var(--text-3) transparent; }

a { color: var(--accent-text); text-decoration: none; }
a:hover { text-decoration: underline; }

.gold { color: var(--gold) !important; }

/* ── Layout ── */
.app-shell { display: flex; height: 100vh; height: 100dvh; overflow: hidden; position: relative; z-index: 1; }
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.66); backdrop-filter: blur(2px); z-index: 900; animation: fadeIn 0.2s ease; }
.main-col { flex: 1; display: flex; flex-direction: column; min-width: 0; }

/* ── Sidebar ── */
.sidebar {
  position: fixed; left: -100%; top: 0; bottom: 0; width: 288px; max-width: 84vw;
  background: var(--bg-raised);
  border-right: 1px solid var(--border);
  z-index: 1000; transition: left 0.3s var(--ease-out);
  display: flex; flex-direction: column;
  padding-top: env(safe-area-inset-top);
  box-shadow: var(--shadow-lg);
}
.sidebar.open { left: 0; }

.sb-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 20px; border-bottom: 1px solid var(--border);
}
.sb-brand { font-size: 15px; font-weight: 650; letter-spacing: -0.03em; }
.sb-close { background: none; border: none; color: var(--text-3); font-size: 16px; cursor: pointer; padding: 4px; transition: color 0.15s; }
.sb-close:hover { color: var(--text-1); }

.sb-scroll { flex: 1; overflow-y: auto; padding: 16px 14px 24px; }

.sb-user-card {
  display: flex; align-items: center; gap: 11px;
  padding: 11px 12px; background: var(--bg-surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius-md);
  margin-bottom: 22px;
}
.sb-avatar {
  width: 34px; height: 34px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--accent-deep));
  color: white; display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 650; flex-shrink: 0;
  box-shadow: var(--glow-accent);
}
.sb-username { font-size: 13px; font-weight: 550; }
.sb-creator-tag {
  font-size: 10px; font-weight: 650; color: var(--gold); margin-top: 1px;
  letter-spacing: 0.05em; text-transform: uppercase;
}

.sb-group { margin-bottom: 22px; }
.sb-group-label { font-size: 10px; font-weight: 650; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); margin-bottom: 9px; padding-left: 4px; }
.sb-group-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 9px; }

.sb-agent {
  display: flex; align-items: center; gap: 9px; width: 100%;
  padding: 9px 11px; background: none; border: 1px solid transparent; border-radius: var(--radius-sm);
  color: var(--text-2); font-size: 13px; cursor: pointer; transition: all 0.16s var(--ease);
  text-align: left; margin-bottom: 2px;
}
.sb-agent:hover { background: var(--bg-hover); color: var(--text-1); }
.sb-agent.active {
  background: var(--accent-dim); color: var(--accent-bright); font-weight: 550;
  border-color: rgba(139,139,245,0.2);
}
.sb-agent-icon { font-size: 14px; width: 20px; text-align: center; }
.sb-agent-check { margin-left: auto; font-size: 12px; }

.sb-new {
  font-size: 11px; font-weight: 650; color: var(--accent-bright); background: var(--accent-dim);
  border: 1px solid rgba(139,139,245,0.2); border-radius: var(--radius-sm); padding: 4px 9px; cursor: pointer;
  transition: all 0.15s;
}
.sb-new:hover { background: rgba(139,139,245,0.22); }

.sb-convos { max-height: 260px; overflow-y: auto; }
.sb-convo {
  display: flex; align-items: center; justify-content: space-between; width: 100%;
  padding: 9px 11px; background: none; border: none; border-radius: var(--radius-sm);
  cursor: pointer; transition: all 0.14s var(--ease); text-align: left; margin-bottom: 1px;
}
.sb-convo:hover { background: var(--bg-hover); }
.sb-convo.active { background: var(--accent-dim); }
.sb-convo-t { font-size: 13px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.sb-convo.active .sb-convo-t { color: var(--text-1); font-weight: 550; }
.sb-convo-d { font-size: 11px; color: var(--text-3); flex-shrink: 0; margin-left: 8px; }
.sb-muted { padding: 12px 11px; font-size: 12px; color: var(--text-3); }

.sb-bottom-links { border-top: 1px solid var(--border); padding-top: 16px; margin-top: auto; }
.sb-link {
  display: block; width: 100%; text-align: left; padding: 9px 11px;
  background: none; border: none; border-radius: var(--radius-sm);
  color: var(--text-2); font-size: 13px; cursor: pointer; text-decoration: none;
  transition: all 0.14s var(--ease); margin-bottom: 1px;
}
.sb-link:hover { background: var(--bg-hover); color: var(--text-1); text-decoration: none; }
.sb-link.danger { color: var(--red); }
.sb-link.danger:hover { background: rgba(255,90,79,0.1); }

/* ── Header ── */
.top-bar {
  padding: 13px 20px; border-bottom: 1px solid var(--border);
  background: rgba(7,7,10,0.72); backdrop-filter: blur(20px) saturate(140%);
  flex-shrink: 0; position: relative; z-index: 10;
}
.top-bar, .top-left, .top-right { display: flex; align-items: center; }
.top-left { gap: 12px; flex: 1; }
.top-right { gap: 7px; }

.menu-btn {
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-sm);
  color: var(--text-2); width: 35px; height: 35px; cursor: pointer;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  transition: all 0.16s var(--ease);
}
.menu-btn:hover { border-color: var(--border-focus); color: var(--text-1); background: var(--bg-hover); }

.top-title { font-size: 15px; font-weight: 650; letter-spacing: -0.03em; }
.top-mode { font-size: 12px; color: var(--text-3); padding: 2px 8px; background: var(--bg-surface); border-radius: 20px; border: 1px solid var(--border-soft); }

.top-pill {
  padding: 6px 12px; background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: 20px; color: var(--text-2); font-size: 12px; font-weight: 650;
  cursor: pointer; transition: all 0.16s var(--ease);
}
.top-pill:hover { border-color: var(--border-focus); color: var(--text-1); }
.top-pill.voice {
  background: linear-gradient(135deg, var(--accent), var(--accent-deep)); border-color: transparent; color: white;
  box-shadow: var(--glow-accent);
}
.top-pill.voice:hover { box-shadow: 0 0 32px rgba(139,139,245,0.5); transform: translateY(-1px); }

/* ── Chat area ── */
.chat-area { flex: 1; overflow-y: auto; }
.chat-inner { max-width: 760px; margin: 0 auto; padding: 36px 24px; }

.notif {
  padding: 11px 15px; border-radius: var(--radius-md); font-size: 13px;
  margin-bottom: 16px; animation: slideDown 0.25s var(--ease-out);
}
.notif.error { background: rgba(255,90,79,0.1); color: #ff9a90; border: 1px solid rgba(255,90,79,0.25); }
.notif.ok { background: var(--accent-2-dim); color: var(--accent-2); border: 1px solid rgba(94,234,216,0.25); }

/* ── Empty state ── */
.empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 62vh; text-align: center;
}
.empty-logo {
  width: 68px; height: 68px; object-fit: contain; margin-bottom: 26px; border-radius: 16px;
  box-shadow: var(--glow-soft);
  animation: floatLogo 4s ease-in-out infinite;
}
.empty-h { font-size: 25px; font-weight: 680; letter-spacing: -0.035em; margin-bottom: 7px; }
.empty-p { font-size: 14px; color: var(--text-2); margin-bottom: 34px; }

.suggestion-row {
  display: flex; gap: 9px; overflow-x: auto; max-width: 100%; padding-bottom: 4px;
  -webkit-overflow-scrolling: touch;
}
.suggestion {
  flex-shrink: 0; padding: 15px 18px; background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-md); cursor: pointer; text-align: left;
  transition: all 0.2s var(--ease-out); min-width: 144px;
}
.suggestion:hover {
  border-color: var(--border-focus); background: var(--bg-hover);
  transform: translateY(-2px); box-shadow: var(--glow-soft);
}
.suggestion-label { display: block; font-size: 14px; font-weight: 550; color: var(--text-1); margin-bottom: 3px; }
.suggestion-sub { display: block; font-size: 12px; color: var(--text-3); }

/* ── Messages ── */
.msg-stack { display: flex; flex-direction: column; gap: 26px; }

.msg { max-width: 100%; animation: msgIn 0.28s var(--ease-out); }
.msg.user { display: flex; justify-content: flex-end; }
.msg.user .msg-body {
  background: linear-gradient(135deg, rgba(139,139,245,0.16), rgba(110,110,224,0.12));
  border: 1px solid rgba(139,139,245,0.18);
  color: var(--text-1);
  padding: 11px 16px; border-radius: 18px 18px 5px 18px;
  max-width: 75%; font-size: 15px; line-height: 1.55; white-space: pre-wrap;
  box-shadow: var(--shadow-sm);
}
.msg.assistant { padding-right: 40px; }
.msg-preview { max-width: 200px; border-radius: var(--radius-md); margin-bottom: 8px; border: 1px solid var(--border); }

/* Markdown in assistant messages */
.md { font-size: 15px; line-height: 1.7; color: rgba(236,237,242,0.9); }
.md p { margin-bottom: 14px; }
.md p:last-child { margin-bottom: 0; }
.md h1,.md h2,.md h3 { color: var(--text-1); margin-top: 22px; margin-bottom: 9px; font-weight: 650; letter-spacing: -0.02em; }
.md h1 { font-size: 20px; } .md h2 { font-size: 17px; } .md h3 { font-size: 15px; }
.md ul,.md ol { margin-left: 20px; margin-bottom: 14px; }
.md li { margin-bottom: 5px; }
.md strong { color: var(--text-1); font-weight: 650; }
.md code {
  background: var(--accent-faint); padding: 1.5px 6px; border-radius: 5px;
  font-family: 'SF Mono','Menlo','Consolas',monospace; font-size: 0.87em;
  color: var(--accent-text); border: 1px solid var(--border-soft);
}
.md pre {
  background: var(--bg-surface); padding: 15px 17px; border-radius: var(--radius-md);
  overflow-x: auto; margin-bottom: 14px; border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
}
.md pre code { background: none; padding: 0; color: var(--text-1); border: none; font-size: 13px; }
.md blockquote { border-left: 2px solid var(--accent); padding-left: 14px; color: var(--text-2); margin: 14px 0; font-style: italic; }
.md a { color: var(--accent-text); text-decoration: underline; text-underline-offset: 2px; }
.md hr { border: none; border-top: 1px solid var(--border); margin: 22px 0; }
.md table { width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 13px; }
.md th,.md td { border: 1px solid var(--border); padding: 9px 11px; text-align: left; }
.md th { background: var(--bg-surface); font-weight: 650; }

/* Message toolbar */
.msg-toolbar { display: flex; gap: 3px; margin-top: 9px; animation: fadeIn 0.18s ease; }
.msg-toolbar button {
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-sm);
  color: var(--text-3); font-size: 12px; padding: 4px 11px; cursor: pointer;
  transition: all 0.14s var(--ease);
}
.msg-toolbar button:hover { border-color: var(--border-focus); color: var(--text-1); }
.msg-toolbar button.active { border-color: var(--accent); color: var(--accent-bright); background: var(--accent-dim); }

/* Thinking */
.thinking { display: flex; align-items: center; gap: 7px; color: var(--text-3); font-size: 14px; }
.dots { display: inline-flex; gap: 3px; }
.dots i {
  width: 5px; height: 5px; background: var(--accent); border-radius: 50%; display: block;
  animation: blink 1.2s infinite ease-in-out; box-shadow: 0 0 6px rgba(139,139,245,0.5);
}
.dots i:nth-child(1) { animation-delay: -0.32s; }
.dots i:nth-child(2) { animation-delay: -0.16s; }

/* ── Input dock ── */
.input-dock {
  border-top: 1px solid var(--border);
  background: rgba(7,7,10,0.8); backdrop-filter: blur(20px) saturate(140%);
  flex-shrink: 0;
}
.input-dock-inner { max-width: 760px; margin: 0 auto; padding: 14px 24px 8px; }

.prog { height: 2px; background: var(--bg-surface); border-radius: 1px; margin-bottom: 10px; overflow: hidden; }
.prog-bar { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent-2)); border-radius: 1px; transition: width 0.3s; }

.img-preview {
  display: flex; align-items: center; gap: 10px; padding: 9px 12px;
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: 10px;
}
.img-preview img { width: 44px; height: 44px; border-radius: var(--radius-sm); object-fit: cover; }
.img-preview-text { flex: 1; font-size: 12px; color: var(--text-2); }
.img-preview-text strong { display: block; color: var(--text-1); font-size: 13px; font-weight: 550; }
.img-preview-x { background: none; border: none; color: var(--text-3); cursor: pointer; font-size: 16px; padding: 4px; transition: color 0.15s; }
.img-preview-x:hover { color: var(--text-1); }

.file-count { font-size: 12px; color: var(--text-3); margin-bottom: 8px; }

.input-bar { display: flex; align-items: flex-end; gap: 7px; }

.ib-icon {
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-sm);
  width: 37px; height: 37px; color: var(--text-3); cursor: pointer;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  transition: all 0.16s var(--ease);
}
.ib-icon:hover { border-color: var(--border-focus); color: var(--text-1); background: var(--bg-hover); }
.ib-icon:disabled { opacity: 0.3; cursor: not-allowed; }
.ib-icon.rec { border-color: var(--red); color: var(--red); animation: pulse 1s infinite; }

.ib-text {
  flex: 1; background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: 10px 15px; color: var(--text-1);
  font-size: 14px; font-family: inherit; resize: none; line-height: 1.45;
  min-height: 39px; max-height: 200px; transition: all 0.18s var(--ease);
}
.ib-text:focus { outline: none; border-color: var(--border-focus); box-shadow: 0 0 0 3px var(--accent-faint); }
.ib-text::placeholder { color: var(--text-3); }
.ib-text:disabled { opacity: 0.5; }

.ib-send {
  width: 37px; height: 37px; border-radius: 50%;
  background: linear-gradient(135deg, var(--accent), var(--accent-deep));
  border: none; color: white; cursor: pointer; display: flex; align-items: center;
  justify-content: center; flex-shrink: 0; transition: all 0.16s var(--ease);
  box-shadow: var(--glow-accent);
}
.ib-send:hover { transform: translateY(-1px) scale(1.04); box-shadow: 0 0 30px rgba(139,139,245,0.5); }
.ib-send:disabled { opacity: 0.3; cursor: not-allowed; box-shadow: none; }

.fine-print { text-align: center; font-size: 11px; color: var(--text-3); margin-top: 9px; opacity: 0.6; }
.abs-bottom { position: absolute; bottom: 20px; left: 0; right: 0; }

/* ── Voice overlay ── */
.voice-full {
  position: fixed; inset: 0; background: var(--bg); z-index: 2000;
  display: flex; flex-direction: column; align-items: center;
}
.voice-full::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(ellipse 600px 400px at center 45%, rgba(139,139,245,0.1), transparent 70%);
  pointer-events: none;
}
.voice-bar { display: flex; justify-content: space-between; align-items: center; width: 100%; padding: 20px 24px; position: relative; z-index: 1; }
.voice-lang {
  background: var(--bg-surface); border: 1px solid var(--border); border-radius: 20px;
  padding: 7px 16px; color: var(--text-1); font-size: 13px; font-weight: 650; cursor: pointer;
  transition: all 0.15s;
}
.voice-lang:hover { border-color: var(--border-focus); }
.voice-x { background: none; border: none; color: var(--text-2); font-size: 22px; cursor: pointer; transition: color 0.15s; }
.voice-x:hover { color: var(--text-1); }
.voice-mid { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 28px; position: relative; z-index: 1; }

.voice-orb {
  width: 184px; height: 184px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.4s var(--ease-out); cursor: pointer; position: relative;
}
.voice-orb::after {
  content: ''; position: absolute; inset: -8px; border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.06);
}
.voice-orb.idle { background: linear-gradient(135deg, var(--accent), var(--accent-deep)); box-shadow: 0 0 60px rgba(139,139,245,0.35); }
.voice-orb.listening { background: linear-gradient(135deg, var(--red), #d63a30); box-shadow: 0 0 70px rgba(255,90,79,0.4); animation: pulse 1.5s infinite; }
.voice-orb.thinking { background: linear-gradient(135deg, var(--gold), #e0b800); box-shadow: 0 0 70px rgba(255,214,10,0.3); animation: pulse 0.8s infinite; }
.voice-orb.speaking { background: linear-gradient(135deg, var(--accent-2), #3dd6c0); box-shadow: 0 0 70px rgba(94,234,216,0.35); animation: pulse 1s infinite; }

.voice-state { font-size: 23px; font-weight: 650; color: var(--text-1); letter-spacing: -0.02em; }
.voice-hint { font-size: 14px; color: var(--text-3); }

/* ── Modal ── */
.modal-bg { position: fixed; inset: 0; background: rgba(0,0,0,0.72); backdrop-filter: blur(4px); z-index: 2000; display: flex; align-items: center; justify-content: center; padding: 16px; animation: fadeIn 0.2s ease; }
.modal-box { background: var(--bg-raised); border: 1px solid var(--border); border-radius: var(--radius-lg); max-width: 400px; width: 100%; overflow: hidden; box-shadow: var(--shadow-lg); animation: modalIn 0.3s var(--ease-out); }
.modal-top {
  display: flex; align-items: center; justify-content: space-between;
  padding: 17px 20px; border-bottom: 1px solid var(--border);
  font-size: 15px; font-weight: 650;
}
.modal-top button { background: none; border: none; color: var(--text-3); font-size: 18px; cursor: pointer; transition: color 0.15s; }
.modal-top button:hover { color: var(--text-1); }
.modal-content { padding: 16px 20px; }

.dl-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; background: var(--bg-surface); border: 1px solid var(--border-soft); border-radius: var(--radius-md);
  text-decoration: none; margin-bottom: 8px; transition: all 0.16s var(--ease);
}
.dl-item:hover { background: var(--bg-hover); text-decoration: none; border-color: var(--border-focus); transform: translateX(2px); }
.dl-name { font-size: 14px; font-weight: 550; color: var(--text-1); }
.dl-sub { font-size: 12px; color: var(--text-3); margin-top: 1px; }
.dl-arrow { color: var(--text-3); font-size: 16px; }
.dl-note { margin-top: 12px; font-size: 12px; color: var(--text-3); text-align: center; }

/* ── PWA ── */
.pwa-bar {
  position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%); z-index: 1000;
  display: flex; align-items: center; gap: 12px; padding: 11px 16px;
  background: linear-gradient(135deg, var(--accent), var(--accent-deep)); border-radius: var(--radius-md);
  box-shadow: var(--shadow-md), var(--glow-accent); font-size: 13px; color: white;
  animation: slideUp 0.4s var(--ease-out);
}
.pwa-go { background: white; color: var(--accent-deep); border: none; border-radius: var(--radius-sm); padding: 6px 13px; font-size: 13px; font-weight: 650; cursor: pointer; }
.pwa-x { background: none; border: none; color: rgba(255,255,255,0.7); cursor: pointer; font-size: 16px; }

/* ── Animations ── */
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes slideDown { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
@keyframes slideUp { from { opacity: 0; transform: translate(-50%, 12px); } to { opacity: 1; transform: translate(-50%, 0); } }
@keyframes msgIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
@keyframes modalIn { from { opacity: 0; transform: scale(0.96) translateY(8px); } to { opacity: 1; transform: scale(1) translateY(0); } }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.65; } }
@keyframes blink { 0%,80%,100% { transform: scale(0.8); opacity: 0.3; } 40% { transform: scale(1); opacity: 1; } }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes floatLogo { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
  .empty-logo { animation: none; }
}

/* ══════════════════════════════
   LOGIN PAGE
   ══════════════════════════════ */

.login-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: var(--bg); padding: 24px; position: relative; z-index: 1;
}
.login-card {
  width: 100%; max-width: 384px; padding: 42px 34px;
  background: var(--bg-raised); border: 1px solid var(--border); border-radius: var(--radius-lg);
  text-align: center; box-shadow: var(--shadow-lg), var(--glow-soft);
  position: relative;
}
.login-logo {
  width: 60px; height: 60px; object-fit: contain; margin-bottom: 22px; border-radius: 14px;
  box-shadow: var(--glow-soft);
}
.login-title { font-size: 24px; font-weight: 680; letter-spacing: -0.035em; margin-bottom: 5px; color: var(--text-1); }
.login-sub { font-size: 13px; color: var(--text-3); margin-bottom: 30px; }

.login-toggle { display: flex; gap: 4px; margin-bottom: 24px; background: var(--bg-surface); border-radius: var(--radius-md); padding: 4px; border: 1px solid var(--border-soft); }
.login-tab {
  flex: 1; padding: 9px; background: none; border: none; border-radius: 8px;
  color: var(--text-3); font-size: 13px; font-weight: 650; cursor: pointer; transition: all 0.16s var(--ease);
}
.login-tab.active { background: linear-gradient(135deg, var(--accent), var(--accent-deep)); color: white; box-shadow: var(--glow-accent); }
.login-tab:not(.active):hover { color: var(--text-2); }

.login-form { display: flex; flex-direction: column; gap: 16px; text-align: left; }
.login-field { display: flex; flex-direction: column; gap: 7px; }
.login-field label { font-size: 12px; font-weight: 550; color: var(--text-3); text-transform: uppercase; letter-spacing: 0.05em; }
.login-field .ib-text { border-radius: var(--radius-sm); padding: 11px 13px; font-size: 14px; }

.login-submit {
  width: 100%; padding: 12px; background: linear-gradient(135deg, var(--accent), var(--accent-deep)); border: none; border-radius: var(--radius-md);
  color: white; font-size: 14px; font-weight: 650; cursor: pointer; transition: all 0.16s var(--ease); margin-top: 4px;
  box-shadow: var(--glow-accent);
}
.login-submit:hover { transform: translateY(-1px); box-shadow: 0 0 32px rgba(139,139,245,0.5); }
.login-submit:disabled { opacity: 0.4; cursor: not-allowed; box-shadow: none; transform: none; }

/* ══════════════════════════════
   ADMIN PANEL
   ══════════════════════════════ */

.admin-page { min-height: 100vh; background: var(--bg); position: relative; z-index: 1; }

.admin-header { border-bottom: 1px solid var(--border); background: rgba(7,7,10,0.72); backdrop-filter: blur(20px); }
.admin-header-inner {
  max-width: 860px; margin: 0 auto; padding: 15px 24px;
  display: flex; align-items: center; justify-content: space-between;
}
.admin-header-left { display: flex; align-items: center; gap: 16px; }
.admin-back { color: var(--accent-text); font-size: 13px; text-decoration: none; font-weight: 550; }
.admin-back:hover { text-decoration: underline; }
.admin-title { font-size: 16px; font-weight: 650; color: var(--text-1); }

.admin-content { max-width: 860px; margin: 0 auto; padding: 30px 24px; }

.admin-card {
  background: var(--bg-raised); border: 1px solid var(--border); border-radius: var(--radius-lg);
  padding: 26px; margin-bottom: 24px; box-shadow: var(--shadow-sm);
}
.admin-card-title { font-size: 15px; font-weight: 650; color: var(--text-1); margin-bottom: 16px; }

.admin-textarea {
  width: 100%; background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: 13px 15px; color: var(--text-1);
  font-family: 'SF Mono','Menlo','Consolas',monospace; font-size: 13px; resize: vertical;
  line-height: 1.55; transition: all 0.18s var(--ease); min-height: 180px;
}
.admin-textarea:focus { outline: none; border-color: var(--border-focus); box-shadow: 0 0 0 3px var(--accent-faint); }
.admin-textarea::placeholder { color: var(--text-3); }

.admin-hint { display: block; font-size: 12px; color: var(--text-3); margin-top: 8px; }

.admin-save {
  padding: 9px 22px; background: linear-gradient(135deg, var(--accent), var(--accent-deep)); border: none; border-radius: var(--radius-sm);
  color: white; font-size: 13px; font-weight: 650; cursor: pointer; margin-top: 12px; transition: all 0.16s var(--ease);
  box-shadow: var(--glow-accent);
}
.admin-save:hover { transform: translateY(-1px); box-shadow: 0 0 28px rgba(139,139,245,0.45); }
.admin-save:disabled { opacity: 0.4; cursor: not-allowed; box-shadow: none; transform: none; }

.admin-info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 24px; }
.admin-info-card {
  background: var(--bg-raised); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 17px;
}
.admin-info-label { font-size: 10px; font-weight: 650; text-transform: uppercase; letter-spacing: 0.1em; color: var(--text-3); margin-bottom: 6px; }
.admin-info-value { font-size: 14px; font-weight: 550; color: var(--text-1); }

.admin-denied { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg); }
.admin-denied-card { text-align: center; padding: 40px; }
.admin-denied-card h1 { font-size: 20px; margin-bottom: 8px; }
.admin-denied-card p { color: var(--text-3); margin-bottom: 20px; font-size: 14px; }

/* ══════════════════════════════
   WELLNESS PAGE
   ══════════════════════════════ */

.wellness-page { min-height: 100vh; background: var(--bg); position: relative; z-index: 1; }

.wellness-header {
  display: flex; align-items: center; gap: 16px;
  padding: 15px 24px; border-bottom: 1px solid var(--border);
  background: rgba(7,7,10,0.72); backdrop-filter: blur(20px);
}

.wellness-content { max-width: 680px; margin: 0 auto; padding: 30px 24px; }

.w-card {
  background: var(--bg-raised); border: 1px solid var(--border); border-radius: var(--radius-lg);
  padding: 26px; margin-bottom: 20px; box-shadow: var(--shadow-sm);
}
.w-card-title { font-size: 15px; font-weight: 650; color: var(--text-1); margin-bottom: 16px; text-align: center; }

.w-moods { display: flex; justify-content: center; gap: 10px; margin-bottom: 12px; }
.w-mood-btn {
  width: 54px; height: 54px; border-radius: 50%; border: 2px solid transparent;
  background: none; cursor: pointer; transition: all 0.2s var(--ease-out); display: flex; align-items: center; justify-content: center;
}
.w-mood-btn:hover { background: rgba(255,255,255,0.04); transform: translateY(-2px); }
.w-mood-btn.active { border-color: var(--mood-color); background: color-mix(in srgb, var(--mood-color) 14%, transparent); transform: scale(1.14); }
.w-mood-emoji { font-size: 27px; }
.w-mood-label { text-align: center; font-size: 14px; font-weight: 550; margin-bottom: 12px; }

.w-note {
  width: 100%; background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: 11px 14px; color: var(--text-1);
  font-size: 13px; font-family: inherit; resize: none; margin-bottom: 12px; transition: all 0.18s var(--ease);
}
.w-note:focus { outline: none; border-color: var(--border-focus); box-shadow: 0 0 0 3px var(--accent-faint); }
.w-note::placeholder { color: var(--text-3); }

.w-checkin-btn {
  width: 100%; padding: 11px; background: linear-gradient(135deg, var(--accent), var(--accent-deep)); border: none;
  border-radius: var(--radius-md); color: white; font-size: 14px; font-weight: 650;
  cursor: pointer; transition: all 0.16s var(--ease); box-shadow: var(--glow-accent);
}
.w-checkin-btn:hover { transform: translateY(-1px); box-shadow: 0 0 28px rgba(139,139,245,0.45); }
.w-checkin-btn:disabled { opacity: 0.4; cursor: not-allowed; box-shadow: none; transform: none; }

.w-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; }
.w-stat {
  background: var(--bg-raised); border: 1px solid var(--border); border-radius: var(--radius-md);
  padding: 15px; text-align: center;
}
.w-stat-val { font-size: 17px; font-weight: 700; color: var(--accent-bright); margin-bottom: 2px; }
.w-stat-label { font-size: 11px; color: var(--text-3); }

.w-range { display: flex; gap: 6px; margin-bottom: 16px; }
.w-range-btn {
  padding: 6px 14px; border: 1px solid var(--border-soft); border-radius: var(--radius-sm);
  font-size: 13px; font-weight: 550; cursor: pointer; transition: all 0.14s var(--ease);
  background: var(--bg-surface); color: var(--text-3);
}
.w-range-btn.active { background: linear-gradient(135deg, var(--accent), var(--accent-deep)); color: white; border-color: transparent; }

.w-empty { text-align: center; padding: 40px 16px; color: var(--text-3); font-size: 13px; }

.w-chart { display: flex; gap: 4px; }
.w-chart-y { display: flex; flex-direction: column; justify-content: space-between; padding-right: 6px; }
.w-chart-y-item { font-size: 11px; line-height: 1; height: 28px; display: flex; align-items: center; }
.w-chart-bars { flex: 1; display: flex; align-items: flex-end; gap: 1px; height: 140px; }
.w-bar-col { flex: 1; height: 100%; display: flex; align-items: flex-end; }
.w-bar { width: 100%; border-radius: 2px 2px 0 0; min-height: 2px; transition: height 0.4s var(--ease-out); }
.w-bar-empty { width: 100%; height: 2px; background: rgba(255,255,255,0.04); border-radius: 1px; }

.w-entries { display: flex; flex-direction: column; }
.w-entry {
  display: flex; align-items: center; gap: 12px;
  padding: 11px 0; border-bottom: 1px solid var(--border);
}
.w-entry:last-child { border-bottom: none; }
.w-entry-emoji { font-size: 22px; flex-shrink: 0; }
.w-entry-info { flex: 1; min-width: 0; }
.w-entry-date { font-size: 13px; font-weight: 550; color: var(--text-1); display: block; }
.w-entry-note { font-size: 12px; color: var(--text-3); display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.w-entry-tag { font-size: 11px; font-weight: 550; padding: 3px 9px; border-radius: 6px; flex-shrink: 0; }

/* ── Responsive ── */
@media (max-width: 768px) {
  .sidebar { width: 84vw; }
  .chat-inner { padding: 22px 16px; }
  .input-dock-inner { padding: 11px 16px 6px; }
  .msg.user .msg-body { max-width: 88%; }
  .suggestion-row { gap: 7px; }
  .suggestion { min-width: 124px; padding: 13px 15px; }
  .top-mode { display: none; }
}

@media (max-width: 480px) {
  .msg.user .msg-body { max-width: 92%; font-size: 14px; padding: 9px 14px; }
  .md { font-size: 14px; }
  .top-bar { padding: 11px 14px; }
  body::before { width: 100%; }
}
