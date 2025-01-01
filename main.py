import sys
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QThread, QTimer

from tube import Worker
from pyvidplayer2 import VideoPyQT

class YouTubePlayer(QMainWindow):
    searchsig=pyqtSignal(str)
    urlsig=pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube")
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        self.video_player: VideoPyQT = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)
        self.add_ui(layout)
        self.w_thread()
        self.add_menubar()


    def add_ui(self, layout):
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search")
        self.search_field.returnPressed.connect(self.search)
        self.search_field.installEventFilter(self)
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
        self.worker.url.connect(self.get_url)
        self.searchsig.connect(self.worker.searchthr)
        self.urlsig.connect(self.worker.get_url)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()


    def add_menubar(self):
        menubar=self.menuBar()
        fileMenu = menubar.addMenu('&File')
        playbackMenu = menubar.addMenu('&Playback')
        self.add_item(fileMenu,  "Download", "Ctrl+D", "download the video")
        self.add_item(fileMenu,  "Download only the audio track", "Ctrl+Shift+D", "download the video")
        self.add_item(fileMenu, "&Exit", "Ctrl+Q", "Exit the application", QApplication.instance().quit)
        self.add_item(playbackMenu, "Play / Pause", "Ctrl+Space", callback=self.playpause)
        self.add_item(playbackMenu, "Forward 5 seconds", "Ctrl+Right", callback= lambda: self.seek(True))
        self.add_item(playbackMenu, "Backward 5 seconds", "Ctrl+Left", callback=lambda: self.seek(False))
        self.add_item(playbackMenu, "Volume up", "Ctrl+Up", callback=lambda: self.volume(True))
        self.add_item(playbackMenu, "Volume down", "Ctrl+Down", callback=lambda: self.volume(False))

    def add_item(self, menu, text, shortcut=None, discryption=None, callback=None):
        act = QAction(QIcon('exit.png'), text, self)
        if shortcut is not None:
            act.setShortcut(shortcut)
        if discryption is not None:
            act.setStatusTip(discryption)
        if callback is not None:
            act.triggered.connect(callback)
        menu.addAction(act)

    def update(self):
        if self.video_player is not None:
            self.video_player.draw(self.video_widget, (0,0))

    def playpause(self):
        if self.video_player is None:
            return
        if not self.video_player.paused:
            self.video_player.pause()
        else:
            self.video_player.play()

    def seek(self, right: bool):
        if self.video_player is None:
            return
        time = 5.0 if right else -5.0
        self.video_player.seek(time = time, relative = True)

    def volume(self, up: bool):
        if self.video_player is None:
            return
        volume_step = 0.1 if up else -0.1
        volume = self.video_player.get_volume()
        volume += volume_step
        if volume < 0:
            volume = 0
        elif volume > 1:
            volume = 1
        self.video_player.set_volume(volume_step)

    @pyqtSlot(list)
    def getsearch(self, search_results):
        for i, (video, url) in enumerate(search_results):
            item = QListWidgetItem(video)
            item.setData(Qt.ItemDataRole.UserRole, url)
            self.results_list.addItem(item)

    def search(self):
        self.results_list.clear()
        query = self.search_field.text()
        # nvda speaks: searching for query
        self.searchsig.emit(query)

    def play_video(self, item: QListWidgetItem):
        if self.video_player is not None:
            self.video_player.stop()
            self.video_player.close()  # unload the video
            self.video_player = None  # for update function to not draw the video
        url = item.data(Qt.ItemDataRole.UserRole)
        # play directly the video
        self.video_player = VideoPyQT(url, 60, 1, youtube=True)
        self.video_player.play()

    # deprecated! Now the data won't pass through the worker
    @pyqtSlot(str)
    def get_url(self, stream_url):
        print("warning! This method should not be automatically called! But it is called! It is a bug!")
        self.video_player = VideoPyQT(stream_url, 60, 1, youtube=True)
        self.video_player.play()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubePlayer()
    window.show()
    sys.exit(app.exec())
