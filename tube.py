from PyQt6.QtCore import QThread, QObject, pyqtSignal as Signal, pyqtSlot as Slot
import pytube

class Worker(QObject):
    search=Signal(list)
    url=Signal(str)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.tubes=[]

    @Slot(str)
    def searchthr(self, query: str):
        self.tubes=pytube.Search(query).results
        self.search.emit([i.title for i in self.tubes])

    @Slot(int)
    def get_url(self, yt):
        self.url.emit(self.tubes[yt].streams.filter(only_video=False, only_audio=False, file_extension="mp4").first().url)

