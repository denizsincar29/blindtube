import sys
from PyQt6.QtWidgets import QApplication
import click
from src.ui.main_window import MainWindow

@click.command()
@click.option('--play', help='URL to play')
@click.option('--search', help='Search query')
@click.option('--play-first', is_flag=True, help='Play first search result')
@click.option('--download', is_flag=True, help='Download the (first) result')
@click.option('--close-on-completion', is_flag=True, help='Close app when done')
def main(play, search, play_first, download, close_on_completion):
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
