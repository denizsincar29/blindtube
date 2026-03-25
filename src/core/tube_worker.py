import yt_dlp
from PyQt6.QtCore import QObject, pyqtSignal as Signal, pyqtSlot as Slot
import json
import os

class TubeWorker(QObject):
    search_finished = Signal(list, bool) # Results, is_append
    url_received = Signal(str)
    status_message = Signal(str)
    video_info_received = Signal(dict)
    comments_received = Signal(list, str) # comments, video_id

    def __init__(self, settings_manager=None) -> None:
        super().__init__()
        self.results = []
        self.settings_manager = settings_manager
        self._setup_ydl_opts()

    def _setup_ydl_opts(self):
        self.ydl_opts = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
        }
        if self.settings_manager:
            proxy = self.settings_manager.get("proxy", {})
            if proxy.get("enabled") and proxy.get("url"):
                self.ydl_opts['proxy'] = proxy.get("url")

    def _format_info(self, entry):
        title = entry.get('title', 'Unknown Title')
        channel = entry.get('uploader', 'Unknown Channel')
        duration = entry.get('duration')
        video_id = entry.get('id')
        url = entry.get('webpage_url') or f"https://www.youtube.com/watch?v={video_id}"

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

    @Slot(str, int)
    def search_videos(self, query: str, start_index: int = 1):
        print(f"Searching for: {query}, starting from: {start_index}")
        self._setup_ydl_opts()
        search_opts = self.ydl_opts.copy()
        search_opts.update({
            'extract_flat': True,
            'force_generic_extractor': True,
        })

        with yt_dlp.YoutubeDL(search_opts) as ydl:
            try:
                # Use playlist_items to simulate pagination if needed, or just fetch more
                # For simplicity, we'll fetch 10 results at a time.
                # ytsearch can take a range: ytsearch10:query
                # To get 11-20, we might need a different approach or just fetch more and slice.
                # Actually, ytsearch doesn't support offset easily.
                # Let's try to fetch N results and return the new ones.
                end_index = start_index + 9
                search_query = f"ytsearch{end_index}:{query}"
                info = ydl.extract_info(search_query, download=False)

                if 'entries' in info:
                    new_entries = info['entries'][start_index-1:]
                    formatted_results = [self._format_info(entry) for entry in new_entries]
                    self.search_finished.emit(formatted_results, start_index > 1)
                    if not formatted_results:
                         self.status_message.emit("No more results found")
                    elif start_index == 1:
                         self.status_message.emit(f"Found {len(formatted_results)} results")
                else:
                    self.search_finished.emit([], start_index > 1)
                    self.status_message.emit("No results found")
            except Exception as e:
                print(f"Search error: {e}")
                self.status_message.emit(f"Search error: {str(e)}")
                self.search_finished.emit([], start_index > 1)

    @Slot(str)
    def get_video_info(self, url: str):
        print(f"Fetching info for: {url}")
        self._setup_ydl_opts()
        opts = self.ydl_opts.copy()
        # Not extract_flat because we need description and maybe comments
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                info_str, final_url = self._format_info(info)
                self.video_info_received.emit({
                    "info": info_str,
                    "url": final_url,
                    "description": info.get("description", "No description"),
                    "id": info.get("id")
                })
            except Exception as e:
                print(f"Info error: {e}")
                self.status_message.emit(f"Error fetching video info: {str(e)}")

    @Slot(str)
    def get_comments(self, url: str):
        print(f"Fetching comments for: {url}")
        self._setup_ydl_opts()
        opts = self.ydl_opts.copy()
        opts.update({
            'getcomments': True,
            'extract_flat': False,
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                comments = info.get("comments", [])
                video_id = info.get("id")
                self.comments_received.emit(comments, video_id)
                self.status_message.emit(f"Fetched {len(comments)} comments")
            except Exception as e:
                print(f"Comments error: {e}")
                self.status_message.emit(f"Error fetching comments: {str(e)}")

    @Slot(str, bool, str)
    def download_video(self, url, audio_only=False, download_dir=None):
        try:
            self._setup_ydl_opts()
            if not download_dir:
                 download_dir = self.settings_manager.get('download_directory', 'downloads/youtube')

            if not os.path.exists(download_dir):
                os.makedirs(download_dir)

            opts = self.ydl_opts.copy()
            opts.update({
                'format': 'bestaudio/best' if audio_only else 'best',
                'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            })
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
