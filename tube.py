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
        print(query)
        self.tubes=pytube.Search(query).results
        self.search.emit([(i.title, f"https://youtube.com/watch?v={i.video_id}") for i in self.tubes])

    # this is the old geturl method, from now on pyvidplayer2 will handle the youtube url itself
    @Slot(int)
    def get_stream(self, yt):
        self.url.emit(self.tubes[yt].streams.filter(only_video=False, only_audio=False, file_extension="mp4").first().url)

    # get the youtube com video url
    @Slot(int)
    def get_url(self, yt):
        self.url.emit(self.tubes[yt].url)
