# std
from typing import cast
from dataclasses import dataclass
import logging

# Tk/CTk
from tkinter import Event
import customtkinter as ctk
from CTkListbox import CTkListbox

# utils
from utils.capture import *
from utils.constants import WIDGET_PADDING, DEFAULT_FONT_FAMILY
from utils.ctk import show_notify_label
from utils.std import traceback_str

# gui
from gui.widgets.still_label import StillLabel
from gui.model.aynime_issen_style import AynimeIssenStyleModel
from gui.model.contents_cache import ImageModelEditSession


@dataclass
class WindowListBoxItem:

    window_handle: WindowHandle
    window_name: str
    is_aynime: bool

    def __str__(self) -> str:
        return self.window_name


class WindowSelectionFrame(ctk.CTkFrame):
    """
    ウィンドウ選択フレームクラス
    """

    UI_TAB_NAME = "構え"

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
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=0, minsize=self.winfo_width() // 2)
        self.columnconfigure(1, weight=1, minsize=self.winfo_width() // 2)

        # ウィンドウ一覧再読み込みボタン
        self.reload_capture_target_list_button = ctk.CTkButton(
            self,
            text="RELOAD",
            command=self.update_list,
            font=default_font,
        )
        self.reload_capture_target_list_button.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # キャプチャ対象リストボックス
        self.capture_target_list_box = CTkListbox(self, multiple_selection=False)
        self.capture_target_list_box.grid(
            row=1,
            column=0,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe",
        )
        self.capture_target_list_box.bind(
            "<<ListboxSelect>>", self.on_capture_target_select
        )

        # フルサイズウィンドウ名表示用
        self.capture_target_full_name_label = ctk.CTkLabel(
            self, font=default_font, fg_color="transparent", bg_color="transparent"
        )
        self.capture_target_full_name_label.grid(
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # プレビュー画像表示用ラベル
        self.capture_target_preview_label = StillLabel(
            self, model.window_selection_image, "Preview"
        )
        self.capture_target_preview_label.grid(
            row=1, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
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
        try:
            self.model.stream.set_capture_window(selection.window_handle)
        except Exception as e:
            # ユーザー向けにはラベルで通知
            show_notify_label(
                self, "error", f'"{selection.window_name}" のキャプチャ開始に失敗'
            )
            # 開発者向けにログを残す
            logging.warning(
                f'Failed to start window capture({selection.window_handle}, "{selection.window_name}")\n{traceback_str(e)}'
            )

        # 描画更新
        with ImageModelEditSession(self.model.window_selection_image) as edit:
            edit.set_raw_image(self.model.stream.capture_still())

        # フルサイズウィンドウ名ラベルを更新
        self.capture_target_full_name_label.configure(text=selection.window_name)

    def update_list(self) -> None:
        """
        ウィンドウリストを更新する
        """
        try:
            # リスト更新ボタンを先に無効化
            self.reload_capture_target_list_button.configure(state=ctk.DISABLED)

            # キャプチャ対象を未選択状態に戻す
            self.model.stream.set_capture_window(None)

            # プレビューをクリア
            with ImageModelEditSession(self.model.window_selection_image) as edit:
                edit.set_raw_image(None)
            self.capture_target_full_name_label.configure(text="Window Full Name")

            # リストをクリア
            self.capture_target_list_box.delete("all")

            # ウィンドウリストを列挙
            raw_items = [
                WindowListBoxItem(window_handle, *get_nime_window_text(window_handle))
                for window_handle in enumerate_windows()
            ]

            # 無名ウィンドウを除外
            raw_items = [item for item in raw_items if item.window_name != ""]

            # ソート
            # NOTE
            #   NIME を先頭に持ってくる
            #   それ以外は ABC 順
            nime_items = sorted(
                [
                    WindowListBoxItem(
                        item.window_handle, "★" + item.window_name, item.is_aynime
                    )
                    for item in raw_items
                    if item.is_aynime
                ],
                key=lambda item: item.window_name,
            )
            other_items = sorted(
                [item for item in raw_items if not item.is_aynime],
                key=lambda item: item.window_name,
            )
            for item in nime_items + other_items:
                self.capture_target_list_box.insert(
                    ctk.END,
                    item,
                    False,
                )
            self.capture_target_list_box.update()

            # NIME があるならそれを自動選択
            if len(nime_items) > 0:
                self.capture_target_list_box.select(0)

        finally:
            # 必ず最後にボタンを有効に戻す
            self.reload_capture_target_list_button.configure(state=ctk.NORMAL)
