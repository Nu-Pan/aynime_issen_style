# std
from pathlib import Path
from typing import cast

# Tk/CTk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent

# utils
from utils.constants import WIDGET_PADDING, WIDGET_MIN_WIDTH, DEFAULT_FONT_FAMILY
from utils.image import (
    AspectRatioPattern,
    ResizeDesc,
    calc_ssim,
)
from utils.duration_and_frame_rate import (
    FILM_TIMELINE_IN_FPS,
    STANDARD_FRAME_RATES,
    DFREntry,
    DFR_MAP,
)
from utils.constants import THUMBNAIL_HEIGHT, CAPTURE_FRAME_BUFFER_DURATION_IN_SEC
from utils.windows import file_to_clipboard
from utils.ctk import show_notify_label, show_error_dialog
from utils.capture import *
from utils.std import MultiscaleSequence

# gui
from gui.widgets.thumbnail_bar import ThumbnailBar
from gui.widgets.video_label import Videoabel
from gui.widgets.size_pattern_selection_frame import SizePatternSlectionFrame
from gui.widgets.ais_entry import AISEntry
from gui.widgets.ais_slider import AISSlider
from gui.model.contents_cache import (
    ImageLayer,
    ImageModel,
    PlaybackMode,
    save_content_model,
    load_content_model,
    VideoModelEditSession,
)

# local
from gui.model.aynime_issen_style import AynimeIssenStyleModel


class VideoCaptureFrame(ctk.CTkFrame, TkinterDnD.DnDWrapper):
    """
    スチル画像のキャプチャ操作を行う CTk フレーム
    """

    UI_TAB_NAME = "キンキンキンキンキンキンキンキンキンキンキンキンキンキンキンキン！"

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
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)

        # レイアウト設定
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # 出力関係フレーム
        # NOTE
        #   使用する画像は与えられるものとして、それをどう gif 化するか？　これを担う
        self._output_kind_frame = ctk.CTkFrame(self, width=WIDGET_MIN_WIDTH, height=0)
        self._output_kind_frame.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._output_kind_frame.rowconfigure(0, weight=1)
        self._output_kind_frame.columnconfigure(0, weight=1)

        # 動画プレビュー
        self._video_preview_label = Videoabel(self._output_kind_frame, self._model)
        self._video_preview_label.grid(
            row=0,
            column=0,
            columnspan=2,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe",
        )

        # アニメ名テキストボックス
        self.nime_name_entry = AISEntry(
            self._output_kind_frame,
            width=WIDGET_MIN_WIDTH,
            placeholder_text="Override NIME name ...",
        )
        self.nime_name_entry.grid(
            row=1,
            column=0,
            columnspan=2,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe",
        )
        self.nime_name_entry.register_handler(self.on_nime_name_entry_changed)

        # 解像度選択フレーム
        self._size_pattern_selection_frame = SizePatternSlectionFrame(
            self._output_kind_frame,
            model,
            self._on_resolution_changes,
            AspectRatioPattern.E_RAW,
            ResizeDesc.Pattern.E_VGA,
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
            row=2,
            column=0,
            columnspan=2,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe",
        )

        # UI とモデルの解像度を揃える
        with VideoModelEditSession(self._model.video) as edit:
            edit.set_size(
                ImageLayer.NIME,
                ResizeDesc.from_pattern(
                    self._size_pattern_selection_frame.aspect_ratio,
                    self._size_pattern_selection_frame.resolution,
                ),
            )

        # 再生モード関係フレーム
        self._playback_mode_frame = ctk.CTkFrame(
            self._output_kind_frame, width=WIDGET_MIN_WIDTH, height=0
        )
        self._playback_mode_frame.grid(
            row=3, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._playback_mode_frame.rowconfigure(0, weight=1)

        # 再生モード変数
        self._playback_mode_var = ctk.StringVar(value=self._model.playback_mode.value)

        # 再生モードラジオボタン
        self._playback_mode_radios: list[ctk.CTkRadioButton] = []
        for i, playback_mode in enumerate(PlaybackMode):
            playback_mode_radio = ctk.CTkRadioButton(
                self._playback_mode_frame,
                text=playback_mode.value,
                variable=self._playback_mode_var,
                value=playback_mode.value,
                command=self._on_playback_mode_radio_change,
                width=WIDGET_MIN_WIDTH,
                font=default_font,
            )
            playback_mode_radio.grid(
                row=0, column=i, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
            )
            self._playback_mode_frame.columnconfigure(i, weight=1)
            self._playback_mode_radios.append(playback_mode_radio)

        # セーブフレームレートスライダー
        # NOTE
        #   保存フレームレートは gif 的に合法でなければいけないので DFR_MAP から候補を取る。
        self._save_frame_rate_slider = AISSlider(
            self._output_kind_frame,
            None,
            [e for e in DFR_MAP],
            lambda lho, rho: abs(lho.frame_rate - rho.frame_rate),
            lambda x: f"{x.frame_rate:6.3f}",
            "FPS",
        )
        self._save_frame_rate_slider.grid(
            row=4, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._save_frame_rate_slider.register_handler(
            self._on_save_frame_rate_slider_changed
        )
        self._model.video.register_duration_change_handler(
            self._on_model_frame_rate_changed
        )
        self._save_frame_rate_slider.set_value(DFR_MAP.default_entry)

        # セーブボタン
        self._save_button = ctk.CTkButton(
            self._output_kind_frame,
            text="SAVE",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_save_button_clicked,
        )
        self._save_button.grid(
            row=3,
            rowspan=2,
            column=1,
            columnspan=1,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe",
        )

        # 入力関係フレーム
        # NOTE
        #   gif にする画像の入力・削除・選定を行う
        self._input_kind_frame = ctk.CTkFrame(self, width=WIDGET_MIN_WIDTH, height=0)
        self._input_kind_frame.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._input_kind_frame.columnconfigure(0, weight=1)

        # フレームリスト
        self._frame_list_bar = ThumbnailBar(
            self._input_kind_frame, self._model, THUMBNAIL_HEIGHT
        )
        self._frame_list_bar.grid(
            row=0,
            column=0,
            columnspan=5,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe",
        )

        # 全削除ボタン
        self._wipe_button = ctk.CTkButton(
            self._input_kind_frame,
            text="REMOVE ALL",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_remove_all_button_clicked,
        )
        self._wipe_button.grid(
            row=1, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
        )

        # 無効化画像削除ボタン
        self._remove_disable_button = ctk.CTkButton(
            self._input_kind_frame,
            text="REMOVE DISABLED",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_remove_disable_button_clicked,
        )
        self._remove_disable_button.grid(
            row=1, column=2, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
        )

        # 全有効化ボタン
        self._disable_all_button = ctk.CTkButton(
            self._input_kind_frame,
            text="ENABLE ALL",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_enable_all_button_clicked,
        )
        self._disable_all_button.grid(
            row=1, column=3, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
        )

        # 全無効化ボタン
        self._disable_all_button = ctk.CTkButton(
            self._input_kind_frame,
            text="DISABLE ALL",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_disable_all_button_clicked,
        )
        self._disable_all_button.grid(
            row=1, column=4, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
        )

        # 重複無効化しきい値スライダー
        # NOTE
        #   スライダーの内部表現としては小数点以下を整数として保持する（実質的に固定小数点）
        #   そのあたりのロジックは MultiscaleSequence で実装されている
        self._disable_dupe_values = MultiscaleSequence(5)
        self._disable_dupe_slider = AISSlider(
            self._input_kind_frame,
            None,
            self._disable_dupe_values.values,
            lambda lho, rho: abs(lho - rho),
            lambda x: self._disable_dupe_values.to_pct_str(x),
            "%",
        )
        self._disable_dupe_slider.grid(
            row=2,
            column=0,
            columnspan=4,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe",
        )
        self._disable_dupe_slider.set_value(99900)

        # 重複無効化ボタン
        self._disable_dupe_button = ctk.CTkButton(
            self._input_kind_frame,
            text="DISABLE DUPE",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_disable_dupe_button_clicked,
        )
        self._disable_dupe_button.grid(
            row=2, column=4, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # レコードフレームレートスライダー
        # NOTE
        #   レコード時はコンテンツ（オリジナル）のフレームレートが重要なので STANDARD_FRAME_RATES を候補とする。
        self._record_frame_rate_slider = AISSlider(
            self._input_kind_frame,
            None,
            STANDARD_FRAME_RATES,
            lambda lho, rho: abs(lho - rho),
            lambda x: f"{x:6.3f}",
            "FPS",
        )
        self._record_frame_rate_slider.grid(
            row=3,
            column=0,
            columnspan=4,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe",
        )
        self._record_frame_rate_slider.set_value(FILM_TIMELINE_IN_FPS)

        # レコード秒数スライダー
        RECORD_LENGTH_STEP = 0.5
        RECORD_LENGTH_STOP = CAPTURE_FRAME_BUFFER_DURATION_IN_SEC
        RECORD_LENGTH_START = min(1, RECORD_LENGTH_STOP)
        NUM_RECORD_LENGTH_STEPS = (
            round((RECORD_LENGTH_STOP - RECORD_LENGTH_START) / RECORD_LENGTH_STEP) + 1
        )
        self._record_length_slider = AISSlider(
            self._input_kind_frame,
            None,
            [
                step * RECORD_LENGTH_STEP + RECORD_LENGTH_START
                for step in range(NUM_RECORD_LENGTH_STEPS)
            ],
            lambda lho, rho: abs(lho - rho),
            lambda x: f"{x:3.1f}",
            "SEC",
        )
        self._record_length_slider.grid(
            row=4,
            column=0,
            columnspan=4,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe",
        )
        self._record_length_slider.set_value(
            min(3, CAPTURE_FRAME_BUFFER_DURATION_IN_SEC)
        )

        # レコードボタン
        self._record_button = ctk.CTkButton(
            self._input_kind_frame,
            text="RECORD",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_record_button_clicked,
        )
        self._record_button.grid(
            row=3,
            rowspan=2,
            column=4,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe",
        )

        # グローバルホットキーを登録
        # NOTE
        #   K はキンキン！　の頭文字
        self._model.global_hotkey.register(
            "K", lambda: self._on_record_button_clicked()
        )

        # ファイルドロップ関係
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop_file)

    def on_nime_name_entry_changed(self, text: str):
        """
        アニメ名テキストボックスが変更されたときに呼び出される
        """
        with VideoModelEditSession(self._model.video) as edit:
            if text != "":
                edit.set_nime_name(text)
            else:
                edit.set_nime_name(self._model.stream.nime_window_text)

    def _on_resolution_changes(
        self, aspect_ratio: AspectRatioPattern, resolution: ResizeDesc.Pattern
    ):
        """
        解像度設定が変更された時に呼び出される

        Args:
            aspect_ratio (AspectRatio): アスペクト比
            resolution (Resolution): 解像度
        """
        self._aspect_ratio = aspect_ratio
        self._resolution = resolution
        with VideoModelEditSession(self._model.video) as edit:
            edit.set_size(
                ImageLayer.NIME, ResizeDesc.from_pattern(aspect_ratio, resolution)
            )

    def _on_playback_mode_radio_change(self):
        """
        再生モードラジオボタンに変化があった時に呼び出されるハンドラ
        """
        self._model.playback_mode = PlaybackMode(self._playback_mode_var.get())

    def _on_save_frame_rate_slider_changed(self, value: DFREntry):
        """
        フレームレートスライダーハンドラ

        Args:
            value (float): スライダー値
        """
        with VideoModelEditSession(self._model.video) as edit:
            edit.set_duration_in_msec(value.duration_in_msec)

    def _on_model_frame_rate_changed(self):
        """
        ビデオモデルフレームレート変更ハンドラ
        """
        duration_in_msec = self._model.video.duration_in_msec
        dfr_entry = DFR_MAP.by_duration_in_msec(duration_in_msec)
        self._save_frame_rate_slider.set_value(dfr_entry)

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
        show_notify_label(self, "info", "「一閃」\nクリップボード転送完了")

    def _on_remove_all_button_clicked(self):
        """
        全削除ボタンクリックハンドラ
        """
        with VideoModelEditSession(self._model.video) as edit:
            edit.clear_frames()

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
        with VideoModelEditSession(self._model.video) as edit:
            for disabled_frame_index in disabled_frame_indices:
                edit.delete_frame(disabled_frame_index)

    def _on_enable_all_button_clicked(self):
        """
        全フレーム有効化ボタンハンドラ
        """
        with VideoModelEditSession(self._model.video) as edit:
            edit.set_enable(None, True)

    def _on_disable_all_button_clicked(self):
        """
        全フレーム無効化ボタンハンドラ
        """
        with VideoModelEditSession(self._model.video) as edit:
            edit.set_enable(None, False)

    def _on_disable_dupe_button_clicked(self):
        """
        重複無効化ボタンハンドラ
        """
        # 全フレームの有効・無効を解決
        # NOTE
        #   全有効を初期値として、類似が見つかったら後ろ側のフレームを無効化する
        frame_enabled = [True for _ in range(self._model.video.num_total_frames)]
        for idx_B in range(1, self._model.video.num_total_frames):
            # 前方に向かって有効フレームを探索
            idx_A = idx_B - 1
            while idx_A > 0:
                if frame_enabled[idx_A]:
                    break
                idx_A -= 1

            # 画像を取得（A）
            image_A = self._model.video.get_frame(ImageLayer.NIME, idx_A)
            if image_A is None:
                raise TypeError()

            # 画像を取得（B）
            image_B = self._model.video.get_frame(ImageLayer.NIME, idx_B)
            if image_B is None:
                raise TypeError()

            # 類似度を元に有効・無効を判定
            similarity = calc_ssim(image_A, image_B)
            ddt = self._disable_dupe_values.to_uniform_float(
                self._disable_dupe_slider.value
            )
            if similarity > ddt:
                frame_enabled[idx_B] = False

        # 解決した有効・無効をモデルに設定
        with VideoModelEditSession(self._model.video) as edit:
            edit.set_enable_batch(
                [
                    (frame_index, enable)
                    for frame_index, enable in enumerate(frame_enabled)
                ]
            )

    def _on_record_button_clicked(self):
        """
        レコードボタンクリックハンドラ
        """
        # キャプチャ
        frames = self._model.stream.capture_video(
            fps=self._record_frame_rate_slider.value,
            duration_in_sec=self._record_length_slider.value,
        )

        # アニメ名を解決
        if self.nime_name_entry.text != "":
            nime_name = self.nime_name_entry.text
        else:
            nime_name = self._model.stream.nime_window_text

        # モデルに設定
        with VideoModelEditSession(self._model.video) as edit:
            edit.clear_frames()
            edit.set_nime_name(nime_name)
            edit.set_time_stamp(None)  # NOTE 現在時刻を適用
            edit.append_frames(
                [
                    ImageModel(
                        frame,
                        self._model.video.nime_name,
                        self._model.video.time_stamp,
                    )
                    for frame in frames
                ]
            )

    def _on_drop_file(self, event: DnDEvent):
        """
        ファイルドロップハンドラ

        Args:
            event (Event): イベント
        """
        # イベントからデータを取り出し
        event_data = vars(event)["data"]
        if not isinstance(event_data, str):
            return

        # 読み込み対象を解決
        file_paths = cast(tuple[str], self.tk.splitlist(event_data))
        if len(file_paths) > 1:
            show_error_dialog("ファイルは１つだけドロップしてね。")
            return
        else:
            file_path = file_paths[0]

        # モデルロード
        try:
            load_result = load_content_model(Path(file_path))
        except Exception as e:
            show_error_dialog("ファイルロードに失敗。", e)
            return

        # スチル画像はロード不可
        if isinstance(load_result, ImageModel):
            show_error_dialog("スチル画像はロード不可。")
            return

        # アニメ名を解決
        if self.nime_name_entry.text != "":
            actual_nime_name = self.nime_name_entry.text
        else:
            actual_nime_name = load_result.nime_name

        # モデルに反映
        with VideoModelEditSession(self._model.video) as edit:
            (
                edit.clear_frames()
                .set_nime_name(actual_nime_name)
                .set_time_stamp(load_result.time_stamp)
                .set_duration_in_msec(load_result.duration_in_msec)
                .append_frames(load_result)
            )
