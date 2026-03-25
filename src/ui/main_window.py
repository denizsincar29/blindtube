import sys
import os
import re
from PyQt6.QtGui import QAction, QKeyEvent
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QLineEdit, QListWidget, QListWidgetItem, QFileDialog,
                             QMessageBox, QMenu)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QThread, QTimer

from src.core.tube_worker import TubeWorker
from src.core.settings_manager import SettingsManager
from src.ui.proxy_dialog import ProxySettingsDialog
from src.ui.video_info_window import VideoInfoWindow
from pyvidplayer2 import VideoPyQT

try:
    from accessible_output3.outputs.auto import Auto
    HAS_AO3 = True
except ImportError:
    HAS_AO3 = False

class MainWindow(QMainWindow):
    search_sig = pyqtSignal(str, int)
    download_sig = pyqtSignal(str, bool, str)
    getinfo_sig = pyqtSignal(str)
    getcomments_sig = pyqtSignal(str)

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

        self.settings_manager = SettingsManager()
        self.current_query = ""
        self.next_index = 1

        self._setup_ui()
        self._setup_worker()
        self._setup_menubar()

        # Home screen (favorites)
        self.show_favorites()

        # Handle CLI arguments
        QTimer.singleShot(100, self.handle_cli_args)

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search or enter URL")
        self.search_field.returnPressed.connect(self.search_action)
        layout.addWidget(self.search_field)

        self.results_list = QListWidget()
        self.results_list.itemActivated.connect(self.play_video_item)
        self.results_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results_list.customContextMenuRequested.connect(self.show_context_menu)
        self.results_list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.results_list)

        self.video_widget = QWidget()
        self.video_widget.setMinimumSize(480, 360)
        layout.addWidget(self.video_widget)

        self.video_player: VideoPyQT = None
        self.playback_active = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(16)

    def _setup_worker(self):
        self.worker = TubeWorker(self.settings_manager)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)

        self.worker.search_finished.connect(self._on_search_finished)
        self.worker.status_message.connect(self.handle_worker_status)
        self.worker.video_info_received.connect(self._on_video_info_received)
        self.worker.comments_received.connect(self._on_comments_received)

        self.search_sig.connect(self.worker.search_videos)
        self.download_sig.connect(self.worker.download_video)
        self.getinfo_sig.connect(self.worker.get_video_info)
        self.getcomments_sig.connect(self.worker.get_comments)

        self.worker_thread.start()

    def _setup_menubar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu('&File')
        favorites_menu = menubar.addMenu('&Favorites')
        playback_menu = menubar.addMenu('&Playback')
        settings_menu = menubar.addMenu('&Settings')

        self.add_menu_item(file_menu, "&Home", "Esc", "Go to favorites", self.show_favorites)
        self.add_menu_item(file_menu, "Download Video", "Ctrl+D", "Download the video", self.download_video_action)
        self.add_menu_item(file_menu, "Download Audio Track", "Ctrl+Shift+D", "Download only the audio", self.download_audio_action)
        self.add_menu_item(file_menu, "&Exit", "Ctrl+Q", "Exit the application", QApplication.instance().quit)

        self.add_menu_item(favorites_menu, "Add current to Favorites", "Ctrl+F", callback=self.add_current_to_favorites)
        self.add_menu_item(favorites_menu, "Download all favorites as Video", None, callback=lambda: self.download_all_favorites(False))
        self.add_menu_item(favorites_menu, "Download all favorites as Audio", None, callback=lambda: self.download_all_favorites(True))

        self.add_menu_item(playback_menu, "Play / Pause", "Ctrl+Space", callback=self.playpause)
        self.add_menu_item(playback_menu, "Forward 5 seconds", "Ctrl+Right", callback=lambda: self.seek(True))
        self.add_menu_item(playback_menu, "Backward 5 seconds", "Ctrl+Left", callback=lambda: self.seek(False))
        self.add_menu_item(playback_menu, "Volume up", "Ctrl+Up", callback=lambda: self.volume(True))
        self.add_menu_item(playback_menu, "Volume down", "Ctrl+Down", callback=lambda: self.volume(False))
        self.add_menu_item(playback_menu, "Announce Position", "P", callback=self.announce_position)
        self.add_menu_item(playback_menu, "View Description and Comments", "Ctrl+Return", callback=self.view_video_info)

        self.add_menu_item(settings_menu, "Proxy Settings", None, "Configure proxy", self.show_proxy_settings)
        self.add_menu_item(settings_menu, "Change Download Directory", None, "Set where downloads go", self.change_download_dir)

    def add_menu_item(self, menu, text, shortcut=None, description=None, callback=None):
        act = QAction(text, self)
        if shortcut is not None:
            act.setShortcut(shortcut)
        if description is not None:
            act.setStatusTip(description)
        if callback is not None:
            act.triggered.connect(callback)
        menu.addAction(act)

    def speak(self, text):
        print(f"Speaking: {text}")
        if self.output:
            self.output.output(text)

    def handle_worker_status(self, message):
        self.speak(message)
        if message == "Download complete" and self.cli_args.get("close_on_completion"):
             QApplication.instance().quit()

    def update_frame(self):
        if self.video_player is not None:
            self.video_player.draw(self.video_widget, (0, 0))
            if self.video_player.active:
                self.playback_active = True
            elif self.playback_active:
                self.playback_active = False
                if self.cli_args.get("close_on_completion"):
                    QApplication.instance().quit()

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

    def search_action(self):
        query = self.search_field.text().strip()
        if not query:
            return

        if re.match(r'^https?://', query):
            self.speak(f"Loading {query}")
            self.getinfo_sig.emit(query)
            return

        self.speak(f"Searching for {query}")
        self.current_query = query
        self.next_index = 1
        self.results_list.clear()
        self.search_sig.emit(query, self.next_index)

    @pyqtSlot(list, bool)
    def _on_search_finished(self, search_results, is_append):
        if not is_append:
             self.results_list.clear()

        for info, url in search_results:
            item = QListWidgetItem(info)
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.results_list.addItem(item)

        if not is_append and not search_results:
            self.speak("No results found.")

        if search_results:
             self.next_index += len(search_results)

        if self.cli_args.get("play_first") and not is_append and search_results:
            self.results_list.setCurrentRow(0)
            self.play_video_item(self.results_list.item(0))
            self.cli_args["play_first"] = False

        if self.cli_args.get("download") and not is_append and search_results:
            self.results_list.setCurrentRow(0)
            self.download_video_action()
            self.cli_args["download"] = False

    def _on_row_changed(self, current_row):
        # When scrolling down, if we reach the last 2 items, load 10 more results
        if self.current_query and current_row >= self.results_list.count() - 2:
            self.search_sig.emit(self.current_query, self.next_index)

    @pyqtSlot(dict)
    def _on_video_info_received(self, data):
        info = data["info"]
        url = data["url"]
        self.current_video_data = data

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

    @pyqtSlot(list, str)
    def _on_comments_received(self, comments, video_id):
        if hasattr(self, 'current_video_data') and self.current_video_data.get("id") == video_id:
            info_win = VideoInfoWindow(self, "Video Info", self.current_video_data.get("description", ""), comments, self.current_video_data.get("url"))
            info_win.show()

    def view_video_info(self):
        item = self.results_list.currentItem()
        if not item:
            self.speak("No video selected")
            return

        url = item.data(Qt.ItemDataRole.UserRole)
        self.speak("Fetching video info and comments...")
        # Make sure we have the description first
        self.getinfo_sig.emit(url)
        # Fetch comments
        self.getcomments_sig.emit(url)

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
            proxy = self.settings_manager.get("proxy", {})
            if proxy.get("enabled") and proxy.get("url"):
                os.environ["HTTP_PROXY"] = proxy.get("url")
                os.environ["HTTPS_PROXY"] = proxy.get("url")
            else:
                os.environ.pop("HTTP_PROXY", None)
                os.environ.pop("HTTPS_PROXY", None)

            self.video_player = VideoPyQT(url, youtube=True)
            self.video_player.play()
            self.speak("playing")
        except Exception as e:
            self.speak(f"Error playing video: {str(e)}")
            print(f"Error playing video: {e}")

    def show_favorites(self):
        self.search_field.clear()
        self.results_list.clear()
        self.current_query = ""
        favorites = self.settings_manager.get("favorites", [])
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

        favorites = self.settings_manager.get("favorites", [])
        if any(f["url"] == url for f in favorites):
            self.speak("Already in favorites")
            return

        favorites.append({"info": info, "url": url})
        self.settings_manager.set("favorites", favorites)
        self.speak("Added to favorites")

    def remove_from_favorites(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        favorites = self.settings_manager.get("favorites", [])
        favorites = [f for f in favorites if f["url"] != url]
        self.settings_manager.set("favorites", favorites)
        self.show_favorites()
        self.speak("Removed from favorites")

    def download_video_action(self):
        item = self.results_list.currentItem()
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            self.download_sig.emit(url, False, self.settings_manager.get("download_directory"))
        else:
            self.speak("Please select a video first.")

    def download_audio_action(self):
        item = self.results_list.currentItem()
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            self.download_sig.emit(url, True, self.settings_manager.get("download_directory"))
        else:
            self.speak("Please select a video first.")

    def download_all_favorites(self, audio_only):
        favorites = self.settings_manager.get("favorites", [])
        if not favorites:
            self.speak("No favorites to download")
            return

        self.speak(f"Downloading {len(favorites)} favorites")
        for fav in favorites:
            self.download_sig.emit(fav["url"], audio_only, self.settings_manager.get("download_directory"))

    def show_context_menu(self, position):
        item = self.results_list.itemAt(position)
        if not item:
            return

        menu = QMenu()
        play_action = menu.addAction("Play")
        view_info_action = menu.addAction("View Description and Comments")
        download_video_action = menu.addAction("Download Video")
        download_audio_action = menu.addAction("Download Audio")
        copy_link_action = menu.addAction("Copy Link")

        favorites = self.settings_manager.get("favorites", [])
        is_favorite = any(f["url"] == item.data(Qt.ItemDataRole.UserRole) for f in favorites)

        if is_favorite:
            fav_action = menu.addAction("Remove from Favorites")
        else:
            fav_action = menu.addAction("Add to Favorites")

        action = menu.exec(self.results_list.mapToGlobal(position))

        if action == play_action:
            self.play_video_item(item)
        elif action == view_info_action:
            self.view_video_info()
        elif action == download_video_action:
            self.download_sig.emit(item.data(Qt.ItemDataRole.UserRole), False, self.settings_manager.get("download_directory"))
        elif action == download_audio_action:
            self.download_sig.emit(item.data(Qt.ItemDataRole.UserRole), True, self.settings_manager.get("download_directory"))
        elif action == copy_link_action:
            QApplication.clipboard().setText(item.data(Qt.ItemDataRole.UserRole))
            self.speak("Link copied to clipboard")
        elif action == fav_action:
            if is_favorite:
                self.remove_from_favorites(item)
            else:
                self.add_current_to_favorites()

    def change_download_dir(self):
        new_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.settings_manager.get("download_directory"))
        if new_dir:
            self.settings_manager.set("download_directory", new_dir)
            self.speak(f"Download directory changed to {new_dir}")

    def show_proxy_settings(self):
        initial_proxy = self.settings_manager.get("proxy", {"enabled": False, "url": ""})
        dialog = ProxySettingsDialog(self, initial_proxy)
        if dialog.exec():
            new_proxy = dialog.get_proxy_settings()
            self.settings_manager.set("proxy", new_proxy)
            self.speak(f"Proxy settings updated. Proxy {'enabled' if new_proxy['enabled'] else 'disabled'}.")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_P:
            self.announce_position()
        elif event.key() == Qt.Key.Key_Escape:
            self.show_favorites()
        elif event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.view_video_info()
        else:
            super().keyPressEvent(event)

    def handle_cli_args(self):
        if self.cli_args.get("url"):
            self.search_field.setText(self.cli_args["url"])
            self.search_action()
        elif self.cli_args.get("search"):
            self.search_field.setText(self.cli_args["search"])
            self.search_action()
