import os
import sys

import customtkinter as ctk
from tkinter import PhotoImage

from window_selection_frame import WindowSelectionFrame
from capture_frame import CaptureFrame
from version_frame import VersionFrame
from aynime_issen_style_model import CaptureMode, AynimeIssenStyleModel
from utils.constants import WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT, DEFAULT_FONT_NAME


def resource_path(relative_path: str) -> str:
    """
    ファイル relative_path のリソースパスを生成する。
    「直接実行した場合」と「 pyinstaller で生成した exe から実行された場合」の差異を吸収するための関数。

    Args:
        relative_path (str): 入力ファイル相対パス

    Returns:
        str: リソースパス
            直接実行時は relative_path がそのまま返される。
            pyinstaller で生成した exe から実行された場合は処理されたパスが返される。

    """
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller バンドル実行時
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        return os.path.join(os.path.abspath("."), relative_path)


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
        self.title("えぃにめ一閃流奥義「一閃」")

        # アイコンを設定
        self.iconbitmap(resource_path("app.ico"))

        # 初期位置を設定
        self.geometry(f"{WINDOW_MIN_WIDTH*2}x{WINDOW_MIN_HEIGHT*2}")

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
        self.capture_frame = VersionFrame(self.tabview.tab("バージョン"))
        self.capture_frame.pack(fill="both", expand=True)

        # 初期選択
        self.tabview.set("構え")
