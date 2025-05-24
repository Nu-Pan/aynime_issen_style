# std
import warnings
from pathlib import Path
from datetime import datetime
from typing import cast, Tuple, List, Optional, Iterable
from time import time

# PIL
from PIL import Image, ImageTk, ImageChops

# Tk/CTk
import tkinter as tk
from tkinter import Event
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent

# local
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

        # メンバー保存
        self._model = model

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

        # レイアウト設定
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)
        self.columnconfigure(0, weight=1)

        # 出力関係フレーム
        # NOTE
        #   使用する画像は与えられるものとして、それをどう gif 化するか？　これを担う
        self._output_frame = ctk.CTkFrame(self, width=0, height=0)
        self._output_frame.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._output_frame.rowconfigure(0, weight=1)
        self._output_frame.rowconfigure(1, weight=0)
        self._output_frame.columnconfigure(0, weight=1)

        # アニメーションプレビュー
        self._animation_preview_label = AnimationLabel(self._output_frame)
        self._animation_preview_label.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 解像度選択フレーム
        self._size_pattern_selection_frame = SizePatternSlectionFrame(
            self._output_frame,
            self._on_resolution_changes,
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
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # フレームレート関係フレーム
        self._frame_rate_frame = ctk.CTkFrame(self._output_frame, width=0, height=0)
        self._frame_rate_frame.grid(
            row=2, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._frame_rate_frame.rowconfigure(0, weight=1)
        self._frame_rate_frame.columnconfigure(0, weight=1)
        self._frame_rate_frame.columnconfigure(1, weight=0)
        self._frame_rate_frame.columnconfigure(2, weight=0)

        # フレームレートスライダー
        MIN_RECORD_LENGTH = 1
        MAX_RECORD_LENGTH = 24
        self._frame_rate_slider = ctk.CTkSlider(
            self._frame_rate_frame,
            from_=MIN_RECORD_LENGTH,
            to=MAX_RECORD_LENGTH,
            number_of_steps=MAX_RECORD_LENGTH - MIN_RECORD_LENGTH,
            command=self._on_frame_rate_slider_changed,
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
        self._frame_rate_slider.set(10)
        self._on_frame_rate_slider_changed(10)

        # セーブボタン
        self._save_button = ctk.CTkButton(
            self._frame_rate_frame,
            text="SAVE",
            width=80,
            command=self._on_save_button_clicked,
        )
        self._save_button.grid(
            row=0, column=2, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 入力関係フレーム
        # NOTE
        #   gif にする画像の入力・削除・選定を行う
        self._input_frame = ctk.CTkFrame(self, width=0, height=0)
        self._input_frame.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._input_frame.rowconfigure(0, weight=0)
        self._input_frame.rowconfigure(1, weight=0)
        self._input_frame.columnconfigure(0, weight=1)

        # フレームリスト
        self._frame_list_bar = ThumbnailBar(
            self._input_frame, 120, self._on_frame_list_change
        )
        self._frame_list_bar.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # フレームリスト編集フレーム
        self._input_ctrl_frame = ctk.CTkFrame(self._input_frame, width=0, height=0)
        self._input_ctrl_frame.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._input_ctrl_frame.rowconfigure(0, weight=1)
        self._input_ctrl_frame.columnconfigure(0, weight=0)
        self._input_ctrl_frame.columnconfigure(1, weight=1)
        self._input_ctrl_frame.columnconfigure(2, weight=0)
        self._input_ctrl_frame.columnconfigure(3, weight=0)

        # ワイプボタン
        self._wipe_button = ctk.CTkButton(
            self._input_ctrl_frame,
            text="WIPE",
            width=80,
            command=self._on_wipe_button_clicked,
        )
        self._wipe_button.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # レコード秒数スライダー
        # NOTE
        #   100msec 単位なのでスライダー上の 10 は 1000 msec の意味
        MIN_RECORD_LENGTH = 10
        MAX_RECORD_LENGTH = 30
        self._record_length_slider = ctk.CTkSlider(
            self._input_ctrl_frame,
            from_=MIN_RECORD_LENGTH,
            to=MAX_RECORD_LENGTH,
            number_of_steps=MAX_RECORD_LENGTH - MIN_RECORD_LENGTH,
            command=self._on_record_length_slider_changed,
        )
        self._record_length_slider.grid(
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # レコード秒数ラベル
        self._record_length_label = ctk.CTkLabel(
            self._input_ctrl_frame, text=f"--.0 SEC", font=default_font, width=80
        )
        self._record_length_label.grid(
            row=0, column=2, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 初期レコード秒数を設定
        self._record_length_slider.set(10)
        self._on_record_length_slider_changed(10)

        # レコードボタン
        self._record_button = ctk.CTkButton(
            self._input_ctrl_frame,
            text="REC",
            width=80,
            command=self._on_record_button_clicked,
        )
        self._record_button.grid(
            row=0, column=3, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
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
        self._frame_list_bar.add_image(pil_images)

    def _on_frame_list_change(self):
        """
        アニメフレーム更新ハンドラ

        Args:
            frames (List[Image.Image]): アニメフレーム
        """
        self._update_preview()

    def _on_frame_rate_slider_changed(self, value: float):
        """
        フレームレートスライダーハンドラ

        Args:
            value (float): スライダー値
        """
        frame_rate_int = round(float(value))
        self._frame_rate_label.configure(text=f"{frame_rate_int} FPS")
        self._animation_preview_label.set_frame_rate(frame_rate_int)

    def _on_wipe_button_clicked(self):
        """
        ワイプボタンクリックハンドラ
        """
        self._frame_list_bar.clear_images()

    def _on_record_length_slider_changed(self, value: float):
        """
        レコード秒数スライダーハンドラ

        Args:
            value (float): スライダー値
        """
        self._record_length = float(value) / 10
        self._record_length_label.configure(text=f"{self._record_length:.1f} SEC")

    def _on_record_button_clicked(self):
        """
        レコードボタンクリックハンドラ
        """
        self.after(0, self._record_handler, time() + self._record_length, [])

    def _on_save_button_clicked(self):
        """
        セーブボタンクリックハンドラ
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

    def _on_resolution_changes(self, aspect_ratio: AspectRatio, resolution: Resolution):
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

    def _record_handler(
        self, stop_time_in_sec: float, record_frames: List[Image.Image] = []
    ):
        """
        レコード処理を実際に担うハンドラ
        自分自身のディスパッチを繰り返すことで並行処理を実現、連続的なキャプチャを実現している

        Args:
            stop_time_in_sec (float): レコード処理終了時刻
            record_frames (Optional[Image.Image]): 今までに記録したフレーム
        """
        # 所定の時間を経過してたら終了
        if time() > stop_time_in_sec:
            self._frame_list_bar.add_image(record_frames)
            return

        # キャプチャ
        new_frame = self._model.capture()

        # 新しいフレームで差分が発生している場合のみ追加する
        if len(record_frames) == 0:
            next_frames = [new_frame]
        else:
            last_frame = record_frames[-1]
            if new_frame == last_frame:
                next_frames = record_frames
            elif ImageChops.difference(new_frame, last_frame).getbbox() is None:
                next_frames = record_frames
            else:
                next_frames = record_frames + [new_frame]

        # 次をディスパッチ
        self.after(10, self._record_handler, stop_time_in_sec, next_frames)
