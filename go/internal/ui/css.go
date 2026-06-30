package ui

const appCSS = `
:root {
  color-scheme: dark light;
  --bg: #14161a;
  --fg: #f0f0f0;
  --accent: #7aa2ff;
  --border: #3a3d44;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  font-family: system-ui, sans-serif;
  background: var(--bg);
  color: var(--fg);
}

.visually-hidden {
  position: absolute;
  width: 1px; height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}

.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  background: var(--accent);
  color: #000;
  padding: 8px 12px;
  z-index: 10;
}
.skip-link:focus { left: 8px; top: 8px; }

.app-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.app-header h1 { margin: 0 0 8px; font-size: 1.3rem; }

.menubar { display: flex; flex-wrap: wrap; gap: 6px; }
.menubar button {
  background: #20232a;
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 6px 10px;
  cursor: pointer;
}
.menubar button:hover, .menubar button:focus { border-color: var(--accent); }

main { padding: 16px; max-width: 900px; margin: 0 auto; }

#search-form { display: flex; gap: 8px; margin-bottom: 16px; }
#search-field { flex: 1; padding: 8px; background: #20232a; color: var(--fg); border: 1px solid var(--border); border-radius: 4px; }
#search-form button { padding: 8px 14px; }

#results-list {
  list-style: none;
  margin: 0 0 16px;
  padding: 0;
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: 4px;
}
#results-list li {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}
#results-list li:last-child { border-bottom: none; }
#results-list li[aria-selected="true"] {
  background: #232742;
  outline: 2px solid var(--accent);
}

.player-wrap { margin-top: 12px; }
#video-player { width: 100%; max-height: 480px; background: #000; }
#now-playing { font-weight: bold; }

.dialog-screen {
  background: #1b1e24;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 16px;
  margin-top: 16px;
}

#info-description {
  width: 100%;
  min-height: 240px;
  background: #20232a;
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 8px;
}

.comments-note { font-style: italic; opacity: 0.85; }

.context-menu {
  position: fixed;
  z-index: 1000;
  list-style: none;
  margin: 0;
  padding: 4px 0;
  background: #23262e;
  border: 1px solid var(--accent);
  border-radius: 4px;
  min-width: 220px;
  box-shadow: 0 4px 16px #0008;
}
.context-menu li {
  padding: 8px 16px;
  cursor: pointer;
}
.context-menu li:hover,
.context-menu li:focus {
  background: #2d3250;
  outline: none;
}

.info-meta { opacity: 0.8; margin: 0 0 8px; }
.dir-row { display: flex; gap: 6px; }
.dir-row input { flex: 1; }

fieldset {
  border: 1px solid var(--border);
  border-radius: 4px;
  margin-bottom: 12px;
}
label { display: block; margin: 6px 0 2px; }
input[type="text"] {
  width: 100%;
  padding: 6px;
  background: #20232a;
  color: var(--fg);
  border: 1px solid var(--border);
  border-radius: 4px;
}

button { font: inherit; }
`
