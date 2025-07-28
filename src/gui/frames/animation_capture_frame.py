# std
from pathlib import Path
from typing import List
from time import time

# Tk/CTk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent

# utils
from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.image import AspectRatioPattern, ResizeDesc, AISImage
from utils.constants import THUMBNAIL_HEIGHT
from utils.windows import file_to_clipboard
from utils.ctk import show_notify, show_error_dialog
from utils.std import flatten

# gui
from gui.widgets.thumbnail_bar import ThumbnailBar
from gui.widgets.animation_label import AnimationLabel
from gui.widgets.size_pattern_selection_frame import SizePatternSlectionFrame
from gui.model.contents_cache import (
    ImageLayer,
    ImageModel,
    VideoModel,
    PlaybackMode,
    save_content_model,
    load_content_model,
)

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
        self._animation_preview_label = AnimationLabel(
            self._output_kind_frame, self._model
        )
        self._animation_preview_label.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 解像度選択フレーム
        self._size_pattern_selection_frame = SizePatternSlectionFrame(
            self._output_kind_frame,
            self._on_resolution_changes,
            AspectRatioPattern.E_RAW,
            ResizeDesc.Pattern.E_RAW,
            [
                AspectRatioPattern.E_RAW,
                AspectRatioPattern.E_16_9,
                AspectRatioPattern.E_4_3,
                AspectRatioPattern.E_1_1,
            ],
            [
                ResizeDesc.Pattern.E_RAW,
                ResizeDesc.Pattern.E_HVGA,
                ResizeDesc.Pattern.E_VGA,
                ResizeDesc.Pattern.E_QHD,
                ResizeDesc.Pattern.E_HD,
            ],
        )
        self._size_pattern_selection_frame.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # UI とモデルの解像度を揃える
        self._model.video.set_size(
            ImageLayer.NIME,
            ResizeDesc.from_pattern(
                self._size_pattern_selection_frame.aspect_ratio,
                self._size_pattern_selection_frame.resolution,
            ),
        )

        # 再生モード関係フレーム
        self._playback_mode_frame = ctk.CTkFrame(
            self._output_kind_frame, width=0, height=0
        )
        self._playback_mode_frame.grid(
            row=2, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._playback_mode_frame.rowconfigure(0, weight=1)

        # 再生モード変数
        self._playback_mode_var = ctk.StringVar(value=self._model.playback_mode.value)

        # 再生モードラジオボタン
        self._playback_mode_radios: List[ctk.CTkRadioButton] = []
        for i, playback_mode in enumerate(PlaybackMode):
            playback_mode_radio = ctk.CTkRadioButton(
                self._playback_mode_frame,
                text=playback_mode.value,
                variable=self._playback_mode_var,
                value=playback_mode.value,
                command=self._on_playback_mode_radio_change,
                width=0,
                font=default_font,
            )
            playback_mode_radio.grid(
                row=0, column=i, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
            )
            self._playback_mode_frame.columnconfigure(i, weight=1)
            self._playback_mode_radios.append(playback_mode_radio)

        # フレームレート関係フレーム
        self._frame_rate_frame = ctk.CTkFrame(
            self._output_kind_frame, width=0, height=0
        )
        self._frame_rate_frame.grid(
            row=3, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._frame_rate_frame.rowconfigure(0, weight=1)
        self._frame_rate_frame.columnconfigure(0, weight=1)

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
            self._frame_rate_frame, text="-- FPS", font=default_font, width=80
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
        self._input_kind_frame = ctk.CTkFrame(self, width=0, height=0)
        self._input_kind_frame.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._input_kind_frame.columnconfigure(0, weight=1)

        # フレームリスト
        self._frame_list_bar = ThumbnailBar(
            self._input_kind_frame, self._model, THUMBNAIL_HEIGHT
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

    def _on_resolution_changes(
        self, aspect_ratio: AspectRatioPattern, resolution: ResizeDesc.Pattern
    ):
        """
        解像度設定が変更された時に呼び出される

        Args:
            aspect_ratio (AspectRatio): アスペクト比
            resolution (Resolution): 解像度
        """
        self._model.video.set_size(
            ImageLayer.NIME, ResizeDesc.from_pattern(aspect_ratio, resolution)
        )
        self._aspect_ratio = aspect_ratio
        self._resolution = resolution

    def _on_playback_mode_radio_change(self):
        """
        再生モードラジオボタンに変化があった時に呼び出されるハンドラ
        """
        self._model.playback_mode = PlaybackMode(self._playback_mode_var.get())

    def _on_frame_rate_slider_changed(self, value: float):
        """
        フレームレートスライダーハンドラ

        Args:
            value (float): スライダー値
        """
        frame_rate_int = round(float(value))
        self._frame_rate_label.configure(text=f"{frame_rate_int} FPS")
        self._model.video.set_frame_rate(frame_rate_int)

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
        video = self._model.video
        if video.num_enable_frames < 2:
            show_error_dialog("gif の保存には最低でも 2 フレーム必要だよ")
            return

        # gif ファイルとして保存
        playback_mode = PlaybackMode(self._playback_mode_var.get())
        try:
            gif_file_path = save_content_model(video, playback_mode)
        except Exception as e:
            show_error_dialog("gif ファイルの保存に失敗", e)
            return

        # クリップボードに転送
        file_to_clipboard(gif_file_path)

        # クリップボード転送完了通知
        show_notify(self, "「一閃」\nクリップボード転送完了")

    def _on_wipe_button_clicked(self):
        """
        ワイプボタンクリックハンドラ
        """
        self._model.video.clear_frames()

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
        raise NotImplementedError()

    def _on_remove_disable_button_clicked(self):
        """
        無効画像削除ボタンハンドラ
        """
        # 無効なフレームを列挙
        disabled_frame_indices = []
        for frame_index in range(self._model.video.num_total_frames):
            if not self._model.video.get_enable(frame_index):
                disabled_frame_indices.append(frame_index)

        # 無効なフレームを後ろから削除
        # NOTE
        #   前方のフレームを削除すると、それよりも後方のフレームがずれるので
        disabled_frame_indices.sort(reverse=True)
        for disabled_frame_index in disabled_frame_indices:
            self._model.video.delete_frame(disabled_frame_index)

    def _record_handler(
        self, stop_time_in_sec: float, record_raw_images: List[AISImage] = []
    ):
        """
        レコード処理を実際に担うハンドラ
        自分自身のディスパッチを繰り返すことで並行処理を実現、連続的なキャプチャを実現している

        Args:
            stop_time_in_sec (float): レコード処理終了時刻
            record_frames (Optional[AISImage]): 今までに記録したフレーム
        """
        # 所定の時間を経過してたら終了
        if time() > stop_time_in_sec:
            self._model.video.set_time_stamp(None)
            self._model.video.append_frames(
                [
                    ImageModel(img, self._model.video.time_stamp)
                    for img in record_raw_images
                ]
            )
            return

        # キャプチャ
        try:
            new_image = self._model.capture.capture()
        except Exception as e:
            show_error_dialog(
                "キャプチャに失敗。多分キャプチャ対象のディスプレイ・ウィンドウの選択を忘れてるよ。",
                e,
            )
            return

        # 新しいフレームで差分が発生している場合のみ追加する
        # NOTE
        #   完全に同一なフレーム
        #   PIL.Image.Image 同士の == での比較は、ピクセル値も含めた完全一致の場合のみ True になる
        #   AISImage 同士の == での比較は
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
        paths = self.tk.splitlist(event_data)
        failed_names = []
        new_models = []
        for path_str in paths:
            path = Path(path_str)
            try:
                new_models.append(load_content_model(path))
            except Exception as e:
                failed_names.append(path.name)

        # モデルに反映
        self._model.video.append_frames(new_models)

        # 問題が起きていればダイアログを出す
        if len(failed_names) > 0:
            # 基本メッセージ
            message_lines = []
            if len(new_models) > 0:
                message_lines.append(
                    "ドロップされた画像・動画のうち、一部の読み込みに失敗。"
                )
            else:
                message_lines.append(
                    "ドロップされたすべての画像・動画の読み込みに失敗。"
                )

            # 読み込み失敗リスト
            TOP_N = 5
            message_lines.extend(failed_names[:TOP_N])
            if len(failed_names) > TOP_N:
                message_lines.append("...")

            # ダイアログ表示
            show_error_dialog("\n".join(message_lines))
