// Command blindtube is the Go rewrite of the Python BlindTube app: an
// accessible YouTube client. Search/info/download/settings/favorites are
// plain Bind request/response calls (see internal/ui/service.go); the
// one thing Bind can't do — streaming media bytes with seek support — is
// served over a real HTTP route (see internal/ui/server.go).
package main

import (
	"fmt"
	"log"
	"net"
	"net/http"
	"time"

	"github.com/crgimenes/glaze"

	"github.com/denizsincar29/blindtube/go/internal/config"
	"github.com/denizsincar29/blindtube/go/internal/ui"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatal("could not load settings: ", err)
	}

	svc := ui.NewService(cfg)
	mux := ui.NewMux(svc)

	baseURL, err := startServer(mux)
	if err != nil {
		log.Fatal(err)
	}

	w, err := glaze.New(false)
	if err != nil {
		log.Fatal(err)
	}
	defer w.Destroy()

	w.SetTitle("BlindTube")
	w.SetSize(1000, 700, glaze.HintNone)

	if _, err := glaze.BindMethods(w, "blindtube", svc); err != nil {
		log.Fatal("BindMethods:", err)
	}

	w.Navigate(baseURL)
	w.Run()
}

// startServer starts the embedded-frontend + /stream proxy on a random
// loopback port, same approach as goshell, so the WebView always talks
// same-origin (no CORS, cookies/auth from the configured proxy stay
// consistent) instead of fetching googlevideo.com directly.
func startServer(mux http.Handler) (string, error) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", fmt.Errorf("listen: %w", err)
	}
	srv := &http.Server{Handler: mux, ReadHeaderTimeout: 10 * time.Second}
	go func() { _ = srv.Serve(ln) }()

	addr := ln.Addr().(*net.TCPAddr)
	return fmt.Sprintf("http://127.0.0.1:%d", addr.Port), nil
}
