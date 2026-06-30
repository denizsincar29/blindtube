package ui

const indexHTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BlindTube</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>

<a class="skip-link" href="#main-content">Skip to main content</a>

<header class="app-header">
  <h1>BlindTube</h1>
  <nav aria-label="Main menu" class="menubar">
    <button id="nav-home"           type="button">Home (Esc)</button>
    <button id="nav-download-video" type="button">Download Video (Ctrl+D)</button>
    <button id="nav-download-audio" type="button">Download Audio (Ctrl+Shift+D)</button>
    <button id="nav-dl-all-video"   type="button" class="desktop-only">Download All Favorites as Video</button>
    <button id="nav-dl-all-audio"   type="button" class="desktop-only">Download All Favorites as Audio</button>
    <button id="nav-favorite"       type="button" class="desktop-only">Add to Favorites (Ctrl+F)</button>
    <button id="nav-copy-link"      type="button">Copy Link</button>
    <button id="nav-info"           type="button">Description (Ctrl+Enter)</button>
    <button id="nav-settings"       type="button" class="desktop-only">Settings</button>
  </nav>
</header>

<!-- Screen-reader live regions -->
<div id="status-live" role="status" aria-live="polite"    class="visually-hidden"></div>
<div id="alert-live"  role="alert"  aria-live="assertive" class="visually-hidden"></div>

<main id="main-content">

  <!-- ===================== SEARCH + PLAYER ===================== -->
  <section id="screen-player" aria-labelledby="search-heading">
    <h2 id="search-heading" class="visually-hidden">Search and play</h2>

    <form id="search-form" autocomplete="off">
      <label for="search-field">Search or enter URL</label>
      <input id="search-field" type="text" placeholder="Search YouTube or paste a video URL">
      <button type="submit">Search</button>
    </form>

    <h3 id="results-heading">Results</h3>
    <ul id="results-list" role="listbox" aria-labelledby="results-heading" tabindex="0"></ul>

    <div class="player-wrap">
      <video id="video-player" controls preload="metadata"></video>
      <p id="now-playing" role="status" aria-live="polite"></p>
    </div>
  </section>

  <!-- ===================== DESCRIPTION DIALOG ===================== -->
  <section id="screen-info" class="dialog-screen" hidden aria-labelledby="info-heading">
    <h2 id="info-heading">Video Info</h2>
    <p  id="info-channel" class="info-meta"></p>
    <button id="info-close" type="button">Close (Esc)</button>
    <h3>Description</h3>
    <textarea id="info-description" readonly></textarea>
    <p class="comments-note">Comments are not yet implemented — use the Python version (<code>python main.py</code>) if you need comments.</p>
  </section>

  <!-- ===================== SETTINGS DIALOG (desktop only) ===================== -->
  <section id="screen-settings" class="dialog-screen desktop-only" hidden aria-labelledby="settings-heading">
    <h2 id="settings-heading">Settings</h2>
    <button id="settings-close" type="button">Close (Esc)</button>

    <form id="settings-form">
      <fieldset>
        <legend>Proxy</legend>
        <label><input id="proxy-enabled" type="checkbox"> Enable proxy</label>
        <label for="proxy-url">Proxy URL (http://, https://, or socks5://user:pass@host:port)</label>
        <input id="proxy-url" type="text" placeholder="socks5://127.0.0.1:1080">
      </fieldset>

      <fieldset>
        <legend>Downloads</legend>
        <label for="download-dir">Download directory</label>
        <div class="dir-row">
          <input id="download-dir" type="text">
          <button id="browse-download-dir" type="button">Browse…</button>
        </div>
      </fieldset>

      <button type="submit">Save settings</button>
    </form>
  </section>

</main>

<script src="/static/app.js"></script>
</body>
</html>
`
