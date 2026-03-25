from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QCheckBox, QPushButton, QFormLayout)
from PyQt6.QtCore import Qt

class ProxySettingsDialog(QDialog):
    def __init__(self, parent=None, initial_proxy=None):
        super().__init__(parent)
        self.setWindowTitle("Proxy Settings")
        self.initial_proxy = initial_proxy or {"enabled": False, "url": ""}

        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.enabled_cb = QCheckBox("Enable Proxy")
        form_layout.addRow(self.enabled_cb)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://user:pass@host:port")
        form_layout.addRow("Proxy URL:", self.url_edit)

        # Helper fields that update the URL
        self.type_edit = QLineEdit()
        self.type_edit.setPlaceholderText("http/https/socks5")
        self.type_edit.textChanged.connect(self._update_url_from_fields)
        form_layout.addRow("Type:", self.type_edit)

        self.host_edit = QLineEdit()
        self.host_edit.textChanged.connect(self._update_url_from_fields)
        form_layout.addRow("Host:", self.host_edit)

        self.port_edit = QLineEdit()
        self.port_edit.textChanged.connect(self._update_url_from_fields)
        form_layout.addRow("Port:", self.port_edit)

        self.user_edit = QLineEdit()
        self.user_edit.textChanged.connect(self._update_url_from_fields)
        form_layout.addRow("Username:", self.user_edit)

        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.textChanged.connect(self._update_url_from_fields)
        form_layout.addRow("Password:", self.pass_edit)

        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        buttons_layout.addStretch()
        buttons_layout.addWidget(save_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)

    def _load_values(self):
        self.enabled_cb.setChecked(self.initial_proxy.get("enabled", False))
        self.url_edit.setText(self.initial_proxy.get("url", ""))

    def _update_url_from_fields(self):
        # Only update if the user is typing in the specific fields, not the URL box directly
        # But for simplicity, we'll just allow both.
        # If any of these are filled, we construct the URL.
        p_type = self.type_edit.text().strip()
        host = self.host_edit.text().strip()
        port = self.port_edit.text().strip()
        user = self.user_edit.text().strip()
        password = self.pass_edit.text().strip()

        if host:
            url = ""
            if p_type:
                url += f"{p_type}://"
            else:
                url += "http://"

            if user:
                url += user
                if password:
                    url += f":{password}"
                url += "@"

            url += host
            if port:
                url += f":{port}"

            self.url_edit.setText(url)

    def get_proxy_settings(self):
        return {
            "enabled": self.enabled_cb.isChecked(),
            "url": self.url_edit.text().strip()
        }
