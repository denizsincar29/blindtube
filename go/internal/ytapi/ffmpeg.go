package ytapi

import "os/exec"

// hasFFmpeg reports whether ffmpeg is reachable on PATH, used to decide
// whether DownloadVideo can attempt the higher-quality composite
// (separate video+audio, muxed) path.
func hasFFmpeg() bool {
	_, err := exec.LookPath("ffmpeg")
	return err == nil
}
