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
from utils.pil import AspectRatio, Resolution
from utils.integrated_image import (
    IntegratedImage,
    integrated_save_image,
    integrated_load_image,
)
from utils.windows import file_to_clipboard, register_global_hotkey_handler
from utils.constants import APP_NAME_JP, NIME_DIR_PATH
from utils.ctk import show_notify
from utils.std import flatten

# gui
from gui.widgets.still_frame import StillLabel
from gui.widgets.size_pattern_selection_frame import (
    SizePatternSlectionFrame,
)

# local
from aynime_issen_style_model import AynimeIssenStyleModel


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

        # 参照を保存
        self.model = model

        # レイアウト設定
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # プレビューラベル兼キャプチャボタン
        self.preview_label = StillLabel(self)
        self.preview_label.set_contents(text="Click Here or Ctrl+Alt+P")
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
            AspectRatio.E_RAW,
            Resolution.E_RAW,
            [AspectRatio.E_RAW, AspectRatio.E_16_9, AspectRatio.E_4_3],
            [
                Resolution.E_RAW,
                Resolution.E_VGA,
                Resolution.E_HD,
                Resolution.E_FHD,
                Resolution.E_4K,
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
        # まずはキャプチャ
        try:
            pil_raw_capture_image = self.model.capture()
        except Exception as e:
            mb.showerror(
                APP_NAME_JP,
                f"キャプチャに失敗。多分キャプチャ対象のディスプレイ・ウィンドウの選択を忘れてるよ。\n{e.args}",
            )
            return

        # 統合画像を生成
        capture_image = IntegratedImage(pil_raw_capture_image, None)
        capture_image.nime(
            self._size_pattern_selection_frame.aspect_ratio,
            self._size_pattern_selection_frame.resolution,
        )

        # プレビューに設定
        self.preview_label.set_contents(image=capture_image)

        # コールバックを設定
        capture_image.register_on_nime_changed(self.on_nime_changed)

        # エクスポート処理
        # NOTE
        #   リサイズ --> コールバック登録の順番なので、
        #   明示的にエクスポートを呼び出す必要がある。
        self.export_image()

    def on_resolution_changes(self, aspect_ratio: AspectRatio, resolution: Resolution):
        """
        解像度が変更された時に呼び出される

        Args:
            aspect_ratio (AspectRatio): アスペクト比
            resolution (Resolution): 解像度
        """
        # リサイズを適用
        # NOTE
        #   リサイズさえすればコールバック経由でエクスポートまで走るはず
        image = self.preview_label.image
        if image is not None:
            image.nime(aspect_ratio, resolution)

    def on_nime_changed(self):
        """
        NIME 画像に変更があった際に呼び出されるハンドラ
        """
        self.preview_label._on_resize(None)
        self.export_image()

    def export_image(self):
        """
        画像のエクスポート処理を行う
        """
        # キャプチャがない場合は何もしない
        image = self.preview_label.image
        if image is None:
            return

        # キャプチャをローカルにファイルに保存する
        nime_file_path = integrated_save_image(image)
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
        exceptions: List[Exception] = []
        for file_path in paths:
            try:
                load_result = integrated_load_image(Path(file_path))
                if isinstance(load_result, IntegratedImage):
                    image = load_result
                    break
                elif isinstance(load_result, list) and len(load_result) > 0:
                    image = load_result[0]
                    break
                else:
                    raise TypeError(load_result)
            except Exception as e:
                exceptions.append(e)

        # 読み込めてない場合はここでおしまい
        if image is None:
            if len(exceptions) > 0:
                mb.showerror(
                    APP_NAME_JP,
                    f"画像・動画の読み込みに失敗。\n{[str(e.args) for e in exceptions]}",
                )
            return

        # アス比・解像度を反映
        image.nime(
            self._size_pattern_selection_frame.aspect_ratio,
            self._size_pattern_selection_frame.resolution,
        )

        # プレビューに設定
        self.preview_label.set_contents(image)

        # コールバックを設定
        image.register_on_nime_changed(self.on_nime_changed)
