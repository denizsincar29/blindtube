import sys
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QUrl, pyqtSlot, pyqtSignal, QThread
from tube import Worker
#from webbrowser import open as wopen

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

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search")
        self.search_field.returnPressed.connect(self.search)
        self.search_field.installEventFilter(self)
        layout.addWidget(self.search_field)

        self.results_list = QListWidget()
        self.results_list.itemActivated.connect(self.play_video)
        layout.addWidget(self.results_list)

        # Video player widget
        self.audio_output=QAudioOutput()
        self.video_player = QMediaPlayer()
        self.video_player.setAudioOutput(self.audio_output)
        #self.video_player.mediaStatusChanged.connect()
        self.video_widget = QVideoWidget()
        layout.addWidget(self.video_widget)

        self.worker = Worker()
        self.worker_thread = QThread()
        self.worker.search.connect(self.getsearch)
        self.worker.url.connect(self.geturl)
        self.searchsig.connect(self.worker.searchthr)
        self.urlsig.connect(self.worker.get_url)
        self.worker.moveToThread(self.worker_thread)
        self.worker_thread.start()

        # self.video_player.mediaStatusChanged.connect(self.handleStateChange)

    """
    @pyqtSlot(QMediaPlayer.MediaStatus)
    def handleStateChange(self, state):
        if state == QMediaPlayer.mediaStatus.:
            print("Playing")
        elif state == QMediaPlayer.State.PausedState:
            print("Paused")
        elif state == QMediaPlayer.State.StoppedState:
            print("Stopped")
    """

    @pyqtSlot(list)
    def getsearch(self, search_results):
        for i, video in enumerate(search_results):
            item = QListWidgetItem(video)
            item.setData(Qt.ItemDataRole.UserRole, i)  # Store the video object in the item
            self.results_list.addItem(item)



    def search(self):
        self.results_list.clear()
        query = self.search_field.text()
        # nvda speaks: searching for query
        self.searchsig.emit(query)

    def play_video(self, item: QListWidgetItem):
        self.video_player.stop()
        vid: int=item.data(Qt.ItemDataRole.UserRole)
        self.urlsig.emit(vid)

    @pyqtSlot(str)
    def geturl(self, stream_url):
        media_content = QUrl.fromUserInput(stream_url)
        self.video_player.setSource(media_content)
        self   .video_player.setVideoOutput(self.video_widget)
        self.video_player.play()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubePlayer()
    window.show()
    sys.exit(app.exec())
