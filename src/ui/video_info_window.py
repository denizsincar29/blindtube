from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTextBrowser,
                             QListWidget, QListWidgetItem, QLabel, QSplitter, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from webbrowser import open as open_browser
import re

class VideoInfoWindow(QDialog):
    def __init__(self, parent=None, title="Video Info", description="", comments=None, video_url=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(800, 600)
        self.video_url = video_url
        self.comments_data = comments or []

        self._setup_ui(description)
        self._display_comments(self.comments_data)

    def _setup_ui(self, description):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Description
        desc_widget = QWidget()
        desc_layout = QVBoxLayout(desc_widget)
        desc_layout.addWidget(QLabel("Description (Press Enter on links):"))
        self.desc_browser = QTextBrowser()
        self.desc_browser.setOpenExternalLinks(True)
        # Convert plain text URLs to HTML links for QTextBrowser
        html_desc = self._linkify(description)
        self.desc_browser.setHtml(f"<pre style='white-space: pre-wrap;'>{html_desc}</pre>")
        desc_layout.addWidget(self.desc_browser)
        splitter.addWidget(desc_widget)

        # Comments
        comm_widget = QWidget()
        comm_layout = QVBoxLayout(comm_widget)
        comm_layout.addWidget(QLabel("Comments (Enter to view replies or open links):"))
        self.comments_list = QListWidget()
        self.comments_list.itemActivated.connect(self._on_comment_activated)
        comm_layout.addWidget(self.comments_list)
        splitter.addWidget(comm_widget)

        layout.addWidget(splitter)

    def _linkify(self, text):
        return re.sub(r'(https?://[^\s]+)', r'<a href="\1">\1</a>', text)

    def _display_comments(self, comments):
        self.comments_list.clear()
        for comment in comments:
            author = comment.get("author", "Unknown")
            text = comment.get("text", "")
            likes = comment.get("like_count", 0)

            info = f"{author}: {text} ({likes} likes)"
            item = QListWidgetItem(info)
            item.setData(Qt.ItemDataRole.UserRole, comment)
            self.comments_list.addItem(item)

    def _on_comment_activated(self, item):
        comment = item.data(Qt.ItemDataRole.UserRole)
        urls = re.findall(r'(https?://[^\s]+)', comment.get("text", ""))
        if urls:
            for url in urls: open_browser(url)
            return

        replies = comment.get("replies", [])
        if replies:
            reply_win = VideoInfoWindow(self, "Replies", f"Replies to {comment.get('author')}", replies, self.video_url)
            reply_win.exec()
