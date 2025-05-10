import customtkinter as ctk
from PIL import ImageTk
from pathlib import Path
from datetime import datetime
import warnings

from aynime_issen_style_model import AynimeIssenStyleModel
from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.pil import (
    isotropic_downscale_image_in_rectangle,
    save_pil_image_to_jpeg_file,
)
from utils.windows import file_to_clipboard, register_global_hotkey_handler


class CaptureFrame(ctk.CTkFrame):
    """
    キャプチャ操作を行う CTk フレーム
    """

    def __init__(self, master, model: AynimeIssenStyleModel, **kwargs):
        """
        コンストラクタ

        Args:
            master (_type_): 親ウィジェット
            model (AynimeIssenStyleModel): モデル
        """
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

        # 参照を保存
        self.model = model

        # プレビューラベル兼キャプチャボタン
        self.preview_label = ctk.CTkLabel(
            self, text="Click Here or Ctrl+Alt+P", font=default_font
        )
        self.preview_label.pack(
            fill="both", expand=True, padx=WIDGET_PADDING, pady=WIDGET_PADDING
        )
        self.preview_label.bind("<Button-1>", self.on_preview_label_click)
        self.preview_label.bind("<Configure>", self.on_preview_label_resize)

        # リサイズ前のキャプチャ画像
        self.original_capture_image = None

        # グローバルホットキーを登録
        register_global_hotkey_handler(self, self.on_preview_label_click, None)

    def on_preview_label_click(self, event) -> None:
        """
        プレビューラベルクリックイベントハンドラ

        Args:
            event (_type_): イベントオブジェクト
        """
        # まずはキャプチャ＆プレビュー
        self.update_original_capture_image()
        self.update_preview_label()

        # キャプチャ画像がない場合は何もしない
        if self.original_capture_image is None:
            return

        # キャプチャをローカルにファイル保存する
        nime_dir_path = Path(".\\nime")
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        jpeg_file_path = nime_dir_path / (date_str + ".jpg")
        save_pil_image_to_jpeg_file(self.original_capture_image, jpeg_file_path)

        # 保存したファイルをクリップボードに乗せる
        file_to_clipboard(jpeg_file_path)

        # クリップボード転送完了通知
        self.show_notify("「一閃」\nクリップボード転送完了")

    def on_preview_label_resize(self, event) -> None:
        """
        フレームのリサイズイベントハンドラ

        Args:
            event (_type_): イベントオブジェクト
        """
        self.update_preview_label()

    def update_original_capture_image(self) -> None:
        """
        選択されたウィンドウのキャプチャを撮影し、その画像で内部状態を更新する。
        """
        try:
            self.original_capture_image = self.model.capture()
        except Exception as e:
            self.original_capture_image = None
            self.preview_label.configure(
                text=f"一閃失敗\n多分、キャプチャ対象のディスプレイ・ウィンドウの選択を忘れてるよ\n{e.args}"
            )

    def update_preview_label(self) -> None:
        """
        プレビューの表示状態を更新する。
        キャプチャは行わない。
        """
        # キャプチャ画像がない場合は何もしない
        if self.original_capture_image is None:
            return

        # 適切な画像サイズを計算
        # NOTE
        #   フレームが一度も表示されていない段階ではフレームサイズとして (1, 1) が報告される。
        #   こういった特殊ケースで画像サイズが異常値になるのを防ぐため、最低保障値を付ける。
        actual_image_width = max(self.capture_image_width, 32)
        actual_image_height = max(self.capture_image_height, 32)

        # 画像をリサイズ
        pil_image = isotropic_downscale_image_in_rectangle(
            self.original_capture_image, actual_image_width, actual_image_height
        )

        # 画像をラベルに表示
        tk_image = ImageTk.PhotoImage(pil_image)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="CTkLabel Warning: Given image is not CTkImage",
                category=UserWarning,
            )
            self.preview_label.configure(image=tk_image, text="")

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
        self._status_label = ctk.CTkLabel(
            self,
            text=message,
            fg_color="#3a8d3f",
            text_color="white",
            corner_radius=0,
            font=default_font,
        )
        self._status_label.place(relx=0.5, rely=0.5, anchor="center")
        self._status_label.configure(padx=WIDGET_PADDING, pady=WIDGET_PADDING)
        self._status_label.bind("<Button-1>", self.on_preview_label_click)

        # 通知ラベルは一定時間後に自動破棄
        self.after(duration_ms, self.hidden_notify)

    def hidden_notify(self) -> None:
        """
        通知ラベルを隠す
        """
        if self._status_label is not None:
            self._status_label.destroy()
            self._status_label = None

    @property
    def capture_image_width(self) -> int:
        """
        現在のウィジェットの状態における、キャプチャ画像の適切なサイズを得る

        Returns:
            int: キャプチャ画像サイズ（横）
        """
        return self.preview_label.winfo_width() - 2 * WIDGET_PADDING

    @property
    def capture_image_height(self) -> int:
        """
        現在のウィジェットの状態における、キャプチャ画像の適切なサイズを得る

        Returns:
            int: キャプチャ画像サイズ（縦）
        """
        return self.preview_label.winfo_height() - 2 * WIDGET_PADDING
