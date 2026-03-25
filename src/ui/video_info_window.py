from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTextEdit,
                             QListWidget, QListWidgetItem, QLabel, QSplitter, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from webbrowser import open as open_browser
import re

class VideoInfoWindow(QDialog):
    fetch_replies_sig = pyqtSignal(str, str) # video_url, comment_id

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
        desc_layout.addWidget(QLabel("Description:"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setReadOnly(True)
        self.desc_edit.setPlainText(description)
        self.desc_edit.mousePressEvent = self._handle_desc_click
        self.desc_edit.keyPressEvent = self._handle_desc_keypress
        desc_layout.addWidget(self.desc_edit)
        splitter.addWidget(desc_widget)

        # Comments
        comm_widget = QWidget()
        comm_layout = QVBoxLayout(comm_widget)
        label = QLabel("Comments (Press Enter on a comment to view replies):")
        comm_layout.addWidget(label)
        self.comments_list = QListWidget()
        self.comments_list.itemActivated.connect(self._on_comment_activated)
        comm_layout.addWidget(self.comments_list)
        splitter.addWidget(comm_widget)

        layout.addWidget(splitter)

    def _display_comments(self, comments, is_replies=False):
        if not is_replies:
            self.comments_list.clear()

        for comment in comments:
            author = comment.get("author", "Unknown")
            text = comment.get("text", "")
            like_count = comment.get("like_count", 0)

            info = f"{author}: {text} ({like_count} likes)"
            item = QListWidgetItem(info)
            item.setData(Qt.ItemDataRole.UserRole, comment)
            self.comments_list.addItem(item)

    def _on_comment_activated(self, item):
        comment = item.data(Qt.ItemDataRole.UserRole)
        # Check for URLs in comment
        urls = re.findall(r'(https?://[^\s]+)', comment.get("text", ""))
        if urls:
            for url in urls:
                open_browser(url)
            return

        replies = comment.get("replies", [])
        if replies:
            # If we already have replies, maybe just show them or open a new dialog?
            # Requirement says "click on them to view replies".
            # Let's show them in a nested way or just clear and show?
            # Simple approach: New dialog for replies
            reply_win = VideoInfoWindow(self, "Replies", f"Replies to {comment.get('author')}", replies, self.video_url)
            reply_win.exec()

    def _handle_desc_click(self, event):
        # Very basic URL detection on click for the description
        cursor = self.desc_edit.cursorForPosition(event.pos())
        cursor.select(cursor.SelectionType.WordUnderCursor)
        # This is not perfect, let's try to find URL in the whole text if it's a URL
        text = self.desc_edit.toPlainText()
        urls = re.findall(r'(https?://[^\s]+)', text)
        # Check if clicked position is near any URL?
        # For simplicity, if user clicks description, we'll just open first URL found for now
        # Better: Search for URL around the cursor
        pos = cursor.position()
        for url in urls:
            start = text.find(url)
            if start <= pos <= start + len(url):
                open_browser(url)
                return

        # Fallback to default behavior
        QTextEdit.mousePressEvent(self.desc_edit, event)

    def _handle_desc_keypress(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Check for URLs in description
            text = self.desc_edit.toPlainText()
            urls = re.findall(r'(https?://[^\s]+)', text)
            if urls:
                # Open first URL found in description when Enter is pressed
                open_browser(urls[0])
                return

        QTextEdit.keyPressEvent(self.desc_edit, event)
