import sys
import os
import json
from PyQt6.QtGui import QIcon, QAction, QKeyEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QFileDialog, QMessageBox
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QThread, QTimer

from tube import Worker
from pyvidplayer2 import VideoPyQT
try:
    from accessible_output3.outputs.auto import Auto
    HAS_AO3 = True
except ImportError:
    HAS_AO3 = False

class YouTubePlayer(QMainWindow):
    searchsig = pyqtSignal(str)
    downloadsig = pyqtSignal(str, bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube")
        if HAS_AO3:
            try:
                self.output = Auto()
            except Exception as e:
                print(f"Error initializing accessible-output3: {e}")
                self.output = None
        else:
            self.output = None

        self.load_settings()

        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.video_player: VideoPyQT = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

        self.add_ui(layout)
        self.w_thread()
        self.add_menubar()

    def load_settings(self):
        if not os.path.exists("settings.json"):
            self.settings = {"download_directory": os.path.join(os.path.expanduser("~"), "Downloads", "youtube")}
            with open("settings.json", "w") as f:
                json.dump(self.settings, f)
        else:
            try:
                with open("settings.json", "r") as f:
                    self.settings = json.load(f)
            except Exception:
                self.settings = {"download_directory": os.path.join(os.path.expanduser("~"), "Downloads", "youtube")}

    def save_settings(self):
        with open("settings.json", "w") as f:
            json.dump(self.settings, f)

    def add_ui(self, layout):
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search")
        self.search_field.returnPressed.connect(self.search)
        layout.addWidget(self.search_field)

        self.results_list = QListWidget()
        self.results_list.itemActivated.connect(self.play_video)
        layout.addWidget(self.results_list)

        # Video player widget
        self.video_widget = QWidget()
        self.video_widget.setMinimumSize(480, 360)
        self.video_widget.show()
        layout.addWidget(self.video_widget)

    def w_thread(self):
        self.worker = Worker()
        self.worker_thread = QThread()
        self.worker.search.connect(self.getsearch)
        self.worker.status_message.connect(self.speak)
        self.searchsig.connect(self.worker.searchthr)
        self.downloadsig.connect(self.worker.download_video)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

    def add_menubar(self):
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        playbackMenu = menubar.addMenu('&Playback')
        settingsMenu = menubar.addMenu('&Settings')

        self.add_item(fileMenu, "Download Video", "Ctrl+D", "Download the video", self.download_video_action)
        self.add_item(fileMenu, "Download Audio Track", "Ctrl+Shift+D", "Download only the audio", self.download_audio_action)
        self.add_item(fileMenu, "&Exit", "Ctrl+Q", "Exit the application", QApplication.instance().quit)

        self.add_item(playbackMenu, "Play / Pause", "Ctrl+Space", callback=self.playpause)
        self.add_item(playbackMenu, "Forward 5 seconds", "Ctrl+Right", callback=lambda: self.seek(True))
        self.add_item(playbackMenu, "Backward 5 seconds", "Ctrl+Left", callback=lambda: self.seek(False))
        self.add_item(playbackMenu, "Volume up", "Ctrl+Up", callback=lambda: self.volume(True))
        self.add_item(playbackMenu, "Volume down", "Ctrl+Down", callback=lambda: self.volume(False))
        self.add_item(playbackMenu, "Announce Position", "P", callback=self.announce_position)

        self.add_item(settingsMenu, "Change Download Directory", None, "Set where downloads go", self.change_download_dir)

    def add_item(self, menu, text, shortcut=None, description=None, callback=None):
        act = QAction(text, self)
        if shortcut is not None:
            act.setShortcut(shortcut)
        if description is not None:
            act.setStatusTip(description)
        if callback is not None:
            act.triggered.connect(callback)
        menu.addAction(act)

    def update_frame(self):
        if self.video_player is not None:
            self.video_player.draw(self.video_widget, (0, 0))

    def speak(self, text):
        print(f"Speaking: {text}")
        if self.output:
            self.output.output(text)

    def playpause(self):
        if self.video_player is None:
            return
        if not self.video_player.paused:
            self.video_player.pause()
            self.speak("Paused")
        else:
            self.video_player.play()
            self.speak("Resumed")

    def seek(self, right: bool):
        if self.video_player is None:
            return
        time = 5.0 if right else -5.0
        self.video_player.seek(time=time, relative=True)

    def volume(self, up: bool):
        if self.video_player is None:
            return
        volume_step = 0.1 if up else -0.1
        volume = self.video_player.get_volume()
        volume += volume_step
        volume = max(0.0, min(1.0, volume))
        self.video_player.set_volume(volume)

    def announce_position(self):
        if self.video_player is not None:
            pos = self.video_player.get_pos()
            m, s = divmod(int(pos), 60)
            h, m = divmod(m, 60)
            pos_str = f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:d}:{s:02d}"
            self.speak(f"Current position: {pos_str}")

    @pyqtSlot(list)
    def getsearch(self, search_results):
        self.results_list.clear()
        for i, (info, url) in enumerate(search_results):
            item = QListWidgetItem(info)
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.results_list.addItem(item)
        if not search_results:
            self.speak("No results found.")

    def search(self):
        query = self.search_field.text()
        if query:
            self.speak(f"Searching for {query}")
            self.searchsig.emit(query)

    def play_video(self, item: QListWidgetItem):
        if self.video_player is not None:
            self.video_player.stop()
            self.video_player.close()
            self.video_player = None

        url = item.data(Qt.ItemDataRole.UserRole)
        self.speak(f"Streaming {item.text()}")
        try:
            # VideoPyQT(path, chunk_size, max_threads, youtube=False, max_res=720, ...)
            self.video_player = VideoPyQT(url, youtube=True)
            self.video_player.play()
        except Exception as e:
            self.speak(f"Error playing video: {str(e)}")
            print(f"Error playing video: {e}")

    def download_video_action(self):
        item = self.results_list.currentItem()
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            self.downloadsig.emit(url, False)
        else:
            self.speak("Please select a video from the results list first.")

    def download_audio_action(self):
        item = self.results_list.currentItem()
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            self.downloadsig.emit(url, True)
        else:
            self.speak("Please select a video from the results list first.")

    def change_download_dir(self):
        new_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.settings.get("download_directory"))
        if new_dir:
            self.settings["download_directory"] = new_dir
            self.save_settings()
            self.speak(f"Download directory changed to {new_dir}")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_P:
            self.announce_position()
        else:
            super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubePlayer()
    window.show()
    sys.exit(app.exec())
