import wx
import wx.media

class VideoPlayer(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title, wx.DefaultPosition, wx.Size(440, 350))

        # Creating the GUI for the player window
        panel = wx.Panel(self, -1)

        # Creating the media player and video playback screen
        self.mediaPlayer = wx.media.MediaCtrl(panel, wx.ID_ANY, szBackend=wx.media.MEDIABACKEND_REALPLAYER)
        self.mediaPlayer.SetPlaybackRate(1.0)

        # Creating the control buttons
        playBtn = wx.Button(panel, wx.ID_ANY, "Play")
        playBtn.Bind(wx.EVT_BUTTON, self.OnPlay)

        pauseBtn = wx.Button(panel, wx.ID_ANY, "Pause")
        pauseBtn.Bind(wx.EVT_BUTTON, self.OnPause)

        stopBtn = wx.Button(panel, wx.ID_ANY, "Stop")
        stopBtn.Bind(wx.EVT_BUTTON, self.OnStop)

        # Creating the sizer to organize and layout the buttons
        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.Add(playBtn, 0, wx.ALL, 5)
        buttonSizer.Add(pauseBtn, 0, wx.ALL, 5)
        buttonSizer.Add(stopBtn, 0, wx.ALL, 5)

        # Creating the sizer to layout the media player and control buttons
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(self.mediaPlayer, 1, wx.EXPAND | wx.ALL, 5)
        mainSizer.Add(buttonSizer, 0, wx.CENTER)

        panel.SetSizer(mainSizer)
        self.Show(True)

    def OnPlay(self, event):
        # Stream the video from a URL
        inputUrl = "https://www.youtube.com/watch?v=NwzLGx8klcc"
        media = wx.media.MediaCtrl.GetPlayer(self.mediaPlayer)
        media.Load(inputUrl)
        self.mediaPlayer.Play()
        
    def OnPause(self, event):
        # Pause the video
        self.mediaPlayer.Pause()

    def OnStop(self, event):
        # Stop the video
        self.mediaPlayer.Stop()

app = wx.App()
VideoPlayer(None, -1, "Simple wxPython Videoplayer")
app.MainLoop()
