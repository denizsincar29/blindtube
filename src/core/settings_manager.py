import os
import sys
import json
import shutil


def get_app_data_dir(app_name="blindtube"):
    """Return the OS-appropriate per-user config directory for the app."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, app_name)


class SettingsManager:
    DEFAULT_DIR = os.path.join(os.path.expanduser("~"), "Downloads", "youtube")

    def __init__(self, settings_file=None):
        if settings_file is None:
            app_dir = get_app_data_dir()
            try:
                os.makedirs(app_dir, exist_ok=True)
            except Exception:
                app_dir = os.getcwd()
            settings_file = os.path.join(app_dir, "settings.json")

            # Migrate a legacy settings.json sitting next to the script/cwd,
            # if we don't already have one in the appdata location.
            legacy_file = os.path.join(os.getcwd(), "settings.json")
            if not os.path.exists(settings_file) and os.path.exists(legacy_file):
                try:
                    shutil.copy2(legacy_file, settings_file)
                except Exception:
                    pass

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
        os.makedirs(os.path.dirname(self.settings_file) or ".", exist_ok=True)
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()
