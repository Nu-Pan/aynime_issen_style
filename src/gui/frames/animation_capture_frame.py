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
    save_pil_images_to_gif_file,
    AspectRatio,
    Resolution,
    resize_cover_pattern_size,
)
from gui.widgets.thumbnail_bar import ThumbnailBar
from gui.widgets.animation_label import AnimationLabel
from gui.widgets.size_pattern_selection_frame import SizePatternSlectionFrame


class AnimationCaptureFrame(ctk.CTkFrame, TkinterDnD.DnDWrapper):
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
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # フレームレート関係フレーム
        self._frame_rate_frame = ctk.CTkFrame(self, width=0, height=0)
        self._frame_rate_frame.grid(
            row=2, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._frame_rate_frame.rowconfigure(0, weight=1)
        self._frame_rate_frame.columnconfigure(0, weight=1)
        self._frame_rate_frame.columnconfigure(1, weight=0)

        # フレームレートスライダー
        MIN_FRAME_RATE = 1
        MAX_FRAME_RATE = 15
        self._frame_rate_slider = ctk.CTkSlider(
            self._frame_rate_frame,
            from_=MIN_FRAME_RATE,
            to=MAX_FRAME_RATE,
            number_of_steps=MAX_FRAME_RATE - MIN_FRAME_RATE,
            command=self._on_frame_rate_slider,
        )
        self._frame_rate_slider.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # フレームレートラベル
        self._frame_rate_label = ctk.CTkLabel(
            self._frame_rate_frame, text=f"-- FPS", font=default_font, width=80
        )
        self._frame_rate_label.grid(
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 初期フレームレートを設定
        self._on_frame_rate_slider(10)

        # gif 生成ボタン
        self._create_button = ctk.CTkButton(
            self._frame_rate_frame,
            text="萌え",
            width=80,
            command=self._on_create_button_clicked,
        )
        self._create_button.grid(
            row=0, column=2, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 解像度選択フレーム
        self._size_pattern_selection_frame = SizePatternSlectionFrame(
            self,
            self.on_resolution_changes,
            AspectRatio.E_RAW,
            Resolution.E_RAW,
            [
                AspectRatio.E_RAW,
                AspectRatio.E_16_9,
                AspectRatio.E_4_3,
                AspectRatio.E_1_1,
            ],
            [
                Resolution.E_RAW,
                Resolution.E_HVGA,
                Resolution.E_VGA,
                Resolution.E_QHD,
                Resolution.E_HD,
            ],
        )
        self._size_pattern_selection_frame.grid(
            row=3, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
        )

        # ファイルドロップ関係
        # NOTE
        #   シンタックスハイライト上はメソッドが無いことになっているが、
        #   AynimeIssenStyleApp で動的にロードしてるので実際は使える。
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop_file)

    def _on_drop_file(self, event: DnDEvent):
        """
        ファイルドロップハンドラ

        Args:
            event (Event): イベント
        """
        ACCEPTABLE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")
        event_data = cast(str, vars(event)["data"])
        paths = cast(Tuple[str], self.tk.splitlist(event_data))
        pil_images = [
            Image.open(p) for p in paths if p.lower().endswith(ACCEPTABLE_EXTENSIONS)
        ]
        for i in pil_images:
            self._frame_list_bar.add_image(i)

    def _on_frame_list_change(self):
        """
        アニメフレーム更新ハンドラ

        Args:
            frames (List[Image.Image]): アニメフレーム
        """
        self._update_preview()

    def _on_frame_rate_slider(self, value: float):
        """
        フレームレートスライダーハンドラ

        Args:
            value (float): スライダー値
        """
        frame_rate_int = round(float(value))
        self._frame_rate_label.configure(text=f"{frame_rate_int} FPS")
        self._animation_preview_label.set_frame_rate(frame_rate_int)

    def _on_create_button_clicked(self):
        """
        生成ボタンクリックハンドラ

        Args:
            event (Event): イベント
        """
        # 対象フレームの列挙
        frames = self._animation_preview_label.frames
        if len(frames) < 2:
            raise ValueError(f"# of frames less than 2(actual={len(frames)})")

        # gif ファイルとして保存
        nime_dir_path = Path.cwd() / "nime"
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        gif_file_path = nime_dir_path / (date_str + ".gif")
        save_pil_images_to_gif_file(
            frames, self._animation_preview_label.interval_in_ms, gif_file_path
        )

    def on_resolution_changes(self, aspect_ratio: AspectRatio, resolution: Resolution):
        """
        解像度設定が変更された時に呼び出される

        Args:
            aspect_ratio (AspectRatio): アスペクト比
            resolution (Resolution): 解像度
        """
        self._aspect_ratio = aspect_ratio
        self._resolution = resolution
        self._update_preview()

    def _update_preview(self):
        """
        現在の状態に基づいてアニメプレビューを更新する
        """
        frames = [
            resize_cover_pattern_size(f, self._aspect_ratio, self._resolution)
            for f in self._frame_list_bar.original_frames
        ]
        self._animation_preview_label.set_frames(frames)
