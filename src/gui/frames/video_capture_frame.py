# std
from pathlib import Path
from typing import cast

# Tk/CTk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent

# utils
from utils.constants import WIDGET_MIN_WIDTH, DEFAULT_FONT_FAMILY
from utils.image import (
    AspectRatioPattern,
    PlaybackMode,
    ResolutionPattern,
    ResizeDesc,
    calc_ssim,
    ExportTarget,
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
from gui.widgets.video_label import VideoLabel
from gui.widgets.size_pattern_selection_frame import SizePatternSlectionFrame
from gui.widgets.ais_frame import AISFrame
from gui.widgets.ais_entry import AISEntry
from gui.widgets.ais_slider import AISSlider
from gui.model.contents_cache import (
    ImageLayer,
    ImageModel,
    VideoModel,
    save_content_model,
    load_content_model,
    VideoModelEditSession,
)

# local
from gui.model.aynime_issen_style import AynimeIssenStyleModel


class PlaybackModeSelectionFrame(AISFrame):
    """
    再生モード選択フレーム
    ラジオボタンを１つにまとめるためだけに存在
    """

    def __init__(self, master: ctk.CTkBaseClass, model: VideoModel, **kwargs):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # メンバー保存
        self._model = model

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)

        # レイアウト設定
        self.ais.rowconfigure(0, weight=1)

        # 再生モード変数
        self._playback_mode_var = ctk.StringVar(value=self._model.playback_mode.value)

        # 再生モードラジオボタン
        self._radio_buttons: list[ctk.CTkRadioButton] = []
        for i, playback_mode in enumerate(PlaybackMode):
            radio_button = ctk.CTkRadioButton(
                self,
                text=playback_mode.value,
                variable=self._playback_mode_var,
                value=playback_mode.value,
                command=self._on_radio_button_change,
                font=default_font,
            )
            self.ais.grid_child(radio_button, 0, i, sticky="ns")
            self.ais.columnconfigure(i, weight=1)
            self._radio_buttons.append(radio_button)

        # モデル変更ハンドラを登録
        self._model.register_playback_mode_change_handler(
            self._on_playback_mode_changed
        )

    def _on_radio_button_change(self):
        """
        再生モードラジオボタンに変化があった時に呼び出されるハンドラ
        """
        with VideoModelEditSession(self._model) as edit:
            edit.set_playback_mode(PlaybackMode(self._playback_mode_var.get()))

    def _on_playback_mode_changed(self):
        """
        モデル側で再生モードに変更があった時に呼び出されるハンドラ
        """
        if self._playback_mode_var.get() != self._model.playback_mode.value:
            self._playback_mode_var.set(self._model.playback_mode.value)


class VideoCaptureFrame(AISFrame, TkinterDnD.DnDWrapper):
    """
    ビデオのキャプチャ操作を行う CTk フレーム
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

        # レイアウト設定
        self.ais.columnconfigure(0, weight=1)

        # 出力関係フレーム
        # NOTE
        #   使用する画像は与えられるものとして、それをどう動画化するか？　これを担う
        self._output_kind_frame = AISFrame(self)
        self.ais.grid_child(self._output_kind_frame, 0, 0)
        self.ais.rowconfigure(0, weight=1)

        # 出力関係フレームのレイアウト設定
        self._output_kind_frame.ais.columnconfigure(0, weight=1)

        # 動画プレビュー
        self._video_preview_label = VideoLabel(
            self._output_kind_frame, self._model.video
        )
        self._output_kind_frame.ais.grid_child(self._video_preview_label, 0, 0, 1, 2)
        self._output_kind_frame.ais.rowconfigure(0, weight=1)

        # アニメ名テキストボックス
        self._nime_name_entry = AISEntry(
            self._output_kind_frame,
            width=WIDGET_MIN_WIDTH,
            placeholder_text="Override NIME name ...",
        )
        self._output_kind_frame.ais.grid_child(self._nime_name_entry, 1, 0, 1, 2)
        self._nime_name_entry.register_handler(self.on_nime_name_entry_changed)

        # 解像度選択フレーム
        self._size_pattern_selection_frame = SizePatternSlectionFrame(
            self._output_kind_frame,
            model,
            self._on_resolution_changes,
            AspectRatioPattern.E_RAW,
            ResolutionPattern.E_VGA,
            [
                AspectRatioPattern.E_16_9,
                AspectRatioPattern.E_4_3,
                AspectRatioPattern.E_RAW,
            ],
            [
                ResolutionPattern.E_VGA,
                ResolutionPattern.E_HD,
                ResolutionPattern.E_FHD,
                ResolutionPattern.E_RAW,
            ],
        )
        self._output_kind_frame.ais.grid_child(
            self._size_pattern_selection_frame, 2, 0, 1, 2
        )

        # UI とモデルの解像度を揃える
        with VideoModelEditSession(self._model.video) as edit:
            edit.set_size(
                ImageLayer.NIME,
                ResizeDesc(
                    self._size_pattern_selection_frame.aspect_ratio,
                    self._size_pattern_selection_frame.resolution,
                ),
            )

        # 再生モードラジオボタン
        self._playback_mode_frame = PlaybackModeSelectionFrame(
            self._output_kind_frame, model.video
        )
        self._output_kind_frame.ais.grid_child(self._playback_mode_frame, 3, 0)

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
        self._output_kind_frame.ais.grid_child(self._save_frame_rate_slider, 4, 0)
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
        self._output_kind_frame.ais.grid_child(self._save_button, 3, 1, 2, 1)

        # 入力関係フレーム
        # NOTE
        #   動画にする画像の入力・削除・選定を行う
        self._input_kind_frame = AISFrame(self)
        self.ais.grid_child(self._input_kind_frame, 1, 0)
        self.ais.rowconfigure(1, weight=0)

        # 入力関係フレームのレイアウト設定
        self._input_kind_frame.ais.columnconfigure(0, weight=1)

        # フレームリスト
        self._frame_list_bar = ThumbnailBar(
            self._input_kind_frame, self._model, THUMBNAIL_HEIGHT
        )
        self._input_kind_frame.ais.grid_child(self._frame_list_bar, 0, 0, 1, 5)

        # 全削除ボタン
        self._wipe_button = ctk.CTkButton(
            self._input_kind_frame,
            text="REMOVE ALL",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_remove_all_button_clicked,
        )
        self._input_kind_frame.ais.grid_child(self._wipe_button, 1, 1, sticky="ns")

        # 無効化画像削除ボタン
        self._remove_disable_button = ctk.CTkButton(
            self._input_kind_frame,
            text="REMOVE DISABLED",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_remove_disable_button_clicked,
        )
        self._input_kind_frame.ais.grid_child(
            self._remove_disable_button, 1, 2, sticky="ns"
        )

        # 全有効化ボタン
        self._enable_all_button = ctk.CTkButton(
            self._input_kind_frame,
            text="ENABLE ALL",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_enable_all_button_clicked,
        )
        self._input_kind_frame.ais.grid_child(
            self._enable_all_button, 1, 3, sticky="ns"
        )

        # 全無効化ボタン
        self._disable_all_button = ctk.CTkButton(
            self._input_kind_frame,
            text="DISABLE ALL",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_disable_all_button_clicked,
        )
        self._input_kind_frame.ais.grid_child(
            self._disable_all_button, 1, 4, sticky="ns"
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
        self._input_kind_frame.ais.grid_child(self._disable_dupe_slider, 2, 0, 1, 4)
        self._disable_dupe_slider.set_value(99900)

        # 重複無効化ボタン
        self._disable_dupe_button = ctk.CTkButton(
            self._input_kind_frame,
            text="DISABLE DUPE",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_disable_dupe_button_clicked,
        )
        self._input_kind_frame.ais.grid_child(self._disable_dupe_button, 2, 4)

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
        self._input_kind_frame.ais.grid_child(
            self._record_frame_rate_slider, 3, 0, 1, 4
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
        self._input_kind_frame.ais.grid_child(self._record_length_slider, 4, 0, 1, 4)
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
        self._input_kind_frame.ais.grid_child(self._record_button, 3, 4, 2, 1)

        # モデル変更コールバック
        self._model.video.register_layer_changed_handler(
            ImageLayer.NIME, self._on_nime_changed
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
        self, aspect_ratio: AspectRatioPattern, resolution: ResolutionPattern
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
            edit.set_size(ImageLayer.NIME, ResizeDesc(aspect_ratio, resolution))

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
        video_model = self._model.video
        if video_model.num_enable_frames < 2:
            show_error_dialog("動画の保存には最低でも 2 フレーム必要だよ")
            return

        # 動画ファイルとして保存
        try:
            video_file_path = save_content_model(video_model)
        except Exception as e:
            show_error_dialog("動画ファイルの保存に失敗", e)
            return

        # クリップボードに転送
        file_to_clipboard(video_file_path)

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

    def _on_nime_changed(self):
        """
        NIME 画像変更ハンドラ
        """
        # エイリアス
        model = self._model.video

        # 設定変更を各 UI に反映
        resize_desc = model.get_size(ImageLayer.NIME)
        if (
            self._size_pattern_selection_frame.aspect_ratio != resize_desc.aspect_ratio
            or self._size_pattern_selection_frame.resolution != resize_desc.resolution
        ):
            self._size_pattern_selection_frame.set_pattern(
                aspect_ratio=resize_desc.aspect_ratio.pattern,
                resolution=resize_desc.resolution.pattern,
            )

    def _on_record_button_clicked(self):
        """
        レコードボタンクリックハンドラ
        """
        # エイリアス
        model = self._model.video

        # キャプチャ
        frames = self._model.stream.capture_video(
            fps=self._record_frame_rate_slider.value,
            duration_in_sec=self._record_length_slider.value,
        )

        # アニメ名を解決
        if self._nime_name_entry.text != "":
            nime_name = self._nime_name_entry.text
        else:
            nime_name = self._model.stream.nime_window_text

        # モデルに設定
        with VideoModelEditSession(model) as edit:
            edit.clear_frames()
            edit.set_nime_name(nime_name)
            edit.set_time_stamp(None)  # NOTE 現在時刻を適用
            edit.append_frames(frame for frame in frames)

    def _on_drop_file(self, event: DnDEvent):
        """
        ファイルドロップハンドラ

        Args:
            event (Event): イベント
        """
        # エイリアス
        model = self._model.video

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
            new_model = load_content_model(Path(file_path))
        except Exception as e:
            show_error_dialog("ファイルロードに失敗。", e)
            return

        # サムネイルのリサイズ設定を避けておく
        preserved_thumbnail_resize_desc = model.get_size(ImageLayer.THUMBNAIL)
        preserved_thumbnail_resize_mode = model.get_resize_mode(ImageLayer.THUMBNAIL)

        # モデルに諸々を反映
        with VideoModelEditSession(model) as edit:
            # 普通にロード
            if isinstance(new_model, VideoModel):
                # 動画の場合、関連ロード
                edit.set_model(new_model)
                if self._nime_name_entry.text != "":
                    edit.set_nime_name(self._nime_name_entry.text)
            elif isinstance(new_model, ImageModel):
                # 画像の場合、フレーム追加だけ
                edit.append_frames(new_model)
            else:
                raise TypeError(f"Unexpected model type ({type(new_model)})")
            # サムネイルのリサイズ設定を元に戻す
            edit.set_size(ImageLayer.THUMBNAIL, preserved_thumbnail_resize_desc)
            edit.set_resize_mode(ImageLayer.THUMBNAIL, preserved_thumbnail_resize_mode)
