import customtkinter as ctk

from window_selection_frame import WindowSelectionFrame
from capture_frame import CaptureFrame
from aynime_issen_style_model import (
    CaptureMode,
    AynimeIssenStyleModel
)
from constants import (
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
    DEFAULT_FONT_NAME
)


class AynimeIssenStyleApp(ctk.CTk):
    '''
    えぃにめ一閃流奥義
    アプリケーションクラス
    '''


    def __init__(self):
        '''
        コンストラクタ
        '''
        super().__init__()

        # フォントを設定
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)
        self.configure(font=default_font)

        # タイトルを設定
        self.title("えぃにめ一閃流奥義　――キャプチャ――")

        # 初期位置を設定
        self.geometry(f"{WINDOW_MIN_WIDTH}x{WINDOW_MIN_HEIGHT}")

        # Model-View でいうところのモデル
        self.model = AynimeIssenStyleModel()
        self.model.change_capture_mode(CaptureMode.DXCAM)

        # タブビューを追加
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # ウィンドウ選択タブを追加
        self.tabview.add("構え")
        self.select_frame = WindowSelectionFrame(
            self.tabview.tab("構え"),
            self.model
        )
        self.select_frame.pack(fill="both", expand=True)

        # キャプチャタブを追加
        self.tabview.add("キャプチャ")
        self.capture_frame = CaptureFrame(
            self.tabview.tab("キャプチャ"),
            self.model
        )
        self.capture_frame.pack(fill="both", expand=True)

        # 初期選択
        self.tabview.set("構え")
