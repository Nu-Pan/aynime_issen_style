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
from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.image import AspectRatioPattern, ResizeDesc, AISImage
from gui.model.contents_cache import (
    ImageModel,
    VideoModel,
    save_content_model,
    load_content_model,
)
from utils.windows import file_to_clipboard, register_global_hotkey_handler
from utils.constants import APP_NAME_JP, NIME_DIR_PATH
from utils.ctk import show_notify, show_error_dialog

# gui
from gui.widgets.still_label import StillLabel
from gui.widgets.size_pattern_selection_frame import (
    SizePatternSlectionFrame,
)
from gui.model.contents_cache import ImageLayer

# local
from gui.model.aynime_issen_style import AynimeIssenStyleModel


class StillCaptureFrame(ctk.CTkFrame, TkinterDnD.DnDWrapper):
    """
    スチル画像のキャプチャ操作を行う CTk フレーム
    """

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

        # レイアウト設定
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # プレビューラベル兼キャプチャボタン
        self.preview_label = StillLabel(self, model.still, "Click Here or Ctrl+Alt+P")
        self.preview_label.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.preview_label.bind("<Button-1>", self.on_preview_label_click)

        # グローバルホットキーを登録
        register_global_hotkey_handler(self, self.on_preview_label_click, None)

        # 解像度選択フレーム
        self._size_pattern_selection_frame = SizePatternSlectionFrame(
            self,
            self.on_resolution_changes,
            AspectRatioPattern.E_RAW,
            ResizeDesc.Pattern.E_HD,
            [
                AspectRatioPattern.E_RAW,
                AspectRatioPattern.E_16_9,
                AspectRatioPattern.E_4_3,
            ],
            [
                ResizeDesc.Pattern.E_RAW,
                ResizeDesc.Pattern.E_VGA,
                ResizeDesc.Pattern.E_HD,
                ResizeDesc.Pattern.E_FHD,
                ResizeDesc.Pattern.E_4K,
            ],
        )
        self._size_pattern_selection_frame.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

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
            pil_raw_capture_image = self.model.capture.capture()
        except Exception as e:
            show_error_dialog(
                "キャプチャに失敗。多分キャプチャ対象のディスプレイ・ウィンドウの選択を忘れてるよ。",
                e,
            )
            return

        # モデルに反映
        self.model.still.set_raw_image(pil_raw_capture_image, None)

        # エクスポート処理
        # NOTE
        #   リサイズ --> コールバック登録の順番なので、
        #   明示的にエクスポートを呼び出す必要がある。
        self.export_image()

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
        self.model.still.set_size(
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
        show_notify(
            self,
            "「一閃」\nクリップボード転送完了",
            on_click_handler=self.on_preview_label_click,
        )

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

        # 読み込み処理
        # NOTE
        #   複数の画像ファイルがドロップ or 動画系ファイルがドロップされた場合、
        #   先頭のフレームを代表して取り込む。
        paths = cast(Tuple[str], self.tk.splitlist(event_data))
        image = None
        time_stamp = None
        exceptions: List[Exception] = []
        for file_path in paths:
            try:
                load_result = load_content_model(Path(file_path))
                if isinstance(load_result, ImageModel):
                    image = load_result.get_image(ImageLayer.RAW)
                    time_stamp = load_result.time_stamp
                    break
                elif isinstance(load_result, VideoModel):
                    image = load_result.get_frame(ImageLayer.RAW, 0)
                    time_stamp = load_result.time_stamp
                    break
                else:
                    raise TypeError(load_result)
            except Exception as e:
                exceptions.append(e)

        # 読み込めてない場合はここでおしまい
        if not isinstance(image, AISImage) or not isinstance(time_stamp, str):
            if len(exceptions) > 0:
                show_error_dialog("画像・動画の読み込みに失敗。", exceptions)
            return

        # モデルに設定
        self.model.still.set_raw_image(image, time_stamp)
