# std
from pathlib import Path
from datetime import datetime

# Tk/CTk
import customtkinter as ctk
import tkinter.messagebox as mb
from tkinter import Event

# utils
from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.pil import (
    AspectRatio,
    Resolution,
    integrated_save_image,
    IntegratedImage,
)
from utils.windows import file_to_clipboard, register_global_hotkey_handler
from utils.constants import APP_NAME_JP, NIME_DIR_PATH
from utils.ctk import show_notify

# gui
from gui.widgets.still_frame import StillLabel
from gui.widgets.size_pattern_selection_frame import (
    SizePatternSlectionFrame,
)

# local
from aynime_issen_style_model import AynimeIssenStyleModel


class StillCaptureFrame(ctk.CTkFrame):
    """
    スチル画像のキャプチャ操作を行う CTk フレーム
    """

    def __init__(self, master, model: AynimeIssenStyleModel, **kwargs):
        """
        コンストラクタ

        Args:
            master (_type_): 親ウィジェット
            model (AynimeIssenStyleModel): モデル
        """
        super().__init__(master, **kwargs)

        # 参照を保存
        self.model = model

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # プレビューラベル兼キャプチャボタン
        self.preview_label = StillLabel(self)
        self.preview_label.set_contents(text="Click Here or Ctrl+Alt+P")
        self.preview_label.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.preview_label.bind("<Button-1>", self.on_preview_label_click)

        # グローバルホットキーを登録
        register_global_hotkey_handler(self, self.on_preview_label_click, None)

        # 解像度選択フレーム
        self._size_pattern_selection_frame = SizePatternSlectionFrame(
            self,
            self.on_resolution_changes,
            AspectRatio.E_RAW,
            Resolution.E_RAW,
            [AspectRatio.E_RAW, AspectRatio.E_16_9, AspectRatio.E_4_3],
            [
                Resolution.E_RAW,
                Resolution.E_VGA,
                Resolution.E_HD,
                Resolution.E_FHD,
                Resolution.E_4K,
            ],
        )
        self._size_pattern_selection_frame.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

    def on_preview_label_click(self, event: Event) -> None:
        """
        プレビューラベルクリックイベントハンドラ

        Args:
            event (_type_): イベントオブジェクト
        """
        # まずはキャプチャ
        try:
            pil_raw_capture_image = self.model.capture()
        except Exception as e:
            mb.showerror(
                APP_NAME_JP,
                f"キャプチャに失敗。多分キャプチャ対象のディスプレイ・ウィンドウの選択を忘れてるよ。\n{e.args}",
            )
            return

        # 統合画像を生成
        capture_image = IntegratedImage(pil_raw_capture_image)

        # 指定サイズにリサイズの上プレビュー
        self.preview_label.set_contents(image=capture_image)

        # キャプチャをローカルにファイル保存する
        nime_file_path = integrated_save_image(capture_image)
        if not isinstance(nime_file_path, Path):
            raise TypeError(
                f"Expected Path, got {type(nime_file_path)}. "
                "integrated_save_image should return a single Path."
            )

        # 保存したファイルをクリップボードに乗せる
        file_to_clipboard(nime_file_path)

        # クリップボード転送完了通知
        show_notify(
            self,
            "「一閃」\nクリップボード転送完了",
            on_click_handler=self.on_preview_label_click,
        )

    def on_resolution_changes(self, aspect_ratio: AspectRatio, resolution: Resolution):
        """
        解像度が変更された時に呼び出される

        Args:
            aspect_ratio (AspectRatio): アスペクト比
            resolution (Resolution): 解像度
        """
        self._aspect_ratio = aspect_ratio
        self._resolution = resolution
