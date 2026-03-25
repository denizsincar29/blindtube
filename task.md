# Task
Read the web about how to search youtube and download videos using python in 2026 and stream on the qt main window. Then fix the existing python code that probably worked a few years ago but is now broken due to changes in the youtube API or other libraries.
Implement accessible-output3 (fork of accessible-output2) to provide screenreader messages for every action: searching for xxx, found x results, downloading video, download complete, streaming video, etc. Make sure to handle exceptions and provide appropriate messages for errors as well.
In the list of search results, display the video title and channel name.

Currently, search functionality is working, but video doesn't play. Pyvidplayer2 supports youtube after I created an issue, but IDK what library it uses.