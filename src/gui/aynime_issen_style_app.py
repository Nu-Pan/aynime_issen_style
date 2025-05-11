import os
import sys

import customtkinter as ctk
from tkinter import PhotoImage

from window_selection_frame import WindowSelectionFrame
from capture_frame import CaptureFrame
from version_frame import VersionFrame
from aynime_issen_style_model import CaptureMode, AynimeIssenStyleModel
from utils.constants import (
    APP_NAME_JP,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    DEFAULT_FONT_NAME,
)
from utils.pyinstaller import resource_path


class AynimeIssenStyleApp(ctk.CTk):
    """
    えぃにめ一閃流奥義「一閃」 アプリケーションクラス
    """

    def __init__(self):
        """
        コンストラクタ
        """
        super().__init__()

        # フォントを設定
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)
        self.configure(font=default_font)

        # タイトルを設定
        self.title(APP_NAME_JP)

        # アイコンを設定
        self.iconbitmap(resource_path("app.ico"))

        # 初期サイズを設定
        self.geometry(f"{WINDOW_MIN_WIDTH}x{WINDOW_MIN_HEIGHT}")

        # 最小サイズを設定
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # Model-View でいうところのモデル
        self.model = AynimeIssenStyleModel()
        self.model.change_capture_mode(CaptureMode.DXCAM)

        # タブビューを追加
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True)

        # ウィンドウ選択タブを追加
        self.tabview.add("構え")
        self.select_frame = WindowSelectionFrame(self.tabview.tab("構え"), self.model)
        self.select_frame.pack(fill="both", expand=True)

        # キャプチャタブを追加
        self.tabview.add("「一閃」")
        self.capture_frame = CaptureFrame(self.tabview.tab("「一閃」"), self.model)
        self.capture_frame.pack(fill="both", expand=True)

        # バージョン情報タブを追加
        self.tabview.add("バージョン")
        self.version_frame = VersionFrame(self.tabview.tab("バージョン"))
        self.version_frame.pack(fill="both", expand=True)

        # 初期選択
        self.tabview.set("構え")
