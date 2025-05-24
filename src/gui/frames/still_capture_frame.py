# std
from pathlib import Path
from datetime import datetime

# Tk/CTk
import customtkinter as ctk
import tkinter.messagebox as mb

# utils
from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.pil import (
    AspectRatio,
    Resolution,
    resize_cover_pattern_size,
    save_pil_image_to_jpeg_file,
)
from utils.windows import file_to_clipboard, register_global_hotkey_handler
from utils.constants import APP_NAME_JP

# gui
from gui.widgets.still_frame import StillLabel
from gui.widgets.size_pattern_selection_frame import (
    SizePatternSlectionFrame,
)

# local
from aynime_issen_style_model import AynimeIssenStyleModel


class StillCaptureFrame(ctk.CTkFrame):
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

        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)
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

    def on_preview_label_click(self, event) -> None:
        """
        プレビューラベルクリックイベントハンドラ

        Args:
            event (_type_): イベントオブジェクト
        """
        # まずはキャプチャ
        try:
            raw_capture_image = self.model.capture()
        except Exception as e:
            capture_image = None
            mb.showerror(
                APP_NAME_JP,
                f"キャプチャに失敗。多分キャプチャ対象のディスプレイ・ウィンドウの選択を忘れてるよ。\n{e.args}",
            )
            return

        # 指定サイズにリサイズの上プレビュー
        capture_image = resize_cover_pattern_size(
            raw_capture_image, self._aspect_ratio, self._resolution
        )
        self.preview_label.set_contents(image=capture_image)

        # キャプチャをローカルにファイル保存する
        nime_dir_path = Path.cwd() / "nime"
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        jpeg_file_path = nime_dir_path / (date_str + ".jpg")
        save_pil_image_to_jpeg_file(capture_image, jpeg_file_path)

        # 保存したファイルをクリップボードに乗せる
        file_to_clipboard(jpeg_file_path)

        # クリップボード転送完了通知
        self.show_notify("「一閃」\nクリップボード転送完了")

    def on_resolution_changes(self, aspect_ratio: AspectRatio, resolution: Resolution):
        """
        解像度が変更された時に呼び出される

        Args:
            aspect_ratio (AspectRatio): アスペクト比
            resolution (Resolution): 解像度
        """
        self._aspect_ratio = aspect_ratio
        self._resolution = resolution

    def show_notify(self, message: str, duration_ms: int = 2000) -> None:
        """
        通知ラベルを表示する
        duration_ms の間、message が表示される。

        Args:
            message (str): メッセージ文字列
            duration_ms (int, optional): 表示時間（ミリ秒）. Defaults to 2000.
        """
        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

        # 通知ラベルを生成
        # NOTE
        #   ラベルの四隅の外側はテーマ色でフィルされてしまうので、角丸のないラベルを使用する(corner_radius=0)。
        status_label = ctk.CTkLabel(
            self,
            text=message,
            fg_color="#3a8d3f",
            text_color="white",
            corner_radius=0,
            font=default_font,
        )
        status_label.place(relx=0.5, rely=0.5, anchor="center")
        status_label.configure(padx=WIDGET_PADDING, pady=WIDGET_PADDING)
        status_label.bind("<Button-1>", self.on_preview_label_click)

        # 通知ラベルは一定時間後に自動破棄
        self.after(duration_ms, status_label.destroy)
