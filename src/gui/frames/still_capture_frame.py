# std
from typing import List, Tuple, cast
from pathlib import Path

# Tk/CTk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent
import tkinter.messagebox as mb
from tkinter import Event

# utils
from utils.constants import WIDGET_PADDING
from utils.image import AspectRatioPattern, ResizeDesc, AISImage
from gui.model.contents_cache import (
    ImageModel,
    VideoModel,
    save_content_model,
    load_content_model,
    ImageModelEditSession,
)
from utils.windows import file_to_clipboard, register_global_hotkey_handler
from utils.ctk import show_notify_label, show_error_dialog
from utils.capture import *

# gui
from gui.widgets.still_label import StillLabel
from gui.widgets.size_pattern_selection_frame import (
    SizePatternSlectionFrame,
)
from gui.widgets.ais_entry import AISEntry
from gui.widgets.ais_slider import AISSlider
from gui.model.contents_cache import ImageLayer

# local
from utils.constants import CAPTURE_FRAME_BUFFER_DURATION_IN_SEC, DEFAULT_FONT_FAMILY
from gui.model.aynime_issen_style import AynimeIssenStyleModel


class StillCaptureFrame(ctk.CTkFrame, TkinterDnD.DnDWrapper):
    """
    スチル画像のキャプチャ操作を行う CTk フレーム
    """

    UI_TAB_NAME = "「一閃」"

    def __init__(self, master, model: AynimeIssenStyleModel, **kwargs):
        """
        コンストラクタ

        Args:
            master (_type_): 親ウィジェット
            model (AynimeIssenStyleModel): モデル
        """
        super().__init__(master, **kwargs)

        # モデル
        self.model = model
        self.model.still.register_notify_handler(ImageLayer.NIME, self.on_nime_changed)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)

        # レイアウト設定
        self.columnconfigure(0, weight=1)

        # プレビューラベル兼キャプチャボタン
        self.preview_label = StillLabel(self, model.still, "Click Here or Ctrl+Alt+P")
        self.rowconfigure(0, weight=1)
        self.preview_label.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.preview_label.bind("<Button-1>", self.on_preview_label_click)

        # グローバルホットキーを登録
        register_global_hotkey_handler(self, self.on_preview_label_click, None)

        # アニメ名テキストボックス
        self.nime_name_entry = AISEntry(self, placeholder_text="Override NIME name ...")
        self.rowconfigure(2, weight=0)
        self.nime_name_entry.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.nime_name_entry.register_handler(self.on_nime_name_entry_changed)

        # 解像度選択フレーム
        self._size_pattern_selection_frame = SizePatternSlectionFrame(
            self,
            self.on_resolution_changes,
            AspectRatioPattern.E_RAW,
            ResizeDesc.Pattern.E_HD,
            [ar for ar in AspectRatioPattern],
            [
                ResizeDesc.Pattern.E_RAW,
                ResizeDesc.Pattern.E_VGA,
                ResizeDesc.Pattern.E_HD,
                ResizeDesc.Pattern.E_FHD,
                ResizeDesc.Pattern.E_4K,
            ],
        )
        self.rowconfigure(3, weight=0)
        self._size_pattern_selection_frame.grid(
            row=2, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # キャプチャタイミングスライダー
        CAPTURE_TIMING_STEP_IN_SEC = 0.05
        MIN_CAPTURE_TIMING_IN_SEC = 0
        MAX_CAPTURE_TIMING_IN_SEC = min(1, CAPTURE_FRAME_BUFFER_DURATION_IN_SEC)
        NUM_CAPTURE_TIMING_STEPS = (
            round(
                (MAX_CAPTURE_TIMING_IN_SEC - MIN_CAPTURE_TIMING_IN_SEC)
                / CAPTURE_TIMING_STEP_IN_SEC
            )
            + 1
        )
        self._capture_timing_slider = AISSlider(
            self,
            "TIMING",
            [
                CAPTURE_TIMING_STEP_IN_SEC * step + MIN_CAPTURE_TIMING_IN_SEC
                for step in range(NUM_CAPTURE_TIMING_STEPS)
            ],
            lambda lho, rho: abs(lho - rho),
            lambda x: f"{x:4.2f}",
            "SEC",
        )
        self._capture_timing_slider.grid(
            row=3, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self._capture_timing_slider.set_value(0.35)

        # ファイルドロップ関係
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop_file)

    def on_preview_label_click(self, event: Event) -> None:
        """
        プレビューラベルクリックイベントハンドラ

        Args:
            event (_type_): イベントオブジェクト
        """
        # キャプチャ
        try:
            pil_raw_capture_image = self.model.stream.capture_still(
                self._capture_timing_slider.value
            )
        except Exception as e:
            show_notify_label(
                self,
                "error",
                "キャプチャに失敗。\n"
                "キャプチャ対象のディスプレイ・ウィンドウの選択を忘れている？\n"
                f"what: {e}",
            )
            return

        # アニメ名を解決
        if self.nime_name_entry.text != "":
            actual_nime_name = "<NIME>" + self.nime_name_entry.text
        else:
            window_name = self.model.stream.nime_window_text
            if window_name is not None and "<NIME>" in window_name:
                actual_nime_name = window_name
            else:
                actual_nime_name = None

        # モデルに反映
        # NOTE
        #   通知の結果エクスポートも行われる
        with ImageModelEditSession(self.model.still) as edit:
            edit.set_raw_image(pil_raw_capture_image)
            edit.set_nime_name(actual_nime_name)
            edit.set_time_stamp(None)

    def on_nime_name_entry_changed(self, text: str):
        """
        アニメ名テキストボックスが変更されたときに呼び出される
        """
        with ImageModelEditSession(self.model.still) as edit:
            if text != "":
                edit.set_nime_name(text)
            else:
                edit.set_nime_name(self.model.stream.nime_window_text)

    def on_resolution_changes(
        self, aspect_ratio: AspectRatioPattern, resolution: ResizeDesc.Pattern
    ):
        """
        解像度が変更された時に呼び出される

        Args:
            aspect_ratio (AspectRatio): アスペクト比
            resolution (Resolution): 解像度
        """
        # リサイズを適用
        # NOTE
        #   リサイズさえすればコールバック経由でエクスポートまで走るはず
        with ImageModelEditSession(self.model.still) as edit:
            edit.set_size(
                ImageLayer.NIME, ResizeDesc.from_pattern(aspect_ratio, resolution)
            )

    def on_nime_changed(self):
        """
        NIME 画像に変更があった際に呼び出されるハンドラ
        """
        self.export_image()

    def export_image(self):
        """
        画像のエクスポート処理を行う
        """
        # キャプチャがない場合は何もしない
        if self.model.still.get_image(ImageLayer.NIME) is None:
            return

        # キャプチャをローカルにファイルに保存する
        nime_file_path = save_content_model(self.model.still)
        if not isinstance(nime_file_path, Path):
            raise TypeError(
                f"Expected Path, got {type(nime_file_path)}. "
                "integrated_save_image should return a single Path."
            )

        # 保存したファイルをクリップボードに乗せる
        file_to_clipboard(nime_file_path)

        # クリップボード転送完了通知
        show_notify_label(
            self,
            "info",
            "「一閃」\nクリップボード転送完了",
            on_click_handler=self.on_preview_label_click,
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
        file_paths = cast(Tuple[str], self.tk.splitlist(event_data))
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

        # モデルの中身を展開
        if isinstance(load_result, ImageModel):
            image = load_result.get_image(ImageLayer.RAW)
            nime_name = load_result.nime_name
            time_stamp = load_result.time_stamp
        elif isinstance(load_result, VideoModel):
            image = load_result.get_frame(ImageLayer.RAW, 0)
            nime_name = load_result.nime_name
            time_stamp = load_result.time_stamp
        else:
            show_error_dialog(f"ファイルロードに失敗。", TypeError(type(load_result)))
            return

        # アニメ名を解決
        if self.nime_name_entry.text != "":
            actual_nime_name = self.nime_name_entry.text
        else:
            actual_nime_name = nime_name

        # AIS モデルに設定
        with ImageModelEditSession(self.model.still) as edit:
            edit.set_raw_image(image)
            edit.set_nime_name(actual_nime_name)
            edit.set_time_stamp(time_stamp)
