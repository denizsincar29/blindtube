// Package ui: Service holds app-wide state and exposes it as HTTP JSON
// handlers. Everything that was a glaze Bind method is now a regular
// HTTP handler so the same binary works for the desktop (glaze webview
// pointing at the local server) and the web backend
// (tube.denizsincar.ru, multiple users, real browser).
package ui

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"github.com/denizsincar29/blindtube/go/internal/config"
	"github.com/denizsincar29/blindtube/go/internal/ytapi"
)

// Mode lets the frontend know which settings to show.
type Mode string

const (
	ModeDesktop Mode = "desktop"
	ModeWeb     Mode = "web"
)

// searchSession holds a per-user (or per-desktop-window) search client
// so that "load more" can continue the same continuation stream.
type searchSession struct {
	client    *ytapi.Client
	lastTouch time.Time
}

// Service holds all app state and is also the http.Handler (via its
// ServeHTTP, which just delegates to the mux built in newMux).
type Service struct {
	mu   sync.RWMutex
	cfg  *config.Manager // nil in web mode (no per-user settings file)
	mode Mode

	// shared YouTube client (desktop / web single-user baseline)
	yt *ytapi.Client

	// per-session search clients, keyed by session cookie value.
	// Only the search client inside a session tracks the pagination state.
	sessions   map[string]*searchSession
	sessionsMu sync.Mutex
}

func NewService(cfg *config.Manager, mode Mode) *Service {
	var proxy config.Proxy
	if cfg != nil {
		proxy = cfg.ProxySettings()
	}
	svc := &Service{
		cfg:      cfg,
		mode:     mode,
		yt:       ytapi.New(proxy),
		sessions: make(map[string]*searchSession),
	}
	go svc.reapSessions()
	return svc
}

// reapSessions discards sessions idle for more than 30 minutes.
func (s *Service) reapSessions() {
	for range time.Tick(10 * time.Minute) {
		s.sessionsMu.Lock()
		for id, sess := range s.sessions {
			if time.Since(sess.lastTouch) > 30*time.Minute {
				delete(s.sessions, id)
			}
		}
		s.sessionsMu.Unlock()
	}
}

func newSessionID() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func (s *Service) sessionClient(r *http.Request) (*ytapi.Client, string) {
	var sid string
	if c, err := r.Cookie("bt_session"); err == nil {
		sid = c.Value
	}
	s.sessionsMu.Lock()
	defer s.sessionsMu.Unlock()
	sess, ok := s.sessions[sid]
	if !ok {
		var proxy config.Proxy
		if s.cfg != nil {
			proxy = s.cfg.ProxySettings()
		}
		sid = newSessionID()
		sess = &searchSession{client: ytapi.New(proxy)}
		s.sessions[sid] = sess
	}
	sess.lastTouch = time.Now()
	return sess.client, sid
}

// ---- JSON helpers ----

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

func writeErr(w http.ResponseWriter, code int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

func readJSON(r *http.Request, v any) error {
	return json.NewDecoder(r.Body).Decode(v)
}

// ---- Handler methods (each is /api/<name>) ----

// GET /api/mode
func (s *Service) handleMode(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]string{"mode": string(s.mode)})
}

// POST /api/search   body: {"q":"..."}
func (s *Service) handleSearch(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Q string `json:"q"`
	}
	if err := readJSON(r, &req); err != nil || req.Q == "" {
		writeErr(w, http.StatusBadRequest, "q is required")
		return
	}
	client, sid := s.sessionClient(r)
	results, err := client.Search(req.Q)
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	http.SetCookie(w, &http.Cookie{Name: "bt_session", Value: sid, Path: "/", HttpOnly: true, SameSite: http.SameSiteLaxMode})
	writeJSON(w, results)
}

// POST /api/search/more   (uses bt_session cookie)
func (s *Service) handleSearchMore(w http.ResponseWriter, r *http.Request) {
	client, sid := s.sessionClient(r)
	results, err := client.SearchMore()
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	http.SetCookie(w, &http.Cookie{Name: "bt_session", Value: sid, Path: "/", HttpOnly: true, SameSite: http.SameSiteLaxMode})
	writeJSON(w, results)
}

// GET /api/video?id=<id_or_url>
func (s *Service) handleVideoInfo(w http.ResponseWriter, r *http.Request) {
	idOrURL := r.URL.Query().Get("id")
	if idOrURL == "" {
		writeErr(w, http.StatusBadRequest, "id is required")
		return
	}
	info, err := s.yt.GetVideoInfo(idOrURL)
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, info)
}

// GET /api/download/video?id=<id>
// In web mode: streams bytes back with Content-Disposition: attachment.
// In desktop mode: saves to download dir and returns the path as JSON.
func (s *Service) handleDownloadVideo(w http.ResponseWriter, r *http.Request) {
	idOrURL := r.URL.Query().Get("id")
	if idOrURL == "" {
		writeErr(w, http.StatusBadRequest, "id is required")
		return
	}
	if s.mode == ModeWeb {
		s.streamDownload(w, r, idOrURL, false)
		return
	}
	dir := s.cfg.DownloadDirectory()
	path, err := s.yt.DownloadVideo(context.Background(), idOrURL, dir)
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, map[string]string{"path": path})
}

// GET /api/download/audio?id=<id>
func (s *Service) handleDownloadAudio(w http.ResponseWriter, r *http.Request) {
	idOrURL := r.URL.Query().Get("id")
	if idOrURL == "" {
		writeErr(w, http.StatusBadRequest, "id is required")
		return
	}
	if s.mode == ModeWeb {
		s.streamDownload(w, r, idOrURL, true)
		return
	}
	dir := s.cfg.DownloadDirectory()
	path, err := s.yt.DownloadAudio(context.Background(), idOrURL, dir)
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, map[string]string{"path": path})
}

// streamDownload resolves the best stream URL and proxies it directly to the
// browser as a download (no temp file on the server). This works because
// kkdai/youtube gives us a plain HTTPS URL we can forward.
func (s *Service) streamDownload(w http.ResponseWriter, r *http.Request, idOrURL string, audioOnly bool) {
	id, err := ytapi.ExtractVideoID(idOrURL)
	if err != nil {
		writeErr(w, http.StatusBadRequest, err.Error())
		return
	}
	var streamURL, mimeType, filename string
	if audioOnly {
		streamURL, mimeType, filename, err = s.yt.ResolveAudioURL(id)
	} else {
		streamURL, mimeType, filename, err = s.yt.ResolveVideoURL(id)
	}
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}

	req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, streamURL, nil)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	resp, err := s.yt.HTTPDo(req)
	if err != nil {
		writeErr(w, http.StatusBadGateway, err.Error())
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", mimeType)
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s"`, filename))
	if cl := resp.Header.Get("Content-Length"); cl != "" {
		w.Header().Set("Content-Length", cl)
	}
	w.WriteHeader(resp.StatusCode)
	proxyBody(w, resp)
}

// GET /api/favorites
func (s *Service) handleFavoritesGet(w http.ResponseWriter, r *http.Request) {
	if s.cfg == nil {
		writeJSON(w, []config.Favorite{})
		return
	}
	writeJSON(w, s.cfg.Favorites())
}

// POST /api/favorites   body: {"info":"...","url":"..."}
func (s *Service) handleFavoritesAdd(w http.ResponseWriter, r *http.Request) {
	if s.cfg == nil {
		writeErr(w, http.StatusForbidden, "favorites not available in web mode")
		return
	}
	var req config.Favorite
	if err := readJSON(r, &req); err != nil || req.URL == "" {
		writeErr(w, http.StatusBadRequest, "info and url required")
		return
	}
	added, err := s.cfg.AddFavorite(req)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	writeJSON(w, map[string]bool{"added": added})
}

// DELETE /api/favorites?url=<url>
func (s *Service) handleFavoritesDelete(w http.ResponseWriter, r *http.Request) {
	if s.cfg == nil {
		writeErr(w, http.StatusForbidden, "favorites not available in web mode")
		return
	}
	u := r.URL.Query().Get("url")
	if u == "" {
		writeErr(w, http.StatusBadRequest, "url is required")
		return
	}
	if err := s.cfg.RemoveFavorite(u); err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// GET /api/settings   (desktop only)
func (s *Service) handleSettingsGet(w http.ResponseWriter, r *http.Request) {
	if s.cfg == nil {
		writeErr(w, http.StatusForbidden, "settings not available in web mode")
		return
	}
	writeJSON(w, s.cfg.Snapshot())
}

// POST /api/settings/proxy   body: config.Proxy
func (s *Service) handleSettingsProxy(w http.ResponseWriter, r *http.Request) {
	if s.cfg == nil {
		writeErr(w, http.StatusForbidden, "proxy settings not available in web mode")
		return
	}
	var p config.Proxy
	if err := readJSON(r, &p); err != nil {
		writeErr(w, http.StatusBadRequest, err.Error())
		return
	}
	if err := s.cfg.SetProxy(p); err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	// Reconfigure all session clients and the shared client.
	s.mu.Lock()
	_ = s.yt.Reconfigure(p)
	s.mu.Unlock()
	s.sessionsMu.Lock()
	for _, sess := range s.sessions {
		_ = sess.client.Reconfigure(p)
	}
	s.sessionsMu.Unlock()
	w.WriteHeader(http.StatusNoContent)
}

// POST /api/settings/download-dir   body: {"dir":"..."}
func (s *Service) handleSettingsDownloadDir(w http.ResponseWriter, r *http.Request) {
	if s.cfg == nil {
		writeErr(w, http.StatusForbidden, "not available in web mode")
		return
	}
	var req struct {
		Dir string `json:"dir"`
	}
	if err := readJSON(r, &req); err != nil || req.Dir == "" {
		writeErr(w, http.StatusBadRequest, "dir is required")
		return
	}
	if err := s.cfg.SetDownloadDirectory(req.Dir); err != nil {
		writeErr(w, http.StatusInternalServerError, err.Error())
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

// DownloadAllFavorites is called by the desktop client only — it queues
// downloads to the local dir. In web mode this is not surfaced in the UI.
// POST /api/favorites/download-all   body: {"audio_only": bool}
func (s *Service) handleFavoritesDownloadAll(w http.ResponseWriter, r *http.Request) {
	if s.cfg == nil {
		writeErr(w, http.StatusForbidden, "not available in web mode")
		return
	}
	var req struct {
		AudioOnly bool `json:"audio_only"`
	}
	if err := readJSON(r, &req); err != nil {
		writeErr(w, http.StatusBadRequest, err.Error())
		return
	}
	favs := s.cfg.Favorites()
	if len(favs) == 0 {
		writeJSON(w, map[string]string{"status": "no favorites"})
		return
	}
	// Fire off all downloads concurrently and collect results.
	type result struct {
		URL  string `json:"url"`
		Path string `json:"path,omitempty"`
		Err  string `json:"error,omitempty"`
	}
	results := make([]result, len(favs))
	var wg sync.WaitGroup
	dir := s.cfg.DownloadDirectory()
	for i, fav := range favs {
		wg.Add(1)
		go func(i int, fav config.Favorite) {
			defer wg.Done()
			var path string
			var err error
			if req.AudioOnly {
				path, err = s.yt.DownloadAudio(r.Context(), fav.URL, dir)
			} else {
				path, err = s.yt.DownloadVideo(r.Context(), fav.URL, dir)
			}
			if err != nil {
				results[i] = result{URL: fav.URL, Err: err.Error()}
			} else {
				results[i] = result{URL: fav.URL, Path: path}
			}
		}(i, fav)
	}
	wg.Wait()
	writeJSON(w, results)
}

// streamClient exposes the shared yt client for the /stream/<id> handler.
func (s *Service) streamClient() *ytapi.Client { return s.yt }
