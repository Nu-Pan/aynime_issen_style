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
    save_content_model,
    load_content_model,
    ImageModelEditSession,
)
from utils.windows import file_to_clipboard
from utils.ctk import show_notify_label, show_error_dialog
from utils.capture import *
from utils.constants import (
    CAPTURE_FRAME_BUFFER_DURATION_IN_SEC,
    WIDGET_MIN_WIDTH,
    WIDGET_MIN_HEIGHT,
)

# gui
from gui.widgets.still_label import StillLabel
from gui.widgets.size_pattern_selection_frame import (
    SizePatternSlectionFrame,
)
from gui.widgets.ais_frame import AISFrame
from gui.widgets.ais_entry import AISEntry
from gui.widgets.ais_slider import AISSlider
from gui.model.contents_cache import ImageLayer
from gui.model.aynime_issen_style import AynimeIssenStyleModel


class StillCaptureFrame(AISFrame, TkinterDnD.DnDWrapper):
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
        self._model = model
        self._model.still.register_layer_changed_handler(
            ImageLayer.NIME, self._on_nime_changed
        )

        # レイアウト設定
        self.ais.columnconfigure(0, weight=1)

        # プレビューラベル兼キャプチャボタン
        self._preview_label = StillLabel(self, model.still, "Click Here to Capture")
        self.ais.grid_child(self._preview_label, 0, 0, 1, 2)
        self.ais.rowconfigure(0, weight=1)
        self._preview_label.bind("<Button-1>", self._on_preview_label_click)

        # グローバルホットキーを登録
        # NOTE
        #   I は「一閃」の頭文字
        self._model.global_hotkey.register(
            "I", lambda: self._on_preview_label_click(None)
        )

        # アニメ名テキストボックス
        self._nime_name_entry = AISEntry(
            self, placeholder_text="Override NIME name ..."
        )
        self.ais.grid_child(self._nime_name_entry, 1, 0)
        self.ais.rowconfigure(1, weight=0)
        self._nime_name_entry.register_handler(self._on_nime_name_entry_changed)

        # 解像度選択フレーム
        self._size_pattern_selection_frame = SizePatternSlectionFrame(
            self,
            model,
            self._on_resolution_changes,
            AspectRatioPattern.E_RAW,
            ResolutionPattern.E_HD,
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
        self.ais.grid_child(self._size_pattern_selection_frame, 2, 0)
        self.ais.rowconfigure(2, weight=0)

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
        self.ais.grid_child(self._capture_timing_slider, 3, 0)
        self._capture_timing_slider.set_value(
            self._model.user_properties.get("still_capture_timing", 0.1)
        )
        self._capture_timing_slider.register_handler(
            self._on_capture_timing_slider_changed
        )

        # 上書きセーブボタン
        self._save_overwrite_button = ctk.CTkButton(
            self,
            text="STORAGE",
            width=2 * WIDGET_MIN_WIDTH,
            height=WIDGET_MIN_HEIGHT,
            command=lambda: self._on_save_button_clicked(False),
        )
        self.ais.grid_child(self._save_overwrite_button, 1, 1, 2, 1)

        # 新規セーブボタン
        self._save_new_button = ctk.CTkButton(
            self,
            text="STORAGE AS",
            width=2 * WIDGET_MIN_WIDTH,
            height=WIDGET_MIN_HEIGHT,
            command=lambda: self._on_save_button_clicked(True),
        )
        self.ais.grid_child(self._save_new_button, 3, 1, 1, 1)

        # ファイルドロップ関係
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop_file)

    def _on_nime_changed(self):
        """
        NIME 画像に変更があった際に呼び出されるハンドラ
        """
        # エイリアス
        model = self._model.still

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

    def _on_preview_label_click(self, event: Event | None) -> None:
        """
        プレビューラベルクリックイベントハンドラ

        Args:
            event (_type_): イベントオブジェクト
        """
        # キャプチャ
        try:
            pil_raw_capture_image = self._model.stream.capture_still(
                self._capture_timing_slider.value
            )
        except Exception as e:
            show_notify_label(
                self,
                "error",
                "キャプチャに失敗。\n"
                "キャプチャ対象のディスプレイ・ウィンドウの選択を忘れている？",
                exception=e,
            )
            return

        # アニメ名を解決
        if self._nime_name_entry.text != "":
            actual_nime_name = self._nime_name_entry.text
        else:
            actual_nime_name = self._model.stream.nime_window_text

        # モデルに反映
        with ImageModelEditSession(self._model.still) as edit:
            edit.set_raw_image(pil_raw_capture_image)
            edit.set_nime_name(actual_nime_name)
            edit.set_time_stamp(None)

        # エクスポート
        self._on_save_button_clicked(False)

    def _on_nime_name_entry_changed(self, text: str):
        """
        アニメ名テキストボックスが変更されたときに呼び出される
        """
        with ImageModelEditSession(self._model.still) as edit:
            if text != "":
                edit.set_nime_name(text)
            else:
                edit.set_nime_name(self._model.stream.nime_window_text)

    def _on_resolution_changes(
        self, aspect_ratio: AspectRatioPattern, resolution: ResolutionPattern
    ):
        """
        解像度が変更された時に呼び出される

        Args:
            aspect_ratio (AspectRatio): アスペクト比
            resolution (Resolution): 解像度
        """
        # リサイズを適用
        with ImageModelEditSession(self._model.still) as edit:
            edit.set_size(ImageLayer.NIME, ResizeDesc(aspect_ratio, resolution))

    def _on_capture_timing_slider_changed(self, value: float):
        """
        キャプチャタイミングスライダーに変更があった時に呼び出されるハンドラ
        """
        self._model.user_properties.set("still_capture_timing", value)

    def _on_save_button_clicked(self, update_timestamp: bool):
        """
        画像のセーブ処理を行う
        """
        # エイリアス
        model = self._model.still

        # キャプチャがない場合は何もしない
        if model.get_image(ImageLayer.NIME) is None:
            show_notify_label(self, "info", "キャプチャ画像なし")
            return

        # タイムスタンプ更新
        if update_timestamp:
            with ImageModelEditSession(model) as edit:
                edit.set_time_stamp(None)

        # 互換性設定をロード
        compat = self._model.user_properties.get("save_content_model_compat", False)

        # キャプチャをローカルにファイルに保存する
        try:
            nime_file_path = save_content_model(model, compat)
        except Exception as e:
            show_notify_label(self, "error", "画像ファイルの保存に失敗", exception=e)
            return

        # 保存したファイルをクリップボードに乗せる
        file_to_clipboard(nime_file_path)

        # クリップボード転送完了通知
        show_notify_label(
            self,
            "info",
            f"{StillCaptureFrame.UI_TAB_NAME}\nクリップボードに「収納」しました",
            on_click_handler=self._on_preview_label_click,
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
            new_model = load_content_model(Path(file_path))
        except Exception as e:
            show_error_dialog("ファイルロードに失敗。", e)
            raise

        # AIS モデルに設定
        with ImageModelEditSession(self._model.still) as edit:
            edit.set_model(new_model)
            if self._nime_name_entry.text != "":
                edit.set_nime_name(self._nime_name_entry.text)
