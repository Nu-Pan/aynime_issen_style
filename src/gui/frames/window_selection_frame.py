# std
from typing import cast
from dataclasses import dataclass

# Tk/CTk
from tkinter import Event
import customtkinter as ctk
from CTkListbox import CTkListbox

# utils
from utils.capture import *
from utils.constants import DEFAULT_FONT_FAMILY
from utils.ctk import show_notify_label

# gui
from gui.widgets.still_label import StillLabel
from gui.widgets.ais_frame import AISFrame
from gui.model.aynime_issen_style import AynimeIssenStyleModel
from gui.model.contents_cache import ImageModelEditSession


@dataclass
class WindowListBoxItem:

    window_handle: WindowHandle
    window_name: str
    is_aynime: bool

    def __str__(self) -> str:
        return self.window_name


class WindowSelectionFrame(AISFrame):
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
        self.ais.rowconfigure(1, weight=1)
        self.ais.columnconfigure(0, weight=0, minsize=self.winfo_width() // 2)
        self.ais.columnconfigure(1, weight=1, minsize=self.winfo_width() // 2)

        # ウィンドウ一覧再読み込みボタン
        self._reload_capture_target_list_button = ctk.CTkButton(
            self,
            text="RELOAD",
            command=self.update_list,
            font=default_font,
        )
        self.ais.grid_child(self._reload_capture_target_list_button, 0, 0)

        # キャプチャ対象リストボックス
        self._capture_target_list_box = CTkListbox(self, multiple_selection=False)
        self.ais.grid_child(self._capture_target_list_box, 1, 0)
        self._capture_target_list_box.bind(
            "<<ListboxSelect>>", self.on_capture_target_select
        )

        # フルサイズウィンドウ名表示用
        self._capture_target_full_name_label = ctk.CTkLabel(
            self, font=default_font, fg_color="transparent", bg_color="transparent"
        )
        self.ais.grid_child(self._capture_target_full_name_label, 0, 1)

        # プレビュー画像表示用ラベル
        self._capture_target_preview_label = StillLabel(
            self, model.window_selection_image, "Preview"
        )
        self.ais.grid_child(self._capture_target_preview_label, 1, 1)

        # 初回キャプチャターゲットリスト更新
        self.update_list()

    def on_capture_target_select(self, event: Event) -> None:
        """
        リストボックスの選択イベントハンドラ

        Args:
            event (_type_): イベントオブジェクト
        """
        # キャプチャ対象の変更をモデルに反映
        selection = cast(
            WindowListBoxItem,
            self._capture_target_list_box.get(
                self._capture_target_list_box.curselection()
            ),
        )
        try:
            self.model.stream.set_capture_window(selection.window_handle)
        except Exception as e:
            show_notify_label(
                self,
                "error",
                f'"{selection.window_name}" のキャプチャ開始に失敗',
                exception=e,
            )

        # 描画更新
        with ImageModelEditSession(self.model.window_selection_image) as edit:
            edit.set_raw_image(self.model.stream.capture_still())

        # フルサイズウィンドウ名ラベルを更新
        self._capture_target_full_name_label.configure(text=selection.window_name)

    def update_list(self) -> None:
        """
        ウィンドウリストを更新する
        """
        try:
            # リスト更新ボタンを先に無効化
            self._reload_capture_target_list_button.configure(state=ctk.DISABLED)

            # キャプチャ対象を未選択状態に戻す
            self.model.stream.set_capture_window(None)

            # プレビューをクリア
            with ImageModelEditSession(self.model.window_selection_image) as edit:
                edit.set_raw_image(None)
            self._capture_target_full_name_label.configure(text="Window Full Name")

            # リストをクリア
            self._capture_target_list_box.delete("all")

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
                self._capture_target_list_box.insert(
                    ctk.END,
                    item,
                    False,
                )
            self._capture_target_list_box.update()

            # NIME があるならそれを自動選択
            if len(nime_items) > 0:
                self._capture_target_list_box.select(0)

        finally:
            # 必ず最後にボタンを有効に戻す
            self._reload_capture_target_list_button.configure(state=ctk.NORMAL)
