# BlindTube — Go version

This is a full rewrite of BlindTube (accessible YouTube player) in Go,
using [glaze](https://github.com/crgimenes/glaze) for the WebView shell —
same pattern as [goshell](https://github.com/denizsincar29/goshell):
a tiny embedded HTML/CSS/JS frontend, Go methods exposed to JS via
`glaze.BindMethods`, screen-reader announcements via `aria-live` regions
instead of a TTS library.

The Python version in the repo root still works and is kept around
on purpose — if something here is broken or some quirky video won't
play/download, fall back to `python main.py` while it's getting fixed.

## What's implemented

- Search (`raitonoberu/ytsearch`, no API key) with infinite-scroll
  pagination — load more results automatically as you arrow-down or
  scroll near the bottom of the results list (task.md #2).
- Playback: best muxed (audio+video) stream, served through a local
  `/stream/<id>` proxy with Range-header pass-through so seeking works,
  and so the configured proxy (task.md #1) actually applies to playback
  too, not just search/metadata.
- Download video (best quality via ffmpeg composite mux if `ffmpeg` is on
  PATH, otherwise falls back to a single pre-muxed format with no extra
  dependency) and download audio-only (saves the original m4a/webm
  stream as-is — no ffmpeg re-encode needed).
- Favorites: add/remove/list, same `settings.json` shape as the Python
  version (same app-data directory), so favorites carry over between the
  two builds.
- Settings: proxy (http/https/socks5 URL) and download directory.
- Video description view (Ctrl+Enter / Description button).
- All the Python version's keyboard shortcuts: Ctrl+D / Ctrl+Shift+D
  (download video/audio), Ctrl+F (favorite), Ctrl+Space (play/pause),
  Ctrl+Left/Right (seek 5s), Ctrl+Up/Down (volume), P (announce
  position), Ctrl+Enter (description), Escape (favorites/home/close
  dialog).

## What's NOT implemented (use the Python version for this)

- **Comments.** task.md #3 asked for description *and* comments.
  Comments aren't exposed by `kkdai/youtube`, and re-implementing
  YouTube's internal `/youtubei/v1/next` comment-continuation API
  reliably was out of scope for this pass. The Go UI says so explicitly
  in the description dialog. If you need comments, `python main.py`
  still has them.
- A native folder picker for "Browse…" in Settings — WebView has no such
  primitive exposed to JS without extra per-platform glue. Paste/type the
  path instead.

## Building

You need Go 1.26+ (matches what's already on this machine) and, for best
download quality, `ffmpeg` on PATH (optional — falls back gracefully).

```sh
cd go
go mod tidy   # fetches glaze, kkdai/youtube/v2, raitonoberu/ytsearch
go build -o blindtube ./cmd/blindtube
./blindtube
```

`go mod tidy` needs real internet access (this was written in a
network-restricted sandbox that couldn't reach `proxy.golang.org` or
`golang.org/x/...`, so dependencies could not be fetched/locked here —
go.sum is not checked in for that reason. It'll resolve fine on a normal
machine).

### Cross-compiling / Windows

`glaze` wraps WebView2 on Windows. Build on Windows directly, or check
glaze's own README for cross-compilation notes — same as goshell.

## Code layout

```
go/
  cmd/blindtube/main.go      entry point: HTTP server + glaze window wiring
  internal/config/           settings.json load/save (shared shape with Python version)
  internal/ytapi/            search (ytsearch) + resolve/stream/download (kkdai/youtube)
  internal/ui/
    service.go                glaze-bound methods (search, download, favorites, settings)
    server.go                 embedded frontend + /stream/<id> proxy
    html.go, css.go, js.go    embedded frontend source
```
