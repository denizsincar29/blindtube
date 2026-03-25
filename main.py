import sys
import os
import json
import re
from PyQt6.QtGui import QIcon, QAction, QKeyEvent
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLineEdit, QListWidget, QListWidgetItem, QFileDialog,
                             QMessageBox, QMenu)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QThread, QTimer

from tube import Worker
from pyvidplayer2 import VideoPyQT
try:
    from accessible_output3.outputs.auto import Auto
    HAS_AO3 = True
except ImportError:
    HAS_AO3 = False

import click

class YouTubePlayer(QMainWindow):
    searchsig = pyqtSignal(str)
    downloadsig = pyqtSignal(str, bool, str)
    getinfo_sig = pyqtSignal(str)

    def __init__(self, cli_args=None):
        super().__init__()
        self.cli_args = cli_args or {}
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
        self.playback_active = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

        self.add_ui(layout)
        self.w_thread()
        self.add_menubar()

        # Home screen (favorites)
        self.show_favorites()

        # Handle CLI arguments
        QTimer.singleShot(100, self.handle_cli_args)

    def load_settings(self):
        default_dir = os.path.join(os.path.expanduser("~"), "Downloads", "youtube")
        if not os.path.exists(default_dir):
            try:
                os.makedirs(default_dir)
            except Exception:
                default_dir = os.path.join(os.getcwd(), "downloads")

        if not os.path.exists("settings.json"):
            self.settings = {
                "download_directory": default_dir,
                "favorites": []
            }
            self.save_settings()
        else:
            try:
                with open("settings.json", "r") as f:
                    self.settings = json.load(f)
                if "favorites" not in self.settings:
                    self.settings["favorites"] = []
                if "download_directory" not in self.settings:
                    self.settings["download_directory"] = default_dir
            except Exception:
                self.settings = {
                    "download_directory": default_dir,
                    "favorites": []
                }

    def save_settings(self):
        with open("settings.json", "w") as f:
            json.dump(self.settings, f, indent=4)

    def add_ui(self, layout):
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search or enter URL")
        self.search_field.returnPressed.connect(self.search)
        layout.addWidget(self.search_field)

        self.results_list = QListWidget()
        self.results_list.itemActivated.connect(self.play_video_item)
        self.results_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_list.customContextMenuRequested.connect(self.show_context_menu)
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
        self.worker.status_message.connect(self.handle_worker_status)
        self.worker.video_info.connect(self.on_video_info_received)
        self.searchsig.connect(self.worker.searchthr)
        self.downloadsig.connect(self.worker.download_video)
        self.getinfo_sig.connect(self.worker.get_video_info)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

    def handle_worker_status(self, message):
        self.speak(message)
        if message == "Download complete" and self.cli_args.get("close_on_completion"):
             QApplication.instance().quit()

    def add_menubar(self):
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        favoritesMenu = menubar.addMenu('&Favorites')
        playbackMenu = menubar.addMenu('&Playback')
        settingsMenu = menubar.addMenu('&Settings')

        self.add_item(fileMenu, "&Home", "Esc", "Go to favorites", self.show_favorites)
        self.add_item(fileMenu, "Download Video", "Ctrl+D", "Download the video", self.download_video_action)
        self.add_item(fileMenu, "Download Audio Track", "Ctrl+Shift+D", "Download only the audio", self.download_audio_action)
        self.add_item(fileMenu, "&Exit", "Ctrl+Q", "Exit the application", QApplication.instance().quit)

        self.add_item(favoritesMenu, "Add current to Favorites", "Ctrl+F", callback=self.add_current_to_favorites)
        self.add_item(favoritesMenu, "Download all favorites as Video", None, callback=lambda: self.download_all_favorites(False))
        self.add_item(favoritesMenu, "Download all favorites as Audio", None, callback=lambda: self.download_all_favorites(True))

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
            if self.video_player.active:
                self.playback_active = True
            elif self.playback_active:
                # Video was active but now it's not -> finished
                self.playback_active = False
                if self.cli_args.get("close_on_completion"):
                    QApplication.instance().quit()

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
        for info, url in search_results:
            item = QListWidgetItem(info)
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.results_list.addItem(item)
        if not search_results:
            self.speak("No results found.")

        if self.cli_args.get("play_first") and search_results:
            self.results_list.setCurrentRow(0)
            self.play_video_item(self.results_list.item(0))
            self.cli_args["play_first"] = False # Only play once

        if self.cli_args.get("download") and search_results:
            self.results_list.setCurrentRow(0)
            self.download_video_action()
            self.cli_args["download"] = False

    def search(self):
        query = self.search_field.text().strip()
        if not query:
            return

        # Check if it's a URL
        if re.match(r'^https?://', query):
            self.speak(f"Loading {query}")
            self.getinfo_sig.emit(query)
            return

        self.speak(f"Searching for {query}")
        self.searchsig.emit(query)

    @pyqtSlot(dict)
    def on_video_info_received(self, data):
        info = data["info"]
        url = data["url"]

        # Add to list if not already there
        found = False
        item = None
        for i in range(self.results_list.count()):
            if self.results_list.item(i).data(Qt.ItemDataRole.UserRole) == url:
                self.results_list.setCurrentRow(i)
                item = self.results_list.item(i)
                found = True
                break

        if not found:
            item = QListWidgetItem(info)
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.results_list.insertItem(0, item)
            self.results_list.setCurrentRow(0)

        if self.cli_args.get("download"):
            self.download_video_action()
            self.cli_args["download"] = False
        else:
            self.play_video_item(item)

    def play_video_item(self, item: QListWidgetItem):
        if not item:
            return
        url = item.data(Qt.ItemDataRole.UserRole)
        title = item.text()

        if self.video_player is not None:
            self.video_player.stop()
            self.video_player.close()
            self.video_player = None
            self.playback_active = False

        self.speak(f"loading {title}")
        try:
            self.video_player = VideoPyQT(url, youtube=True)
            self.video_player.play()
            self.speak("playing")
        except Exception as e:
            self.speak(f"Error playing video: {str(e)}")
            print(f"Error playing video: {e}")

    def show_favorites(self):
        self.search_field.clear()
        self.results_list.clear()
        favorites = self.settings.get("favorites", [])
        for fav in favorites:
            item = QListWidgetItem(fav["info"])
            item.setData(Qt.ItemDataRole.UserRole, fav["url"])
            self.results_list.addItem(item)
        self.speak(f"Home. {len(favorites)} favorites.")

    def add_current_to_favorites(self):
        item = self.results_list.currentItem()
        if not item:
            self.speak("No video selected")
            return

        info = item.text()
        url = item.data(Qt.ItemDataRole.UserRole)

        favorites = self.settings.get("favorites", [])
        if any(f["url"] == url for f in favorites):
            self.speak("Already in favorites")
            return

        favorites.append({"info": info, "url": url})
        self.settings["favorites"] = favorites
        self.save_settings()
        self.speak("Added to favorites")

    def remove_from_favorites(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        favorites = self.settings.get("favorites", [])
        self.settings["favorites"] = [f for f in favorites if f["url"] != url]
        self.save_settings()
        self.show_favorites()
        self.speak("Removed from favorites")

    def download_video_action(self):
        item = self.results_list.currentItem()
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            self.downloadsig.emit(url, False, self.settings.get("download_directory"))
        else:
            self.speak("Please select a video first.")

    def download_audio_action(self):
        item = self.results_list.currentItem()
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            self.downloadsig.emit(url, True, self.settings.get("download_directory"))
        else:
            self.speak("Please select a video first.")

    def download_all_favorites(self, audio_only):
        favorites = self.settings.get("favorites", [])
        if not favorites:
            self.speak("No favorites to download")
            return

        self.speak(f"Downloading {len(favorites)} favorites")
        for fav in favorites:
            self.downloadsig.emit(fav["url"], audio_only, self.settings.get("download_directory"))

    def show_context_menu(self, position):
        item = self.results_list.itemAt(position)
        if not item:
            return

        menu = QMenu()
        play_action = menu.addAction("Play")
        download_video_action = menu.addAction("Download Video")
        download_audio_action = menu.addAction("Download Audio")
        copy_link_action = menu.addAction("Copy Link")

        is_favorite = any(f["url"] == item.data(Qt.ItemDataRole.UserRole) for f in self.settings.get("favorites", []))

        if is_favorite:
            fav_action = menu.addAction("Remove from Favorites")
        else:
            fav_action = menu.addAction("Add to Favorites")

        action = menu.exec(self.results_list.mapToGlobal(position))

        if action == play_action:
            self.play_video_item(item)
        elif action == download_video_action:
            self.downloadsig.emit(item.data(Qt.ItemDataRole.UserRole), False, self.settings.get("download_directory"))
        elif action == download_audio_action:
            self.downloadsig.emit(item.data(Qt.ItemDataRole.UserRole), True, self.settings.get("download_directory"))
        elif action == copy_link_action:
            QApplication.clipboard().setText(item.data(Qt.ItemDataRole.UserRole))
            self.speak("Link copied to clipboard")
        elif action == fav_action:
            if is_favorite:
                self.remove_from_favorites(item)
            else:
                self.add_current_to_favorites()

    def change_download_dir(self):
        new_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.settings.get("download_directory"))
        if new_dir:
            self.settings["download_directory"] = new_dir
            self.save_settings()
            self.speak(f"Download directory changed to {new_dir}")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_P:
            self.announce_position()
        elif event.key() == Qt.Key.Key_Escape:
            self.show_favorites()
        else:
            super().keyPressEvent(event)

    def handle_cli_args(self):
        if self.cli_args.get("url"):
            self.search_field.setText(self.cli_args["url"])
            self.search()
        elif self.cli_args.get("search"):
            self.search_field.setText(self.cli_args["search"])
            self.search()

@click.command()
@click.option('--play', help='URL to play')
@click.option('--search', help='Search query')
@click.option('--play-first', is_flag=True, help='Play first search result')
@click.option('--download', is_flag=True, help='Download the (first) result')
@click.option('--close-on-completion', is_flag=True, help='Close app when done')
def main(play, search, play_first, download, close_on_completion):
    app = QApplication(sys.argv)

    cli_args = {
        "url": play,
        "search": search,
        "play_first": play_first or (play is not None),
        "download": download,
        "close_on_completion": close_on_completion
    }

    window = YouTubePlayer(cli_args)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
