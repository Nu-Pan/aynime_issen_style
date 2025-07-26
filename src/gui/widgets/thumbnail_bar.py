# std
from typing import Callable, List, Iterable
import time

# Tk/CTk
from tkinter import Event
import customtkinter as ctk

# utils
from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.ctk import configure_presence
from utils.image import AISImage

# gui
from gui.model.contents_cache import ResizeDesc, ImageLayer, AspectRatioPattern
from gui.model.aynime_issen_style import AynimeIssenStyleModel


class SentinelItem(ctk.CTkFrame):
    """
    サムネイルリスト上の「番兵」的なアイテム
    ドロップ可能であることをユーザーに伝えるためだけに存在
    """

    def __init__(self, master: "ThumbnailBar"):
        """
        コンストラクタ

        Args:
            master (ThumbnailBar): このアイテムが所属する ThumbnailBar
            thumbnail_height (int): サムネイルのサイズ（縦方向）
        """
        super().__init__(master)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

        # 通知ラベルを生成
        # NOTE
        #   ラベルの四隅の外側はテーマ色でフィルされてしまうので、角丸のないラベルを使用する(corner_radius=0)。
        self._text_label = ctk.CTkLabel(
            self,
            text="Drop image file(s) HERE",
            bg_color="transparent",
            font=default_font,
        )
        self._text_label.pack(fill="both", expand=True)
        self._text_label.configure(padx=WIDGET_PADDING, pady=WIDGET_PADDING)


class ThumbnailItem(ctk.CTkFrame):
    """
    画像をサムネイル表示するためのウィジェット
    THumbnailBar を構成するアイテムとして使う
    """

    def __init__(
        self, master: "ThumbnailBar", model: AynimeIssenStyleModel, frame_index: int
    ):
        """
        コンストラクタ
        """
        super().__init__(master)

        # 現在表示している画像
        # NOTE
        #   現在表示している AISImage のインスタンスをウィジェットから取ることはできない。
        #   そのため、この階層でキャッシュ情報を保持しておく
        self._current_frame = None

        # 引数を保存
        self._master = master
        self._model = model
        self._frame_index = frame_index

        # プレビュー用画像を取得
        thumbnail_image = self._model.video.get_frame(
            ImageLayer.THUMBNAIL, self._frame_index
        )
        if not isinstance(thumbnail_image, AISImage):
            raise TypeError()

        # クリック操作受付用のボタン
        self._button = ctk.CTkButton(
            self,
            image=thumbnail_image.photo_image,
            text="",
            width=thumbnail_image.width,
            height=thumbnail_image.height,
            fg_color="transparent",
            hover=False,
        )
        self._button.pack()

        # マウスイベント
        self._button.bind("<Button-1>", self._on_click_left)
        self._button.bind("<Button-3>", self._on_click_right)

        # リサイズハンドラ
        self.bind("<Configure>", self._on_resize)

    def update_image(self):
        """
        サムネイルの更新が必要なときに呼び出すべき関数
        ハンドラじゃない
        """
        new_frame = self._model.video.get_frame(ImageLayer.THUMBNAIL, self._frame_index)
        if new_frame != self._current_frame:
            if isinstance(new_frame, AISImage):
                configure_presence(self._button, new_frame.photo_image)
                self._current_frame = new_frame
            else:
                configure_presence(self._button, "NO IMAGE")
                self._current_frame = None

    def _on_click_left(self, event: Event):
        """
        マウスクリック（左ボタン）
        """
        enable = self._model.video.get_enable(self._frame_index)
        self._model.video.set_enable(self._frame_index, not enable)

    def _on_click_right(self, event: Event):
        """
        マウスクリック（右ボタン）
        """
        self._model.video.delete_frame(self._frame_index)

    def _on_resize(self, _):
        """
        リサイズハンドラ
        """
        # 適切なサイズを解決
        actual_width = self.winfo_width()
        actual_height = self.winfo_height()
        print(f"set_size: {actual_height}")
        self._model.video.set_size(
            ImageLayer.THUMBNAIL,
            ResizeDesc(AspectRatioPattern.E_RAW, None, actual_height),
        )


class ThumbnailBar(ctk.CTkScrollableFrame):
    """
    画像（アイテム）サムネイルを横並びでリスト表示可能なウィジェット
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        model: AynimeIssenStyleModel,
        thumbnail_height: int,
        **kwargs,
    ):
        """
        コンストラクタ

        Args:
            master (CTkBaseClass): 親ウィジェット
            thumbnail_height (int): サムネイルの大きさ（縦方向）
            on_change (Callable): サムネイルに変化があった場合に呼び出されるハンドラ
        """
        super().__init__(
            master,
            height=thumbnail_height,
            orientation="horizontal",
            **kwargs,
        )

        # 引数保存
        self._model = model

        # 内部状態
        self._items: list[ThumbnailItem] = []

        # 高さ方向はいっぱいまで拡大
        self.grid_rowconfigure(0, weight=1)

        # 番兵アイテムを追加
        self._sentinel_item = SentinelItem(self)
        self._sentinel_item.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING
        )

        # マウスホイール横スクロール設定
        self._parent_canvas.bind("<Enter>", self._mouse_enter)
        self._parent_canvas.bind("<Leave>", self._mouse_leave)

        # コールバック設定
        self._model.video.register_notify_handler(
            ImageLayer.THUMBNAIL, self._on_thumbnail_change
        )

    def _on_thumbnail_change(self):
        """
        動画に変更があった時に呼び出されるハンドラ
        """
        # UI 上とモデル上とでフレーム数をあわせる（ウィジェット削除）
        while len(self._items) > self._model.video.num_total_frames:
            self._items[-1].destroy()
            self._items.pop()

        # UI 上とモデル上とでフレーム数をあわせる（ウィジェット追加）
        while len(self._items) < self._model.video.num_total_frames:
            new_item = ThumbnailItem(self, self._model, len(self._items))
            new_item.grid(
                row=0, column=len(self._items), padx=WIDGET_PADDING, pady=WIDGET_PADDING
            )
            self._items.append(new_item)

        pass

        # 番兵アイテムを移動
        current_sentinel_column = self._sentinel_item.grid_info()["column"]
        new_sentinel_column = len(self._items)
        if current_sentinel_column != new_sentinel_column:
            self._sentinel_item.grid(
                row=0,
                column=new_sentinel_column,
                padx=WIDGET_PADDING,
                pady=WIDGET_PADDING,
            )

        # 全ウィジェットの表示を更新
        for item in self._items:
            item.update_image()

    def _mouse_enter(self, _):
        """
        ウィジェットにマウスカーソルが入った時のハンドラ
        """
        # NOTE
        #   カーソルが入った時だけマウスホイールのハンドラを有効化する
        self._parent_canvas.bind_all("<MouseWheel>", self._on_mousewheel_windows)

    def _mouse_leave(self, _):
        """
        ウィジェットからマウスカーソルが離れた時のハンドラ
        """
        # NOTE
        #   カーソルが外れたらマウスホイールのハンドラを無効化する
        self._parent_canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel_windows(self, event: Event):
        """
        マウスホイールころころハンドラ

        Args:
            event (_type_): イベント
        """
        # NOTE
        #   普通のスクロールで横方向にスクロール
        self._parent_canvas.xview_scroll(-event.delta, "units")
