package ui

import (
	"context"
	"errors"
	"sync"

	"github.com/denizsincar29/blindtube/go/internal/config"
	"github.com/denizsincar29/blindtube/go/internal/ytapi"
)

// Service holds app-wide state: settings, the proxy-aware YouTube client,
// and which video is "current" for playback. Every exported method here
// becomes window.blindtube_<MethodName>(...) in JS once bound with
// glaze.BindMethods(w, "blindtube", svc) — see cmd/blindtube/main.go and
// the equivalent pattern in goshell's internal/ui/service.go. Each call
// already runs off the UI thread, so the blocking yt-dlp-equivalent
// network calls here don't freeze the window.
type Service struct {
	mu  sync.RWMutex
	cfg *config.Manager
	yt  *ytapi.Client

	currentVideoID string
}

func NewService(cfg *config.Manager) *Service {
	return &Service{
		cfg: cfg,
		yt:  ytapi.New(cfg.ProxySettings()),
	}
}

func (s *Service) client() *ytapi.Client {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.yt
}

// ---- Search (task.md #2: infinite-scroll pagination) ----

func (s *Service) Search(query string) ([]ytapi.Result, error) {
	if query == "" {
		return nil, errors.New("empty query")
	}
	return s.client().Search(query)
}

func (s *Service) SearchMore() ([]ytapi.Result, error) {
	return s.client().SearchMore()
}

// ---- Video info / playback ----

// GetVideoInfo resolves a URL, bare id, or one of the current search
// results into full metadata (title, channel, description, and the
// same-origin /stream/<id> path the <video> element should play).
func (s *Service) GetVideoInfo(urlOrID string) (*ytapi.VideoInfo, error) {
	info, err := s.client().GetVideoInfo(urlOrID)
	if err != nil {
		return nil, err
	}
	s.mu.Lock()
	s.currentVideoID = info.ID
	s.mu.Unlock()
	return info, nil
}

// ---- Downloads ----

func (s *Service) DownloadVideo(urlOrID string) (string, error) {
	dir := s.cfg.DownloadDirectory()
	return s.client().DownloadVideo(context.Background(), urlOrID, dir)
}

func (s *Service) DownloadAudio(urlOrID string) (string, error) {
	dir := s.cfg.DownloadDirectory()
	return s.client().DownloadAudio(context.Background(), urlOrID, dir)
}

// ---- Favorites ----

func (s *Service) Favorites() []config.Favorite {
	return s.cfg.Favorites()
}

type FavoriteRequest struct {
	Info string `json:"info"`
	URL  string `json:"url"`
}

// AddFavorite returns false (not an error) if the URL was already saved,
// matching the Python version's "Already in favorites" status message.
func (s *Service) AddFavorite(req FavoriteRequest) (bool, error) {
	return s.cfg.AddFavorite(config.Favorite{Info: req.Info, URL: req.URL})
}

func (s *Service) RemoveFavorite(url string) error {
	return s.cfg.RemoveFavorite(url)
}

// ---- Settings ----

func (s *Service) GetSettings() config.Settings {
	return s.cfg.Snapshot()
}

func (s *Service) SetDownloadDirectory(dir string) error {
	return s.cfg.SetDownloadDirectory(dir)
}

func (s *Service) SetProxy(p config.Proxy) error {
	if err := s.cfg.SetProxy(p); err != nil {
		return err
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.yt.Reconfigure(p)
}

// streamClient exposes the yt client to the /stream/<id> HTTP handler in
// server.go, which needs it directly (resolving + proxying a CDN URL
// isn't a Bind-shaped request/response call).
func (s *Service) streamClient() *ytapi.Client {
	return s.client()
}
