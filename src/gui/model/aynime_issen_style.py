# TK/CTk
import customtkinter as ctk

# utils
from utils.capture import *
from utils.windows import GlobalHotkey
from utils.user_properties import UserProperties
from utils.ffmpeg import FFmpeg

# model
from gui.model.contents_cache import ImageModel, VideoModel


class AynimeIssenStyleModel:
    """
    えぃにめ一閃流奥義「一閃」のモデル
    """

    def __init__(self, ctk_app: ctk.CTk) -> None:
        """
        コンストラクタ
        """
        self.global_hotkey = GlobalHotkey(ctk_app)
        self.stream = CaptureStream()
        self.window_selection_image = ImageModel()
        self.still = ImageModel()
        self.video = VideoModel()
        self.foreign = VideoModel()
        self.user_properties = UserProperties()
        self.ffmpeg = FFmpeg()

    def close(self):
        """
        後始末
        """
        self.stream.release()
        self.user_properties.close()
