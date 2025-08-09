# std
from typing import cast
from dataclasses import dataclass

# Tk/CTk
from tkinter import Event
import customtkinter as ctk
from CTkListbox import CTkListbox

# utils
from utils.capture_context import WindowHandle
from utils.constants import WIDGET_PADDING, WINDOW_MIN_WIDTH, DEFAULT_FONT_FAMILY

# gui
from gui.widgets.still_label import StillLabel
from gui.model.aynime_issen_style import AynimeIssenStyleModel
from gui.model.contents_cache import ImageModelEditSession


@dataclass
class WindowListBoxItem:

    window_handle: WindowHandle
    window_name: str

    def __str__(self) -> str:
        return self.window_name


class WindowSelectionFrame(ctk.CTkFrame):
    """
    ウィンドウ選択フレームクラス
    """

    def __init__(
        self, master: ctk.CTkBaseClass, model: AynimeIssenStyleModel, **kwargs
    ):
        """
        コンストラクタ

        Args:
            master (_type_): 親ウィジェット
            model (AynimeIssenStyleModel): モデル
        """
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)

        # モデル
        self.model = model

        # レイアウト設定
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=0, minsize=self.winfo_width() // 2)
        self.columnconfigure(1, weight=1, minsize=self.winfo_width() // 2)

        # 画面左側のフレーム
        self.west_frame = ctk.CTkFrame(self)
        self.west_frame.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.west_frame.configure(width=WINDOW_MIN_WIDTH // 2)
        self.west_frame.columnconfigure(0, weight=1)

        # キャプチャ対象リストボックス
        self.capture_target_list_box = CTkListbox(
            self.west_frame, multiple_selection=False
        )
        self.capture_target_list_box.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.west_frame.rowconfigure(0, weight=1)
        self.capture_target_list_box.bind(
            "<<ListboxSelect>>", self.on_capture_target_select
        )

        # ウィンドウ一覧再読み込みボタン
        self.reload_capture_target_list_button = ctk.CTkButton(
            self.west_frame,
            text="リロード",
            command=self.update_list,
            font=default_font,
        )
        self.west_frame.rowconfigure(1, weight=0)
        self.reload_capture_target_list_button.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 画面右側のフレーム
        self.east_frame = ctk.CTkFrame(self)
        self.east_frame.grid(
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.east_frame.rowconfigure(1, weight=1)
        self.east_frame.columnconfigure(0, weight=1)

        # プレビュー画像表示用ラベル
        self.capture_target_preview_label = StillLabel(
            self.east_frame, model.window_selection_image, "Preview"
        )
        self.capture_target_preview_label.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 初回キャプチャターゲットリスト更新
        self.update_list()
        with ImageModelEditSession(self.model.window_selection_image) as edit:
            edit.set_raw_image(None)

    def on_capture_target_select(self, event: Event) -> None:
        """
        リストボックスの選択イベントハンドラ

        Args:
            event (_type_): イベントオブジェクト
        """
        # キャプチャ対象の変更をモデルに反映
        selection = cast(
            WindowListBoxItem,
            self.capture_target_list_box.get(
                self.capture_target_list_box.curselection()
            ),
        )
        self.model.capture.set_capture_window(selection.window_handle)

        # 描画更新
        with ImageModelEditSession(self.model.window_selection_image) as edit:
            try:
                edit.set_raw_image(self.model.capture.capture())
            except Exception as e:
                edit.set_raw_image(None)

    def update_list(self) -> None:
        """
        ウィンドウリストを更新する
        """
        # リストボックスをクリアしてから、ウィンドウタイトルを取得して追加
        try:
            self.reload_capture_target_list_button.configure(state=ctk.DISABLED)
            self.capture_target_list_box.delete("all")
            raw_items = [
                WindowListBoxItem(
                    window_handle, self.model.capture.get_window_name(window_handle)
                )
                for window_handle in self.model.capture.enumerate_windows()
            ]
            nime_items = sorted(
                [
                    WindowListBoxItem(
                        item.window_handle, item.window_name.replace("<NIME>", "")
                    )
                    for item in raw_items
                    if "<NIME>" in item.window_name
                ],
                key=lambda item: item.window_name,
            )
            other_items = sorted(
                [item for item in raw_items if "<NIME>" not in item.window_name],
                key=lambda item: item.window_name,
            )
            for item in nime_items + other_items:
                self.capture_target_list_box.insert(
                    ctk.END,
                    item,
                    False,
                )
            self.capture_target_list_box.update()
        finally:
            self.reload_capture_target_list_button.configure(state=ctk.NORMAL)
