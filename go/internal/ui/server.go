package ui

import (
	"io"
	"log"
	"net/http"
	"strings"
)

// NewMux wires up every HTTP route. The same mux is used for both the
// desktop build (glaze points its webview at http://127.0.0.1:<port>/)
// and the web build (tube.denizsincar.ru, public internet). There is no
// glaze-Bind bridge at all — everything is plain JSON over HTTP so a real
// browser and the embedded webview talk the same protocol.
func NewMux(svc *Service) *http.ServeMux {
	mux := http.NewServeMux()

	// Frontend assets.
	mux.HandleFunc("/", serveIndex)
	mux.HandleFunc("/static/app.js", serveJS)
	mux.HandleFunc("/static/app.css", serveCSS)

	// Stream proxy: piped through the Go server so the configured proxy
	// applies to playback, not just to search/metadata, and so CDN URLs
	// (IP-pinned, short-lived) never reach the browser directly.
	mux.HandleFunc("/stream/", streamHandler(svc))

	// REST API.
	mux.HandleFunc("/api/mode", svc.handleMode)
	mux.HandleFunc("/api/search", svc.handleSearch)
	mux.HandleFunc("/api/search/more", svc.handleSearchMore)
	mux.HandleFunc("/api/video", svc.handleVideoInfo)
	mux.HandleFunc("/api/download/video", svc.handleDownloadVideo)
	mux.HandleFunc("/api/download/audio", svc.handleDownloadAudio)
	mux.HandleFunc("/api/favorites", favoritesRouter(svc))
	mux.HandleFunc("/api/favorites/download-all", svc.handleFavoritesDownloadAll)
	mux.HandleFunc("/api/settings", svc.handleSettingsGet)
	mux.HandleFunc("/api/settings/proxy", svc.handleSettingsProxy)
	mux.HandleFunc("/api/settings/download-dir", svc.handleSettingsDownloadDir)

	return mux
}

// favoritesRouter dispatches GET / POST / DELETE on /api/favorites.
func favoritesRouter(svc *Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			svc.handleFavoritesGet(w, r)
		case http.MethodPost:
			svc.handleFavoritesAdd(w, r)
		case http.MethodDelete:
			svc.handleFavoritesDelete(w, r)
		default:
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	}
}

func serveIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	io.WriteString(w, indexHTML)
}

func serveJS(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/javascript")
	io.WriteString(w, appJS)
}

func serveCSS(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/css")
	io.WriteString(w, appCSS)
}

// streamHandler proxies the resolved googlevideo URL for the given video
// id back to the browser/webview with Range support so seeking works.
func streamHandler(svc *Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := strings.TrimPrefix(r.URL.Path, "/stream/")
		if id == "" {
			http.Error(w, "missing video id", http.StatusBadRequest)
			return
		}
		streamURL, mimeType, _, err := svc.streamClient().ResolveVideoURL(id)
		if err != nil {
			log.Println("stream resolve error:", err)
			http.Error(w, "could not resolve stream: "+err.Error(), http.StatusBadGateway)
			return
		}
		req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, streamURL, nil)
		if err != nil {
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}
		if rng := r.Header.Get("Range"); rng != "" {
			req.Header.Set("Range", rng)
		}
		resp, err := svc.streamClient().HTTPDo(req)
		if err != nil {
			log.Println("stream fetch error:", err)
			http.Error(w, "could not fetch stream", http.StatusBadGateway)
			return
		}
		defer resp.Body.Close()

		if ct := resp.Header.Get("Content-Type"); ct != "" {
			w.Header().Set("Content-Type", ct)
		} else {
			w.Header().Set("Content-Type", mimeType)
		}
		if cl := resp.Header.Get("Content-Length"); cl != "" {
			w.Header().Set("Content-Length", cl)
		}
		if cr := resp.Header.Get("Content-Range"); cr != "" {
			w.Header().Set("Content-Range", cr)
		}
		w.Header().Set("Accept-Ranges", "bytes")
		w.WriteHeader(resp.StatusCode)
		proxyBody(w, resp)
	}
}

// proxyBody copies a response body into w, flushing after each chunk
// when the ResponseWriter supports it (important for streaming playback).
func proxyBody(w http.ResponseWriter, resp *http.Response) {
	if f, ok := w.(http.Flusher); ok {
		buf := make([]byte, 32*1024)
		for {
			n, err := resp.Body.Read(buf)
			if n > 0 {
				_, _ = w.Write(buf[:n])
				f.Flush()
			}
			if err != nil {
				break
			}
		}
	} else {
		_, _ = io.Copy(w, resp.Body)
	}
}
