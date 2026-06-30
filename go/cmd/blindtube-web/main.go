// Command blindtube-web: web backend for tube.denizsincar.ru.
// Same handler as the desktop build — no glaze, no settings file,
// just a plain HTTP server. Downloads stream back to the browser
// as file attachments. Favorites/proxy/download-dir settings are
// not available (the /api/mode endpoint returns "web" so the frontend
// hides those controls automatically).
package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/denizsincar29/blindtube/go/internal/ui"
)

func main() {
	addr := flag.String("addr", ":8080", "listen address")
	flag.Parse()

	// cfg=nil signals web mode: no settings file, no local download dir.
	svc := ui.NewService(nil, ui.ModeWeb)
	mux := ui.NewMux(svc)

	srv := &http.Server{
		Addr:              *addr,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
	}

	fmt.Println("blindtube-web listening on", *addr)
	log.Fatal(srv.ListenAndServe())
}
