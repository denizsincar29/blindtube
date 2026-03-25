from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                             QLineEdit, QListWidget, QListWidgetItem, QFileDialog,
                             QMessageBox, QMenu, QApplication)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QAction, QKeyEvent
import re
import os

from src.core.tube_worker import TubeWorker
from src.core.settings_manager import SettingsManager
from src.ui.proxy_dialog import ProxySettingsDialog
from src.ui.video_info_window import VideoInfoWindow
from src.ui.video_player_widget import VideoPlayerWidget

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

        self.output = Auto() if HAS_AO3 else None
        self.settings_manager = SettingsManager()
        self.current_query = ""
        self.next_index = 1
        self.current_video_data = None

        self._setup_ui()
        self._setup_worker()
        self._setup_menubar()

        self.show_favorites()
        QTimer.singleShot(100, self.handle_cli_args)

    def _setup_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

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

        self.video_player_widget = VideoPlayerWidget()
        layout.addWidget(self.video_player_widget)

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
        self.add_menu_item(file_menu, "&Home", "Esc", "Go to favorites", self.show_favorites)
        self.add_menu_item(file_menu, "Download Video", "Ctrl+D", "Download video", self.download_video_action)
        self.add_menu_item(file_menu, "Download Audio", "Ctrl+Shift+D", "Download audio", self.download_audio_action)
        self.add_menu_item(file_menu, "&Exit", "Ctrl+Q", "Exit", QApplication.instance().quit)

        fav_menu = menubar.addMenu('&Favorites')
        self.add_menu_item(fav_menu, "Add current to Favorites", "Ctrl+F", callback=self.add_current_to_favorites)
        self.add_menu_item(fav_menu, "Download all as Video", None, callback=lambda: self.download_all_favorites(False))
        self.add_menu_item(fav_menu, "Download all as Audio", None, callback=lambda: self.download_all_favorites(True))

        playback_menu = menubar.addMenu('&Playback')
        self.add_menu_item(playback_menu, "Play / Pause", "Ctrl+Space", callback=self.play_pause)
        self.add_menu_item(playback_menu, "Forward 5s", "Ctrl+Right", callback=lambda: self.seek(5))
        self.add_menu_item(playback_menu, "Backward 5s", "Ctrl+Left", callback=lambda: self.seek(-5))
        self.add_menu_item(playback_menu, "Volume Up", "Ctrl+Up", callback=lambda: self.volume(0.1))
        self.add_menu_item(playback_menu, "Volume Down", "Ctrl+Down", callback=lambda: self.volume(-0.1))
        self.add_menu_item(playback_menu, "Announce Position", "P", callback=self.announce_position)
        self.add_menu_item(playback_menu, "View Video Info", "Ctrl+Return", callback=self.view_video_info)

        settings_menu = menubar.addMenu('&Settings')
        self.add_menu_item(settings_menu, "Proxy Settings", None, "Configure proxy", self.show_proxy_settings)
        self.add_menu_item(settings_menu, "Change Download Directory", None, "Set where downloads go", self.change_download_dir)

    def add_menu_item(self, menu, text, shortcut=None, tip=None, callback=None):
        act = QAction(text, self)
        if shortcut: act.setShortcut(shortcut)
        if tip: act.setStatusTip(tip)
        if callback: act.triggered.connect(callback)
        menu.addAction(act)

    def speak(self, text):
        print(f"Speaking: {text}")
        if self.output: self.output.output(text)

    def handle_worker_status(self, message):
        self.speak(message)
        if message == "Download complete" and self.cli_args.get("close_on_completion"):
             QApplication.instance().quit()

    @pyqtSlot(list, bool)
    def _on_search_finished(self, results, is_append):
        if not is_append: self.results_list.clear()
        for info, url in results:
            item = QListWidgetItem(info)
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.results_list.addItem(item)
        if results: self.next_index += len(results)

        if not is_append and not results: self.speak("No results found.")

        if self.cli_args.get("play_first") and not is_append and results:
            self.results_list.setCurrentRow(0)
            self.play_video_item(self.results_list.item(0))
            self.cli_args["play_first"] = False

    def _on_row_changed(self, row):
        if self.current_query and row >= self.results_list.count() - 2:
            self.search_sig.emit(self.current_query, self.next_index)

    @pyqtSlot(dict)
    def _on_video_info_received(self, data):
        self.current_video_data = data
        found = False
        for i in range(self.results_list.count()):
            if self.results_list.item(i).data(Qt.ItemDataRole.UserRole) == data["url"]:
                self.results_list.setCurrentRow(i)
                found = True
                break
        if not found:
            item = QListWidgetItem(data["info"])
            item.setData(Qt.ItemDataRole.UserRole, data["url"])
            self.results_list.insertItem(0, item)
            self.results_list.setCurrentRow(0)

        if self.cli_args.get("download"):
            self.download_video_action()
            self.cli_args["download"] = False
        else:
            self.play_video_item(self.results_list.currentItem())

    @pyqtSlot(list, str)
    def _on_comments_received(self, comments, video_id):
        if self.current_video_data and self.current_video_data.get("id") == video_id:
            info_win = VideoInfoWindow(self, "Video Info", self.current_video_data.get("description", ""), comments, self.current_video_data.get("url"))
            info_win.show()

    def search_action(self):
        query = self.search_field.text().strip()
        if not query: return
        if re.match(r'^https?://', query):
            self.speak(f"Loading {query}")
            self.getinfo_sig.emit(query)
        else:
            self.speak(f"Searching for {query}")
            self.current_query = query
            self.next_index = 1
            self.results_list.clear()
            self.search_sig.emit(query, self.next_index)

    def play_video_item(self, item):
        if not item: return
        url = item.data(Qt.ItemDataRole.UserRole)
        title = item.text()
        self.speak(f"Loading {title}")
        proxy = self.settings_manager.get("proxy", {})
        proxy_url = proxy.get("url") if proxy.get("enabled") else None
        if self.video_player_widget.play_video(url, proxy_url):
            self.speak("Playing")
        else:
            self.speak("Error playing video")

    def play_pause(self):
        res = self.video_player_widget.toggle_pause()
        if res: self.speak(res)

    def seek(self, seconds):
        self.video_player_widget.seek(seconds)

    def volume(self, delta):
        vol = self.video_player_widget.change_volume(delta)
        if vol is not None: self.speak(f"Volume {int(vol*100)}%")

    def announce_position(self):
        pos = self.video_player_widget.get_position_str()
        if pos: self.speak(f"Current position: {pos}")

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
        info, url = item.text(), item.data(Qt.ItemDataRole.UserRole)
        favorites = self.settings_manager.get("favorites", [])
        if any(f["url"] == url for f in favorites):
            self.speak("Already in favorites")
            return
        favorites.append({"info": info, "url": url})
        self.settings_manager.set("favorites", favorites)
        self.speak("Added to favorites")

    def view_video_info(self):
        item = self.results_list.currentItem()
        if not item:
            self.speak("No video selected")
            return
        url = item.data(Qt.ItemDataRole.UserRole)
        self.speak("Fetching video info...")
        self.getinfo_sig.emit(url)
        self.getcomments_sig.emit(url)

    def download_video_action(self):
        item = self.results_list.currentItem()
        if item:
            self.download_sig.emit(item.data(Qt.ItemDataRole.UserRole), False, self.settings_manager.get("download_directory"))
        else:
            self.speak("No video selected")

    def download_audio_action(self):
        item = self.results_list.currentItem()
        if item:
            self.download_sig.emit(item.data(Qt.ItemDataRole.UserRole), True, self.settings_manager.get("download_directory"))
        else:
            self.speak("No video selected")

    def download_all_favorites(self, audio_only):
        favorites = self.settings_manager.get("favorites", [])
        if not favorites:
            self.speak("No favorites to download")
            return
        self.speak(f"Downloading {len(favorites)} favorites")
        for fav in favorites:
            self.download_sig.emit(fav["url"], audio_only, self.settings_manager.get("download_directory"))

    def show_context_menu(self, pos):
        item = self.results_list.itemAt(pos)
        if not item: return
        menu = QMenu()
        play_act = menu.addAction("Play")
        info_act = menu.addAction("View Info")
        dl_vid_act = menu.addAction("Download Video")
        dl_aud_act = menu.addAction("Download Audio")
        copy_act = menu.addAction("Copy Link")

        favorites = self.settings_manager.get("favorites", [])
        is_fav = any(f["url"] == item.data(Qt.ItemDataRole.UserRole) for f in favorites)
        fav_act = menu.addAction("Remove from Favorites" if is_fav else "Add to Favorites")

        action = menu.exec(self.results_list.mapToGlobal(pos))
        if action == play_act: self.play_video_item(item)
        elif action == info_act: self.view_video_info()
        elif action == dl_vid_act: self.download_video_action()
        elif action == dl_aud_act: self.download_audio_action()
        elif action == copy_act:
            QApplication.clipboard().setText(item.data(Qt.ItemDataRole.UserRole))
            self.speak("Link copied")
        elif action == fav_act:
            if is_fav:
                url = item.data(Qt.ItemDataRole.UserRole)
                self.settings_manager.set("favorites", [f for f in favorites if f["url"] != url])
                self.show_favorites()
                self.speak("Removed from favorites")
            else:
                self.add_current_to_favorites()

    def show_proxy_settings(self):
        dialog = ProxySettingsDialog(self, self.settings_manager.get("proxy"))
        if dialog.exec():
            new_proxy = dialog.get_proxy_settings()
            self.settings_manager.set("proxy", new_proxy)
            self.speak(f"Proxy {'enabled' if new_proxy['enabled'] else 'disabled'}")

    def change_download_dir(self):
        new_dir = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.settings_manager.get("download_directory"))
        if new_dir:
            self.settings_manager.set("download_directory", new_dir)
            self.speak(f"Download directory set to {new_dir}")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_P: self.announce_position()
        elif event.key() == Qt.Key.Key_Escape: self.show_favorites()
        elif event.key() == Qt.Key.Key_Return and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.view_video_info()
        else: super().keyPressEvent(event)

    def handle_cli_args(self):
        if self.cli_args.get("url"):
            self.search_field.setText(self.cli_args["url"])
            self.search_action()
        elif self.cli_args.get("search"):
            self.search_field.setText(self.cli_args["search"])
            self.search_action()
