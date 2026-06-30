// Package config handles persistent app settings: favorites, download
// directory, and proxy configuration. Mirrors the Python version's
// src/core/settings_manager.py so settings.json stays compatible between
// the two builds (same app-data directory, same JSON shape).
package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"sync"
)

// AppDataDir returns the OS-appropriate per-user config directory,
// matching get_app_data_dir() in the Python version.
func AppDataDir() string {
	home, _ := os.UserHomeDir()
	switch runtime.GOOS {
	case "windows":
		if v := os.Getenv("APPDATA"); v != "" {
			return filepath.Join(v, "blindtube")
		}
		return filepath.Join(home, "AppData", "Roaming", "blindtube")
	case "darwin":
		return filepath.Join(home, "Library", "Application Support", "blindtube")
	default:
		if v := os.Getenv("XDG_CONFIG_HOME"); v != "" {
			return filepath.Join(v, "blindtube")
		}
		return filepath.Join(home, ".config", "blindtube")
	}
}

// Favorite mirrors the {"info": ..., "url": ...} shape used by the Python
// version's favorites list.
type Favorite struct {
	Info string `json:"info"`
	URL  string `json:"url"`
}

// Proxy mirrors {"enabled": bool, "url": "scheme://user:pass@host:port"}.
type Proxy struct {
	Enabled bool   `json:"enabled"`
	URL     string `json:"url"`
}

type Settings struct {
	DownloadDirectory string     `json:"download_directory"`
	Favorites         []Favorite `json:"favorites"`
	Proxy             Proxy      `json:"proxy"`
}

func defaultDownloadDir() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, "Downloads", "youtube")
}

func defaultSettings() Settings {
	return Settings{
		DownloadDirectory: defaultDownloadDir(),
		Favorites:         []Favorite{},
		Proxy:             Proxy{Enabled: false, URL: ""},
	}
}

// Manager is safe for concurrent use; every exported method is what the
// glaze-bound Service calls into from internal/ui/service.go.
type Manager struct {
	mu   sync.RWMutex
	path string
	s    Settings
}

func Load() (*Manager, error) {
	dir := AppDataDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		dir, _ = os.Getwd()
	}
	path := filepath.Join(dir, "settings.json")

	m := &Manager{path: path}

	data, err := os.ReadFile(path)
	if err != nil {
		m.s = defaultSettings()
		if mkErr := os.MkdirAll(m.s.DownloadDirectory, 0o755); mkErr != nil {
			m.s.DownloadDirectory = filepath.Join(os.TempDir(), "blindtube-downloads")
			_ = os.MkdirAll(m.s.DownloadDirectory, 0o755)
		}
		return m, m.save()
	}

	var s Settings
	if err := json.Unmarshal(data, &s); err != nil {
		m.s = defaultSettings()
		return m, m.save()
	}
	if s.Favorites == nil {
		s.Favorites = []Favorite{}
	}
	if s.DownloadDirectory == "" {
		s.DownloadDirectory = defaultDownloadDir()
	}
	m.s = s
	return m, nil
}

func (m *Manager) save() error {
	data, err := json.MarshalIndent(m.s, "", "    ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(m.path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(m.path, data, 0o644)
}

func (m *Manager) Snapshot() Settings {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.s
}

func (m *Manager) DownloadDirectory() string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.s.DownloadDirectory
}

func (m *Manager) SetDownloadDirectory(dir string) error {
	m.mu.Lock()
	m.s.DownloadDirectory = dir
	defer m.mu.Unlock()
	return m.save()
}

func (m *Manager) ProxySettings() Proxy {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.s.Proxy
}

func (m *Manager) SetProxy(p Proxy) error {
	m.mu.Lock()
	m.s.Proxy = p
	defer m.mu.Unlock()
	return m.save()
}

func (m *Manager) Favorites() []Favorite {
	m.mu.RLock()
	defer m.mu.RUnlock()
	out := make([]Favorite, len(m.s.Favorites))
	copy(out, m.s.Favorites)
	return out
}

func (m *Manager) AddFavorite(f Favorite) (bool, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, existing := range m.s.Favorites {
		if existing.URL == f.URL {
			return false, nil
		}
	}
	m.s.Favorites = append(m.s.Favorites, f)
	return true, m.save()
}

func (m *Manager) RemoveFavorite(url string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	filtered := m.s.Favorites[:0]
	for _, f := range m.s.Favorites {
		if f.URL != url {
			filtered = append(filtered, f)
		}
	}
	m.s.Favorites = filtered
	return m.save()
}
