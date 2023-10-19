import webbrowser
import pytube

yt=pytube.YouTube("https://www.youtube.com/watch?v=Jd1PvOdAdXY")
streams=yt.streams
print(f'total streams: {len(streams)}')
vids=streams.filter(only_audio=False, only_video=False, file_extension="mp4")
print(f'mp4 streams: {len(vids)}')
webbrowser.open(vids.first().url)