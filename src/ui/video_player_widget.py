from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer
from pyvidplayer2 import VideoPyQT
import os

class VideoPlayerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 360)

        self.video_player: VideoPyQT = None
        self.playback_active = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

    def update_frame(self):
        if self.video_player is not None:
            self.video_player.draw(self, (0, 0))
            if self.video_player.active:
                self.playback_active = True
            elif self.playback_active:
                self.playback_active = False
                # Optionally notify parent that video finished

    def play_video(self, url, proxy_url=None):
        self.stop_video()

        if proxy_url:
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
        else:
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("HTTPS_PROXY", None)

        try:
            self.video_player = VideoPyQT(url, youtube=True)
            self.video_player.play()
            return True
        except Exception as e:
            print(f"Error playing video: {e}")
            return False

    def stop_video(self):
        if self.video_player is not None:
            self.video_player.stop()
            self.video_player.close()
            self.video_player = None
            self.playback_active = False

    def toggle_pause(self):
        if self.video_player:
            if not self.video_player.paused:
                self.video_player.pause()
                return "Paused"
            else:
                self.video_player.play()
                return "Resumed"
        return None

    def seek(self, seconds):
        if self.video_player:
            self.video_player.seek(time=seconds, relative=True)

    def change_volume(self, delta):
        if self.video_player:
            volume = self.video_player.get_volume()
            volume = max(0.0, min(1.0, volume + delta))
            self.video_player.set_volume(volume)
            return volume
        return None

    def get_position_str(self):
        if self.video_player:
            pos = self.video_player.get_pos()
            m, s = divmod(int(pos), 60)
            h, m = divmod(m, 60)
            return f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:d}:{s:02d}"
        return None
