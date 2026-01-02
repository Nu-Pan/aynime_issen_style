# TK/CTk
import customtkinter as ctk

# utils
from utils.capture import *
from utils.windows import GlobalHotkey

# model
from gui.model.contents_cache import ImageModel, VideoModel, ResizeMode


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
