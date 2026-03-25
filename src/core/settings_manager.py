import os
import json

class SettingsManager:
    DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "youtube")

    def __init__(self, settings_file="settings.json"):
        self.settings_file = settings_file
        self.settings = self.load_settings()

    def load_settings(self):
        if not os.path.exists(self.DEFAULT_DIR):
            try:
                os.makedirs(self.DEFAULT_DIR)
            except Exception:
                self.DEFAULT_DIR = os.path.join(os.getcwd(), "downloads")

        if not os.path.exists(self.settings_file):
            settings = {
                "download_directory": self.DEFAULT_DIR,
                "favorites": [],
                "proxy": {
                    "enabled": False,
                    "url": ""
                }
            }
            self.save_settings(settings)
            return settings
        else:
            try:
                with open(self.settings_file, "r") as f:
                    settings = json.load(f)
                if "favorites" not in settings:
                    settings["favorites"] = []
                if "download_directory" not in settings:
                    settings["download_directory"] = self.DEFAULT_DIR
                if "proxy" not in settings:
                    settings["proxy"] = {"enabled": False, "url": ""}
                return settings
            except Exception:
                return {
                    "download_directory": self.DEFAULT_DIR,
                    "favorites": [],
                    "proxy": {"enabled": False, "url": ""}
                }

    def save_settings(self, settings=None):
        if settings:
            self.settings = settings
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()
