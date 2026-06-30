// Package ytapi wraps two third-party libraries behind one small surface
// that the rest of blindtube-go talks to:
//
//   - github.com/raitonoberu/ytsearch for search (no API key, scrapes
//     YouTube's internal "innertube" search endpoint, supports pagination
//     via a continuation token).
//   - github.com/kkdai/youtube/v2 for resolving a video id/URL into
//     metadata + playable/downloadable stream formats.
//
// Both libraries take a *http.Client, which is how proxy support (Task #1
// in task.md: socks5/http(s), configurable in settings) is threaded
// through: NewClient builds that http.Client once from config.Proxy and
// reuses it everywhere.
package ytapi

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"time"

	"github.com/kkdai/youtube/v2"
	"github.com/kkdai/youtube/v2/downloader"
	"github.com/raitonoberu/ytsearch"

	"github.com/denizsincar29/blindtube/go/internal/config"
)

// Result is one search hit or a resolved single video, shaped for direct
// display in the results list (mirrors TubeWorker._format_info's
// "Title by Channel (h:mm:ss)" string from the Python version, but kept
// structured here since formatting now happens in JS for the UI).
type Result struct {
	ID       string `json:"id"`
	Title    string `json:"title"`
	Channel  string `json:"channel"`
	Duration int    `json:"duration"` // seconds
	URL      string `json:"url"`
}

// VideoInfo is the richer payload used when a video is opened for
// playback or for the description view.
type VideoInfo struct {
	ID          string `json:"id"`
	Title       string `json:"title"`
	Channel     string `json:"channel"`
	Duration    int    `json:"duration"`
	URL         string `json:"url"`
	Description string `json:"description"`
	// StreamPath is a same-origin path (e.g. "/stream/<id>") that the
	// <video> element's src is set to. The Go HTTP server resolves and
	// proxies the real googlevideo URL on demand (see internal/ui/server.go);
	// we never hand a raw googlevideo URL to the browser, since those are
	// short-lived, IP-pinned, and would bypass the configured proxy.
	StreamPath string `json:"streamPath"`
}

var videoIDRe = regexp.MustCompile(`^[a-zA-Z0-9_-]{10,12}$`)

// ExtractVideoID pulls an 11-char id out of a youtube.com/youtu.be URL, or
// returns the input unchanged if it already looks like a bare id.
func ExtractVideoID(input string) (string, error) {
	input = strings.TrimSpace(input)
	if videoIDRe.MatchString(input) {
		return input, nil
	}
	u, err := url.Parse(input)
	if err != nil {
		return "", fmt.Errorf("not a URL or video id: %s", input)
	}
	if id := u.Query().Get("v"); id != "" {
		return id, nil
	}
	// youtu.be/<id> and youtube.com/shorts/<id> / /embed/<id>
	parts := strings.Split(strings.Trim(u.Path, "/"), "/")
	if len(parts) > 0 {
		last := parts[len(parts)-1]
		if videoIDRe.MatchString(last) {
			return last, nil
		}
	}
	return "", fmt.Errorf("could not find a video id in: %s", input)
}

// Client bundles the proxy-aware HTTP client plus an in-flight search
// continuation, mirroring how TubeWorker kept self.ydl_opts +
// self.results around in the Python version.
type Client struct {
	httpClient *http.Client
	yt         youtube.Client

	search      *ytsearch.SearchClient
	searchQuery string
}

// New builds a Client using the given proxy settings (may be a zero value
// for "no proxy"). Call Reconfigure later if the user changes proxy
// settings without restarting the app.
func New(p config.Proxy) *Client {
	c := &Client{}
	c.Reconfigure(p)
	return c
}

// Reconfigure rebuilds the underlying http.Client. Safe to call any time;
// in-flight requests started before the call keep using the old client.
func (c *Client) Reconfigure(p config.Proxy) error {
	transport := &http.Transport{}
	if p.Enabled && p.URL != "" {
		proxyURL, err := url.Parse(p.URL)
		if err != nil {
			return fmt.Errorf("invalid proxy url: %w", err)
		}
		transport.Proxy = http.ProxyURL(proxyURL)
	}
	c.httpClient = &http.Client{Transport: transport, Timeout: 30 * time.Second}
	c.yt = youtube.Client{HTTPClient: c.httpClient}
	return nil
}

// Search starts a brand-new search (equivalent of next_index = 1 in the
// Python version) and returns the first page.
func (c *Client) Search(query string) ([]Result, error) {
	sc := ytsearch.VideoSearch(query)
	sc.HTTPClient = c.httpClient
	c.search = sc
	c.searchQuery = query
	return c.nextPage()
}

// SearchMore continues the current search (the "load 10 more when
// scrolling near the bottom" behavior from task.md #2). Returns an empty
// slice, not an error, once results are exhausted.
func (c *Client) SearchMore() ([]Result, error) {
	if c.search == nil {
		return nil, fmt.Errorf("no active search; call Search first")
	}
	if !c.search.NextExists() {
		return []Result{}, nil
	}
	return c.nextPage()
}

func (c *Client) nextPage() ([]Result, error) {
	page, err := c.search.Next()
	if err != nil {
		return nil, err
	}
	out := make([]Result, 0, len(page.Videos))
	for _, v := range page.Videos {
		out = append(out, Result{
			ID:       v.ID,
			Title:    v.Title,
			Channel:  v.Channel.Title,
			Duration: v.Duration,
			URL:      "https://www.youtube.com/watch?v=" + v.ID,
		})
	}
	return out, nil
}

// GetVideoInfo resolves a URL or bare video id into full metadata. This is
// used both to populate the description window and to prepare playback
// (the StreamPath field tells the frontend where to point the <video>
// element; resolving the actual googlevideo URL happens lazily in
// internal/ui/server.go so a stale resolve doesn't go stale waiting on the
// user to press play).
func (c *Client) GetVideoInfo(urlOrID string) (*VideoInfo, error) {
	id, err := ExtractVideoID(urlOrID)
	if err != nil {
		return nil, err
	}
	v, err := c.yt.GetVideo(id)
	if err != nil {
		return nil, fmt.Errorf("fetching video info: %w", err)
	}
	return &VideoInfo{
		ID:          v.ID,
		Title:       v.Title,
		Channel:     v.Author,
		Duration:    int(v.Duration.Seconds()),
		URL:         "https://www.youtube.com/watch?v=" + v.ID,
		Description: v.Description,
		StreamPath:  "/stream/" + v.ID,
	}, nil
}

// bestPlaybackFormat picks a muxed (audio+video in one file) format
// suitable for direct <video> playback without server-side remuxing.
// Prefers mp4 (best browser/WebView2 compatibility) and higher
// resolution. Falls back to any format with audio if no mp4 muxed stream
// exists (e.g. very new uploads sometimes only expose webm+vp9 muxed).
func bestPlaybackFormat(v *youtube.Video) (*youtube.Format, error) {
	muxed := v.Formats.WithAudioChannels()
	if len(muxed) == 0 {
		return nil, fmt.Errorf("no playable (audio+video) format found for this video")
	}
	sort.Slice(muxed, func(i, j int) bool {
		return muxed[i].Bitrate > muxed[j].Bitrate
	})
	for _, f := range muxed {
		if strings.Contains(f.MimeType, "video/mp4") {
			fc := f
			return &fc, nil
		}
	}
	fc := muxed[0]
	return &fc, nil
}

// bestAudioOnlyFormat picks the highest-bitrate pure-audio format, for
// "Download Audio Track" — no ffmpeg/transcoding needed, we just save the
// raw stream (typically .m4a or .webm/opus) as-is.
func bestAudioOnlyFormat(v *youtube.Video) (*youtube.Format, error) {
	var best *youtube.Format
	for i := range v.Formats {
		f := &v.Formats[i]
		if f.AudioChannels > 0 && f.QualityLabel == "" {
			if best == nil || f.Bitrate > best.Bitrate {
				best = f
			}
		}
	}
	if best == nil {
		// Some clients return no pure-audio formats; fall back to the
		// best muxed format and let the user end up with a small video
		// file rather than failing outright.
		return bestPlaybackFormat(v)
	}
	return best, nil
}

// ResolveStreamURL returns the time-limited googlevideo CDN URL for the
// given video id, used by the /stream/<id> proxy handler in server.go. It
// re-resolves on every call (URLs expire and are IP-pinned to whichever
// client fetched them, which matters when a proxy is configured).
func (c *Client) ResolveStreamURL(id string) (streamURL string, mimeType string, err error) {
	v, err := c.yt.GetVideo(id)
	if err != nil {
		return "", "", fmt.Errorf("fetching video: %w", err)
	}
	f, err := bestPlaybackFormat(v)
	if err != nil {
		return "", "", err
	}
	u, err := c.yt.GetStreamURL(v, f)
	if err != nil {
		return "", "", fmt.Errorf("resolving stream url: %w", err)
	}
	return u, f.MimeType, nil
}

// HTTPDo runs req through the same proxy-aware http.Client used for
// search/resolve, so the /stream/<id> proxy handler in server.go honors
// the configured proxy too (not just search and metadata lookups).
func (c *Client) HTTPDo(req *http.Request) (*http.Response, error) {
	return c.httpClient.Do(req)
}

// DownloadVideo saves the best available video (with audio) to dir. It
// tries a composite (best-video + best-audio, muxed via ffmpeg) download
// first since that gives the highest quality; if ffmpeg isn't on PATH (or
// the composite download otherwise fails), it falls back to a single
// pre-muxed format so the feature still works without ffmpeg installed.
func (c *Client) DownloadVideo(ctx context.Context, urlOrID, dir string) (string, error) {
	id, err := ExtractVideoID(urlOrID)
	if err != nil {
		return "", err
	}
	v, err := c.yt.GetVideo(id)
	if err != nil {
		return "", fmt.Errorf("fetching video: %w", err)
	}

	dl := &downloader.Downloader{Client: c.yt, OutputDir: dir}
	outFile := downloader.SanitizeFilename(v.Title) + ".mp4"

	if hasFFmpeg() {
		if err := dl.DownloadComposite(ctx, outFile, v, "hd1080", "mp4", ""); err == nil {
			return outFile, nil
		}
		// fall through to muxed-only on composite failure (e.g. no
		// formats at that quality, ffmpeg failing on a particular codec)
	}

	f, err := bestPlaybackFormat(v)
	if err != nil {
		return "", err
	}
	if err := dl.Download(ctx, v, f, outFile); err != nil {
		return "", fmt.Errorf("download failed: %w", err)
	}
	return outFile, nil
}

// DownloadAudio saves the best pure-audio stream to dir, unmodified
// (no re-encode to mp3 — that needs ffmpeg postprocessing the Python
// version relied on; saving the original m4a/opus avoids that
// dependency entirely while still giving an audio-only file).
func (c *Client) DownloadAudio(ctx context.Context, urlOrID, dir string) (string, error) {
	id, err := ExtractVideoID(urlOrID)
	if err != nil {
		return "", err
	}
	v, err := c.yt.GetVideo(id)
	if err != nil {
		return "", fmt.Errorf("fetching video: %w", err)
	}
	f, err := bestAudioOnlyFormat(v)
	if err != nil {
		return "", err
	}
	ext := extensionForMime(f.MimeType)
	dl := &downloader.Downloader{Client: c.yt, OutputDir: dir}
	outFile := downloader.SanitizeFilename(v.Title) + ext
	if err := dl.Download(ctx, v, f, outFile); err != nil {
		return "", fmt.Errorf("download failed: %w", err)
	}
	return outFile, nil
}

func extensionForMime(mime string) string {
	switch {
	case strings.Contains(mime, "mp4"):
		return ".m4a"
	case strings.Contains(mime, "webm"):
		return ".webm"
	default:
		return ".audio"
	}
}
