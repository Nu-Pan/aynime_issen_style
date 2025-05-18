import warnings
from pathlib import Path
from datetime import datetime
from typing import cast, Tuple, List
import re

from PIL import Image, ImageTk

import tkinter as tk
from tkinter import Event
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent

from aynime_issen_style_model import AynimeIssenStyleModel
from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.pil import (
    isotropic_downscale_image_in_rectangle,
    save_pil_image_to_jpeg_file,
)
from utils.windows import file_to_clipboard, register_global_hotkey_handler
from gui.widgets.thumbnail_bar import ThumbnailBar
from gui.widgets.animation_label import AnimationLabel


class AnimationCaptureFrame(ctk.CTkFrame):
    """
    スチル画像のキャプチャ操作を行う CTk フレーム
    """

    def __init__(
        self, master: ctk.CTkBaseClass, model: AynimeIssenStyleModel, **kwargs
    ):
        """
        コンストラクタ

        Args:
            master (CTkBaseClass): 親ウィジェット
            model (AynimeIssenStyleModel): モデル
        """
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

        # レイアウト設定
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=0)
        self.columnconfigure(0, weight=1)

        # アニメーションプレビュー
        self._animation_preview_label = AnimationLabel(self)
        self._animation_preview_label.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # フレームリスト
        self._frame_list_bar = ThumbnailBar(self, 120, self._on_frame_list_change)
        self._frame_list_bar.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="swe"
        )

        # ファイルドロップ関係
        # NOTE
        #   シンタックスハイライト上はメソッドが無いことになっているが、
        #   AynimeIssenStyleApp で動的にロードしてるので実際は使える。
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop_file)

        # コントロール類配置用フレーム
        self._ctrl_frame = ctk.CTkFrame(self, width=0, height=0)
        self._ctrl_frame.grid(
            row=2, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="swe"
        )
        self._ctrl_frame.rowconfigure(0, weight=1)
        self._ctrl_frame.columnconfigure(0, weight=1)
        self._ctrl_frame.columnconfigure(1, weight=0)

        # フレームレートスライダー
        self._frame_rate_slider = ctk.CTkSlider(
            self._ctrl_frame,
            from_=1,
            to=60,
            number_of_steps=59,
            command=self._on_frame_rate_slider,
        )
        self._frame_rate_slider.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # フレームレートラベル
        self._frame_rate_label = ctk.CTkLabel(
            self._ctrl_frame, text=f"-- FPS", font=default_font, width=80
        )
        self._frame_rate_label.grid(
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 初期フレームレートを設定
        self._on_frame_rate_slider(24)

    def _on_drop_file(self, event: DnDEvent):
        """
        ファイルドロップハンドラ

        Args:
            event (Event): イベント
        """
        ACCEPTABLE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
        paths = cast(Tuple[str], self.tk.splitlist(event.data))
        pil_images = [
            Image.open(p) for p in paths if p.lower().endswith(ACCEPTABLE_EXTENSIONS)
        ]
        for i in pil_images:
            self._frame_list_bar.add_image(i)

    def _on_frame_list_change(self, frames: List[Image.Image]):
        """
        アニメフレーム更新ハンドラ

        Args:
            frames (List[Image.Image]): アニメフレーム
        """
        self._animation_preview_label.set_frames(frames)

    def _on_frame_rate_slider(self, value: float):
        """
        フレームレートスライダーハンドラ

        Args:
            value (float): スライダー値
        """
        frame_rate_int = round(float(value))
        self._frame_rate_label.configure(text=f"{frame_rate_int} FPS")
        self._animation_preview_label.set_frame_rate(frame_rate_int)
