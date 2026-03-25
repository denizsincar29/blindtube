# Task
1. The downloads folder must be %userprofile%/downloads/youtube by default, or ./downloads if the former is not accessible.
2. When pressing enter on a search result, screenreader should say loading xxx title. And when it's starts playing, it mustn't say streaming (long title), but just "playing".
3. Add context menu to the search results to play, download, or copy the link, etc.
4. Favorites: add an item in the context menu and the menubar to ad the current video to favorites. They are listed when you start the app in the search results list, or if you press escape (menu item home) to clear the search and list the favorites. They can be removed from the favorites list by right-clicking and selecting remove from favorites. There must be a menu item to download all favorites as video or audio.
5. Play a url by typing it in the search box and pressing enter. It should be added to the search results list with a thumbnail and title, and start playing immediately.
6. Command line parsing with click: make up your own syntax for the command line arguments, but it should allow the user to specify a url to play, a search query to search and play the first result, and a flag to download the first search result instead of playing it. For example:
   - `uv run main.py --play https://www.youtube.com/watch?v=dQw4w9WgXcQ`
   - `uv run main.py --search "never gonna give you up" --play`
   - `uv run main.py --search "never gonna give you up" --download`