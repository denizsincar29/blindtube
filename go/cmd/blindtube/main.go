// Command blindtube: desktop build. Starts the embedded HTTP server then
// opens a glaze (WebView2/webkitgtk) window pointing at it. No glaze Bind
// is used — everything is plain JSON over HTTP so the same frontend works
// in a browser on tube.denizsincar.ru without changes.
package main

import (
	"flag"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"time"

	"github.com/crgimenes/glaze"

	"github.com/denizsincar29/blindtube/go/internal/config"
	"github.com/denizsincar29/blindtube/go/internal/ui"
)

func main() {
	// CLI flags (mirror the Python version's argparse in main.py)
	urlFlag := flag.String("url", "", "Open a YouTube URL or video id directly")
	searchFlag := flag.String("search", "", "Search for this query on startup")
	flag.Parse()

	cfg, err := config.Load()
	if err != nil {
		log.Fatal("could not load settings: ", err)
	}

	svc := ui.NewService(cfg, ui.ModeDesktop)
	mux := ui.NewMux(svc)

	addr, err := startServer(mux)
	if err != nil {
		log.Fatal(err)
	}

	// Build startup URL: append CLI args as query params so the JS can
	// act on them after the page loads (same as handle_cli_args in Python).
	startURL := addr + "/"
	if *urlFlag != "" {
		startURL += "?url=" + *urlFlag
	} else if *searchFlag != "" {
		startURL += "?search=" + *searchFlag
	}

	// Check if we're headless (no display / scripting use): skip glaze.
	if os.Getenv("BT_HEADLESS") != "" {
		fmt.Println("Server running at", addr)
		select {}
	}

	w, err := glaze.New(false)
	if err != nil {
		log.Fatal(err)
	}
	defer w.Destroy()

	w.SetTitle("BlindTube")
	w.SetSize(1000, 700, glaze.HintNone)
	w.Navigate(startURL)
	w.Run()
}

func startServer(mux http.Handler) (string, error) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return "", fmt.Errorf("listen: %w", err)
	}
	srv := &http.Server{Handler: mux, ReadHeaderTimeout: 10 * time.Second}
	go func() { _ = srv.Serve(ln) }()
	return fmt.Sprintf("http://127.0.0.1:%d", ln.Addr().(*net.TCPAddr).Port), nil
}
