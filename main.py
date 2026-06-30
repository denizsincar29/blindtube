import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
import click
from src.core.settings_manager import get_app_data_dir
from src.ui.main_window import MainWindow


def setup_logging():
    """Log to a file in the appdata dir. print() is invisible in a
    --windowed PyInstaller build, so this is the only way to diagnose
    issues (e.g. screen reader output failing to initialize) post-build."""
    log_dir = get_app_data_dir()
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "blindtube.log")
    except Exception:
        log_file = "blindtube.log"

    logging.basicConfig(
        filename=log_file,
        filemode="a",
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.info("---- blindtube starting ----")


@click.command()
@click.option('--play', help='URL to play')
@click.option('--search', help='Search query')
@click.option('--play-first', is_flag=True, help='Play first search result')
@click.option('--download', is_flag=True, help='Download the (first) result')
@click.option('--close-on-completion', is_flag=True, help='Close app when done')
def main(play, search, play_first, download, close_on_completion):
    setup_logging()
    app = QApplication(sys.argv)

    cli_args = {
        "url": play,
        "search": search,
        "play_first": play_first or (play is not None),
        "download": download,
        "close_on_completion": close_on_completion
    }

    window = MainWindow(cli_args)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
