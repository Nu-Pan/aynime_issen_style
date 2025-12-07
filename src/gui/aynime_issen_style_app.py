# Tk/CTk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD

# utils
from utils.constants import (
    APP_NAME_JP,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    WINDOW_INIT_WIDTH,
    WINDOW_INIT_HEIGHT,
    DEFAULT_FONT_FAMILY,
)
from utils.pyinstaller import resource_path
from utils.capture import *
from utils.ctk import place_window_to_display_center

# gui
from gui.frames.window_selection_frame import WindowSelectionFrame
from gui.frames.still_capture_frame import StillCaptureFrame
from gui.frames.video_capture_frame import VideoCaptureFrame
from gui.frames.version_frame import VersionFrame

# local
from gui.model.aynime_issen_style import AynimeIssenStyleModel


class AynimeIssenStyleApp(ctk.CTk, TkinterDnD.DnDWrapper):
    """
    えぃにめ一閃流奥義「一閃」 アプリケーションクラス
    """

    def __init__(self):
        """
        コンストラクタ
        """
        super().__init__()

        # tkdnd をロード
        # NOTE
        #   明示的にロード処理を呼び出さないと D&D 機能を使えない
        self.tk_dnd_version = TkinterDnD._require(self)

        # フォントを設定
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)
        self.configure(font=default_font)

        # タイトルを設定
        self.title(APP_NAME_JP)

        # アイコンを設定
        self.iconbitmap(resource_path("app.ico"))

        # 初期サイズを設定
        place_window_to_display_center(self, WINDOW_INIT_WIDTH, WINDOW_INIT_HEIGHT)

        # 最小サイズを設定
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # Model-View でいうところのモデル
        self.model = AynimeIssenStyleModel(self)

        # タブビューを追加
        self.tabview = ctk.CTkTabview(self, corner_radius=0, border_width=0)
        self.tabview.pack(fill="both", expand=True)

        # ウィンドウ選択タブを追加
        self.tabview.add(WindowSelectionFrame.UI_TAB_NAME)
        self.window_select_frame = WindowSelectionFrame(
            self.tabview.tab(WindowSelectionFrame.UI_TAB_NAME), self.model
        )
        self.window_select_frame.pack(fill="both", expand=True)

        # スチルキャプチャタブを追加
        self.tabview.add(StillCaptureFrame.UI_TAB_NAME)
        self.still_capture_frame = StillCaptureFrame(
            self.tabview.tab(StillCaptureFrame.UI_TAB_NAME), self.model
        )
        self.still_capture_frame.pack(fill="both", expand=True)

        # ビデオキャプチャタブを追加
        self.tabview.add(VideoCaptureFrame.UI_TAB_NAME)
        self.video_capture_frame = VideoCaptureFrame(
            self.tabview.tab(VideoCaptureFrame.UI_TAB_NAME),
            self.model,
        )
        self.video_capture_frame.pack(fill="both", expand=True)

        # バージョン情報タブを追加
        self.tabview.add(VersionFrame.UI_TAB_NAME)
        self.version_frame = VersionFrame(self.tabview.tab(VersionFrame.UI_TAB_NAME))
        self.version_frame.pack(fill="both", expand=True)

        # 初期選択
        self.tabview.configure(command=self.on_tab_change)
        self.tabview.set(WindowSelectionFrame.UI_TAB_NAME)

        # グローバルホットキーを設定
        self.model.global_hotkey.register(
            "I", lambda: self.tabview.set(StillCaptureFrame.UI_TAB_NAME)
        )
        self.model.global_hotkey.register(
            "K", lambda: self.tabview.set(VideoCaptureFrame.UI_TAB_NAME)
        )

    def on_tab_change(self, tab_name: str | None = None) -> None:
        """タブ切り替え時に呼ばれるコールバック"""
        current_tab_name = tab_name or self.tabview.get()
        if current_tab_name == WindowSelectionFrame.UI_TAB_NAME:
            self.window_select_frame.update_list()
