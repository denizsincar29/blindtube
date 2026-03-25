import yt_dlp
from PyQt6.QtCore import QThread, QObject, pyqtSignal as Signal, pyqtSlot as Slot
import json
import os

class Worker(QObject):
    search = Signal(list)
    url = Signal(str)
    status_message = Signal(str)
    video_info = Signal(dict)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.results = []
        self.ydl_opts = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
        }

    def _format_info(self, entry):
        title = entry.get('title', 'Unknown Title')
        channel = entry.get('uploader', 'Unknown Channel')
        duration = entry.get('duration')
        video_id = entry.get('id')
        url = entry.get('webpage_url') or f"https://www.youtube.com/watch?v={video_id}"

        # Better format for screenreaders and blind users
        info_str = f"{title} by {channel}"
        if duration:
            try:
                m, s = divmod(int(duration), 60)
                h, m = divmod(m, 60)
                duration_str = f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:d}:{s:02d}"
                info_str += f" ({duration_str})"
            except (ValueError, TypeError):
                pass
        return info_str, url

    @Slot(str)
    def searchthr(self, query: str):
        print(f"Searching for: {query}")
        search_opts = {
            'format': 'best',
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': True,
        }
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            try:
                # Search for 10 results
                search_query = f"ytsearch10:{query}"
                info = ydl.extract_info(search_query, download=False)
                if 'entries' in info:
                    self.results = info['entries']
                    formatted_results = [self._format_info(entry) for entry in self.results]
                    self.search.emit(formatted_results)
                    self.status_message.emit(f"Found {len(formatted_results)} results")
                else:
                    self.search.emit([])
                    self.status_message.emit("No results found")
            except Exception as e:
                print(f"Search error: {e}")
                self.status_message.emit(f"Search error: {str(e)}")
                self.search.emit([])

    @Slot(str)
    def get_video_info(self, url: str):
        print(f"Fetching info for: {url}")
        opts = {
            'format': 'best',
            'quiet': True,
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                info_str, final_url = self._format_info(info)
                self.video_info.emit({"info": info_str, "url": final_url})
            except Exception as e:
                print(f"Info error: {e}")
                self.status_message.emit(f"Error fetching video info: {str(e)}")

    @Slot(str, bool, str)
    def download_video(self, url, audio_only=False, download_dir=None):
        try:
            if not download_dir:
                try:
                    with open('settings.json', 'r') as f:
                        settings = json.load(f)
                    download_dir = settings.get('download_directory', 'downloads/youtube')
                except (FileNotFoundError, json.JSONDecodeError):
                    download_dir = 'downloads/youtube'

            if not os.path.exists(download_dir):
                os.makedirs(download_dir)

            opts = {
                'format': 'bestaudio/best' if audio_only else 'best',
                'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
                'quiet': True,
            }
            if audio_only:
                opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]

            self.status_message.emit("Downloading video..." if not audio_only else "Downloading audio...")
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.status_message.emit("Download complete")
        except Exception as e:
            print(f"Download error: {e}")
            self.status_message.emit(f"Download error: {str(e)}")

    # get the youtube com video url
    @Slot(int)
    def get_url(self, index):
        if 0 <= index < len(self.results):
            video_id = self.results[index].get('id')
            url = f"https://www.youtube.com/watch?v={video_id}"
            self.url.emit(url)
