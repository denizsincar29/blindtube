import wx
import wx.media
import pafy
from webbrowser import open as wopen
from youtubesearchpython import VideosSearch
from accessible_output2.outputs import auto


class YoutubePlayer(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, None, title="Youtube Player", size=(640, 480))
        self.panel = wx.Panel(self)
        self.edit_box = wx.TextCtrl(self.panel, style=wx.TE_PROCESS_ENTER, pos=(10, 10), size=(200, 20))
        self.list_box = wx.ListCtrl(self.panel, pos=(10, 40), size=(200, 400), style=wx.LC_SINGLE_SEL|wx.LC_REPORT)
        self.list_box.InsertColumn(0, 'Results')
        #self.media_player = wx.media.MediaCtrl(self.panel)
        #self.media_player.Bind(wx.media.EVT_MEDIA_LOADED, self.on_media_loaded)

        self.edit_box.Bind(wx.EVT_TEXT_ENTER, self.on_search)
        self.output = auto.Auto()
        self.speak=self.output.output
        self.results={}

    def new_item(self, id, text):
        item = wx.ListItem()
        item.SetId(id)
        item.SetText(text)
        self.list_box.InsertItem(item)


    def on_search(self, event):
        query = self.edit_box.GetValue()
        self.output.output("Searching for " + query)
        search = VideosSearch(query, limit=10)
        items = search.result()["result"]
        video_ids = [item["id"] for item in items]
        video_titles = [item["title"] for item in items]
        self.list_box.DeleteAllItems()
        for i, item in enumerate(video_titles):
            self.new_item(i, item)

        #self.media_player.Stop()
        self.results={k: v for k, v in zip(video_titles, video_ids)}
        self.list_box.Focus(0)
    '''
    def on_media_loaded(self, event):
        print("loaded")
        self.output.output("Playing")
        self.media_player.Play()
    '''
    def play_video(self, video_id):
        url = f"https://www.youtube.com/watch?v={video_id}"
        video = pafy.new(url)
        best = video.getbest(preftype="mp4")
        play_url = best.url
        #wopen(play_url)
        self.media.LoadUri(play_url)
        #mpv.MPV().play(play_url)

    def on_list_select(self, event):
        self.output.output("loading")
        video_id = self.results[event.GetText()]
        self.play_video(video_id)


    def bind_list_events(self):
        self.list_box.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_list_select)

        
if __name__ == "__main__":
    app = wx.App()
    player = YoutubePlayer()
    player.bind_list_events()
    player.Show()
    app.MainLoop()