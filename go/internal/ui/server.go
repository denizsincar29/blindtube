package ui

import (
	"io"
	"log"
	"net/http"
	"strings"
)

// NewMux builds the http.Handler passed to glaze's window.Navigate. Same
// shape as goshell: the embedded frontend + one streaming endpoint that
// Bind has no primitive for; everything else (search, download, settings)
// is a direct Bind call from JS into Service's methods (see service.go).
func NewMux(svc *Service) *http.ServeMux {
	mux := http.NewServeMux()
	mux.HandleFunc("/", serveIndex)
	mux.HandleFunc("/static/app.js", serveJS)
	mux.HandleFunc("/static/app.css", serveCSS)
	mux.HandleFunc("/stream/", streamHandler(svc))
	return mux
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

// streamHandler proxies the resolved googlevideo CDN URL for a video id,
// forwarding the Range header both ways so the <video> element's native
// seek bar keeps working. Resolving here (rather than handing the
// frontend a raw CDN URL) is what makes the proxy setting in Settings
// actually apply to playback, not just to search/download.
func streamHandler(svc *Service) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := strings.TrimPrefix(r.URL.Path, "/stream/")
		if id == "" {
			http.Error(w, "missing video id", http.StatusBadRequest)
			return
		}

		streamURL, mimeType, err := svc.streamClient().ResolveStreamURL(id)
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

		client := svc.streamClient()
		resp, err := client.HTTPDo(req)
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
		_, _ = io.Copy(w, resp.Body)
	}
}
