# std
from pathlib import Path
from typing import cast, Tuple, List, Any
from time import time

# PIL
from PIL import Image

# Tk/CTk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent
import tkinter.messagebox as mb

# utils
from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.pil import AspectRatio, Resolution
from gui.model.contents_cache import (
    ImageModel,
    VideoModel,
    save_content_model,
    load_content_model,
)
from utils.constants import APP_NAME_JP, NIME_DIR_PATH, RAW_DIR_PATH
from utils.windows import file_to_clipboard
from utils.ctk import show_notify
from utils.std import flatten

# gui
from gui.widgets.thumbnail_bar import ThumbnailBar
from gui.widgets.animation_label import AnimationLabel
from gui.widgets.size_pattern_selection_frame import SizePatternSlectionFrame

# local
from gui.model.aynime_issen_style import AynimeIssenStyleModel


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
        self.columnconfigure(0, weight=1)

        # 出力関係フレーム
        # NOTE
        #   使用する画像は与えられるものとして、それをどう gif 化するか？　これを担う
        self._output_kind_frame = ctk.CTkFrame(self, width=0, height=0)
        self._output_kind_frame.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._output_kind_frame.rowconfigure(0, weight=1)
        self._output_kind_frame.columnconfigure(0, weight=1)

        # アニメーションプレビュー
        self._animation_preview_label = AnimationLabel(self._output_kind_frame)
        self._animation_preview_label.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 解像度選択フレーム
        self._size_pattern_selection_frame = SizePatternSlectionFrame(
            self._output_kind_frame,
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
        self._frame_rate_frame = ctk.CTkFrame(
            self._output_kind_frame, width=0, height=0
        )
        self._frame_rate_frame.grid(
            row=2, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._frame_rate_frame.rowconfigure(0, weight=1)
        self._frame_rate_frame.columnconfigure(1, weight=1)

        # 折り返し変数
        self._reflect_var = ctk.BooleanVar(value=False)

        # 折り返しチェックボックス
        self._reflect_checkbox = ctk.CTkCheckBox(
            self._frame_rate_frame,
            text="REFLECT",
            width=80,
            variable=self._reflect_var,
            command=self._on_reflect_checkbox_toggle,
        )
        self._reflect_checkbox.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

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
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # フレームレートラベル
        self._frame_rate_label = ctk.CTkLabel(
            self._frame_rate_frame, text=f"-- FPS", font=default_font, width=80
        )
        self._frame_rate_label.grid(
            row=0, column=2, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
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
            row=0, column=3, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 入力関係フレーム
        # NOTE
        #   gif にする画像の入力・削除・選定を行う
        self._input_kind_frame = ctk.CTkFrame(self, width=0, height=0)
        self._input_kind_frame.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._input_kind_frame.columnconfigure(0, weight=1)

        # フレームリスト
        self._frame_list_bar = ThumbnailBar(
            self._input_kind_frame, 120, self._on_frame_list_change
        )
        self._frame_list_bar.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # キャプチャ操作フレーム
        self._capture_ctrl_frame = ctk.CTkFrame(
            self._input_kind_frame, width=0, height=0
        )
        self._capture_ctrl_frame.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._capture_ctrl_frame.rowconfigure(0, weight=1)
        self._capture_ctrl_frame.columnconfigure(0, weight=1)

        # レコード秒数スライダー
        # NOTE
        #   100msec 単位なのでスライダー上の 10 は 1000 msec の意味
        MIN_RECORD_LENGTH = 5
        MAX_RECORD_LENGTH = 30
        self._record_length_slider = ctk.CTkSlider(
            self._capture_ctrl_frame,
            from_=MIN_RECORD_LENGTH,
            to=MAX_RECORD_LENGTH,
            number_of_steps=MAX_RECORD_LENGTH - MIN_RECORD_LENGTH,
            command=self._on_record_length_slider_changed,
        )
        self._record_length_slider.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # レコード秒数ラベル
        self._record_length_label = ctk.CTkLabel(
            self._capture_ctrl_frame, text=f"--.0 SEC", font=default_font, width=80
        )
        self._record_length_label.grid(
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 初期レコード秒数を設定
        self._record_length_slider.set(10)
        self._on_record_length_slider_changed(10)

        # レコードボタン
        self._record_button = ctk.CTkButton(
            self._capture_ctrl_frame,
            text="REC",
            width=80,
            command=self._on_record_button_clicked,
        )
        self._record_button.grid(
            row=0, column=2, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # フレームリスト編集フレーム
        self._edit_ctrl_frame = ctk.CTkFrame(self._input_kind_frame, width=0, height=0)
        self._edit_ctrl_frame.grid(
            row=2, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._edit_ctrl_frame.rowconfigure(0, weight=1)
        self._edit_ctrl_frame.columnconfigure(1, weight=1)

        # 全削除ボタン
        self._wipe_button = ctk.CTkButton(
            self._edit_ctrl_frame,
            text="REMOVE ALL",
            width=80,
            command=self._on_wipe_button_clicked,
        )
        self._wipe_button.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 重複しきい値スライダー
        # NOTE
        #   最終的にほしいのは [0.0, 1.0] だけど、スライダー上は [0, 100] を扱う
        MIN_DUPE_THRESHOLD = 0
        MAX_DUPE_THRESHOLD = 99
        self._dupe_threshold_slider = ctk.CTkSlider(
            self._edit_ctrl_frame,
            from_=MIN_DUPE_THRESHOLD,
            to=MAX_DUPE_THRESHOLD,
            number_of_steps=MAX_DUPE_THRESHOLD - MIN_DUPE_THRESHOLD,
            command=self._on_dupe_threshold_slider_changed,
        )
        self._dupe_threshold_slider.grid(
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 重複しきい値ラベル
        self._duple_threshold_label = ctk.CTkLabel(
            self._edit_ctrl_frame, text=f"--", font=default_font, width=80
        )
        self._duple_threshold_label.grid(
            row=0, column=2, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 初期重複除去しきい値を設定
        self._dupe_threshold_slider.set(95)
        self._on_dupe_threshold_slider_changed(95)

        # 重複無効化ボタン
        self._disable_dupe_button = ctk.CTkButton(
            self._edit_ctrl_frame,
            text="DISABLE DUPE",
            width=80,
            command=self._on_disable_dup_button_clicked,
        )
        self._disable_dupe_button.grid(
            row=0, column=3, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 無効化画像ワイプボタン
        self._remove_disable_button = ctk.CTkButton(
            self._edit_ctrl_frame,
            text="REMOVE DISABLED",
            width=80,
            command=self._on_remove_disable_button_clicked,
        )
        self._remove_disable_button.grid(
            row=0, column=4, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # ファイルドロップ関係
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop_file)

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

    def _on_frame_list_change(self):
        """
        アニメフレーム更新ハンドラ
        """
        self._update_preview()

    def _on_reflect_checkbox_toggle(self):
        """
        「折り返し」チェックボックスハンドラ
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
        # 最低２フレーム必要
        video = self._animation_preview_label.video
        if video.num_enable_frames < 2:
            raise ValueError(f"# of frames less than 2(actual={len(video)})")

        # gif ファイルとして保存
        # date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # gif_file_path = NIME_DIR_PATH / (date_str + ".gif")
        gif_file_path = save_content_model(
            video, self._animation_preview_label.interval_in_ms
        )
        if not isinstance(gif_file_path, Path):
            raise TypeError(
                f"Expected Path, but got {type(gif_file_path)}. "
                "This is a bug, please report it."
            )

        # クリップボードに転送
        file_to_clipboard(gif_file_path)

        # クリップボード転送完了通知
        show_notify(self, "「一閃」\nクリップボード転送完了")

    def _on_wipe_button_clicked(self):
        """
        ワイプボタンクリックハンドラ
        """
        self._frame_list_bar.clear_images()

    def _on_dupe_threshold_slider_changed(self, value: float):
        """
        重複除去しきい値スライダーハンドラ

        Args:
            value (float): スライダー値
        """
        self._dupe_threshold = value / 100
        self._duple_threshold_label.configure(text=f"{self._dupe_threshold}")

    def _on_disable_dup_button_clicked(self):
        """
        重複無効化ボタンハンドラ
        """
        self._frame_list_bar.disable_dupe_images(self._dupe_threshold)

    def _on_remove_disable_button_clicked(self):
        """
        無効画像削除ボタンハンドラ
        """
        self._frame_list_bar.clear_disable_images()

    def _update_preview(self):
        """
        現在の状態に基づいてアニメプレビューを更新する
        """
        # 初期化途中で来ちゃった場合は何もしない
        if "_frame_list_bar" not in vars(self):
            return

        # エイリアス
        video = self._frame_list_bar.video

        # 「折り返し」の対応
        # NOTE
        #   最終フレームまで再生したあと、先頭フレームへ向けて逆再生を行うことを「折り返し」と呼んでいる。
        if self._reflect_checkbox.get():
            if len(video) > 2:
                extend_frames = video[1:-1]
                extend_frames.reverse()
                video = video + extend_frames

        # プレビューウィジェットに設定
        self._animation_preview_label.set_video(video)

    def _record_handler(
        self, stop_time_in_sec: float, record_raw_images: List[Image.Image] = []
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
            self._frame_list_bar.add_image(record_raw_images)
            return

        # キャプチャ
        try:
            new_image = self._model.capture()
        except Exception as e:
            mb.showerror(
                APP_NAME_JP,
                f"キャプチャに失敗。多分キャプチャ対象のディスプレイ・ウィンドウの選択を忘れてるよ。\n{e.args}",
            )
            return

        # 新しいフレームで差分が発生している場合のみ追加する
        if len(record_raw_images) == 0:
            next_frames = [new_image]
        else:
            last_frame = record_raw_images[-1]
            if new_image == last_frame:
                next_frames = record_raw_images
            else:
                next_frames = record_raw_images + [new_image]

        # 次をディスパッチ
        self.after(10, self._record_handler, stop_time_in_sec, next_frames)

    def _on_drop_file(self, event: DnDEvent):
        """
        ファイルドロップハンドラ

        Args:
            event (Event): イベント
        """
        # ファイルパスのみ受付
        event_data = vars(event)["data"]
        if not isinstance(event_data, str):
            return

        # 動画・画像で分岐
        try:
            paths = cast(Tuple[str], self.tk.splitlist(event_data))
            video_models = cast(
                List[Any],
                flatten([load_content_model(Path(p)) for p in paths]),
            )
            # TODO 実装
            raise NotImplementedError()
        except Exception as e:
            mb.showerror(
                APP_NAME_JP,
                f"画像・動画の読み込みに失敗。\n{e.args}",
            )
            return

        # フレームリストに追加
        self._frame_list_bar.add_image(frames)
