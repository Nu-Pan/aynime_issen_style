# std
from typing import cast
from pathlib import Path

# Tk/CTk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent
from tkinter import Event

# utils
from utils.image import AspectRatioPattern, ResolutionPattern, ResizeDesc
from gui.model.contents_cache import (
    ImageModel,
    VideoModel,
    save_content_model,
    load_content_model,
    ImageModelEditSession,
)
from utils.windows import file_to_clipboard
from utils.ctk import show_notify_label, show_error_dialog
from utils.capture import *
from utils.constants import CAPTURE_FRAME_BUFFER_DURATION_IN_SEC
from utils.duration_and_frame_rate import (
    FILM_TIMELINE_IN_FPS,
    STANDARD_FRAME_RATES,
    DFREntry,
    DFR_MAP,
)

# gui
from gui.widgets.still_label import StillLabel
from gui.widgets.size_pattern_selection_frame import (
    SizePatternSlectionFrame,
)
from gui.widgets.ais_frame import AISFrame
from gui.widgets.ais_entry import AISEntry
from gui.widgets.ais_slider import AISSlider
from gui.widgets.video_label import VideoLabel, VideoModelEditSession
from gui.model.contents_cache import ImageLayer
from gui.model.aynime_issen_style import AynimeIssenStyleModel


class ForeignExportFrame(AISFrame, TkinterDnD.DnDWrapper):
    """
    いろんなサービス（Foreign）向けのエクスポート操作をサポートする CTk フレーム
    """

    UI_TAB_NAME = "転生"

    def __init__(self, master, model: AynimeIssenStyleModel, **kwargs):
        """
        コンストラクタ

        Args:
            master (_type_): 親ウィジェット
            model (AynimeIssenStyleModel): モデル
        """
        super().__init__(master, **kwargs)

        # メンバー保存
        self._model = model

        # レイアウト設定
        self.ais.columnconfigure(0, weight=1)

        # 切り取り結果プレビュー
        self._preview_label = VideoLabel(self, model.foreign, "blank text")
        self.ais.grid_child(self._preview_label, 0, 0)
        self.ais.rowconfigure(0, weight=1)

        # ファイルドロップ関係
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop_file)

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

        # モデルに反映
        # NOTE
        #   スチル画像の場合はフレーム数１の動画としてロードする。
        #   スチル・ビデオで処理分けると実装がダルくなるので、それを避けるための措置。
        with VideoModelEditSession(self._model.foreign) as edit:
            if isinstance(load_result, ImageModel):
                (
                    edit.clear_frames()
                    .set_nime_name(load_result.nime_name)
                    .set_time_stamp(load_result.time_stamp)
                    .set_duration_in_msec(DFR_MAP.default_entry.duration_in_msec)
                    .append_frames(load_result)
                )
            elif isinstance(load_result, VideoModel):
                (
                    edit.clear_frames()
                    .set_nime_name(load_result.nime_name)
                    .set_time_stamp(load_result.time_stamp)
                    .set_duration_in_msec(load_result.duration_in_msec)
                    .append_frames(load_result)
                )
