import time
from pytube import YouTube, Search  # pafy and youtubesearchpython goes to hell!
from prompt_toolkit import print_formatted_text as print, prompt
from prompt_toolkit.completion import ThreadedCompleter, Completer, Completion
from prompt_toolkit.validation import Validator
from webbrowser import open as wopen
from vlc import MediaPlayer


class YTSearchCompleter(Completer):
    def get_completions(self, document, event):
        # with open("type.log", "w") as f: f.write(repr(document.text))
        dt=Search(document.text)
        return (Completion(i, start_position=-len(document.text)) for i in dt.completion_suggestions)

sr=Search(prompt("Search: > ", completer=ThreadedCompleter(YTSearchCompleter()), complete_while_typing=False, complete_in_thread=False, validator=Validator.from_callable(lambda x: len(x)>3, "Error! Search must contain more than 3 characters!"), validate_while_typing=False))

print(len(sr.results))
astream=sr.results[0].streams.filter(file_extension="mp4")
#audiostream="http://us2.internet-radio.com:8443/stream"
#astream[-1].download()
audiostream=astream[-1].url
player=MediaPlayer(audiostream)
player.play()
time.sleep(1)
try:
    while player.is_playing():
        pass
except KeyboardInterrupt: pass
except Exception as e:
    raise(e)
finally:
    player.stop()
