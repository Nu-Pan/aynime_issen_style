from typing import cast, Tuple, Callable, List
import time

from PIL import Image

from tkinter import Event
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent

import customtkinter as ctk

from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME


class SentinelItem(ctk.CTkFrame):
    """
    サムネイルリスト上の「番兵」的なアイテム
    ドロップ可能であることをユーザーに伝えるためだけに存在
    """

    def __init__(self, master: "ThumbnailBar", thumbnail_height: int):
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
            width=thumbnail_height * 16 // 9,
            height=thumbnail_height,
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
        self, master: "ThumbnailBar", pil_image: Image.Image, thumbnail_height: int
    ):
        """
        コンストラクタ

        Args:
            master (ThumbnailBar): このアイテムが所属する ThumbnailBar
            pil_image (str): このアイテムで保持する画像
            thumbnail_height (int): サムネイルのサイズ（縦方向）
        """
        super().__init__(master)

        # 引数を保存
        self._master = master
        self._original_image = pil_image.copy()

        # サムネイル画像を生成
        thumbnail_width = int(pil_image.width * thumbnail_height / pil_image.height)
        thumbnail_size = (thumbnail_width, thumbnail_height)
        pil_image.thumbnail(thumbnail_size, Image.Resampling.BOX)
        self._tk_image = ctk.CTkImage(
            light_image=pil_image,
            dark_image=pil_image,
            size=(thumbnail_width, thumbnail_height),
        )

        # ドラッグをハンドルするためのボタン
        self._button = ctk.CTkButton(
            self,
            image=self._tk_image,
            text="",
            width=thumbnail_width,
            height=thumbnail_height,
            fg_color="transparent",
            hover=False,
        )
        self._button.pack()

        # マウスドラッグイベント
        # NOTE
        #   こっちは並び替え用
        self._button.bind("<ButtonPress-1>", self._begin_drag)
        self._button.bind("<B1-Motion>", self._on_drag)
        self._button.bind("<ButtonRelease-1>", self._end_drag)

        # マウスクリックイベント
        # NOTE
        #   こっちは有効・無効切り替えと削除
        self._button.bind("<Button-1>", self._on_click_left)
        self._button.bind("<Button-3>", self._on_click_right)

        # 最後にスワップを行った時刻を初期化
        self._last_swap_time = 0.0

    def _begin_drag(self, event: Event):
        """
        ドラッグ開始

        Args:
            event (Event): イベント
        """
        pass

    def _on_drag(self, event: Event):
        """
        ドラッグ中

        Args:
            event (Event): イベント
        """
        # 最後にスワップを行った直後なら無視
        # NOTE
        #   チャタリング防止用
        #   汚い対処法だけど、問題は再現しなくなるのでヨシ
        if (time.time() - self._last_swap_time) < 0.05:
            return

        # ドラッグ先のインデックスを解決
        cur_idx = self._master._items.index(self)
        if event.x < 0:
            new_idx = cur_idx - 1
        elif event.x > self._button.winfo_width():
            new_idx = cur_idx + 1
        else:
            new_idx = cur_idx

        # 不要 or 範囲外なら何もしない
        if new_idx == cur_idx or new_idx < 0 or new_idx >= len(self._master._items):
            return

        # 自分自身の位置を移動させる
        self._master.swap(cur_idx, new_idx)

        # 最後にスワップを行った時刻を更新
        self._last_swap_time = time.time()

    def _end_drag(self, event: Event):
        """
        ドラッグ終了

        Args:
            event (Event): イベント
        """
        pass

    def _on_click_left(self, event: Event):
        """
        マウスクリック（左ボタン）
        """
        pass

    def _on_click_right(self, event: Event):
        """
        マウスクリック（右ボタン）
        """
        self._master.delete_image(self)

    @property
    def original_image(self) -> Image.Image:
        """
        リサイズ前の画像を返す

        Returns:
            Image.Image: リサイズ前の画像
        """
        return self._original_image


class ThumbnailBar(ctk.CTkScrollableFrame):
    """
    画像（アイテム）サムネイルを横並びでリスト表示可能なウィジェット
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        thumbnail_height: int,
        on_change: Callable[[List[Image.Image]], None],
        **kwargs
    ):
        """
        コンストラクタ

        Args:
            master (CTkBaseClass): 親ウィジェット
            thumbnail_height (int): サムネイルの大きさ（縦方向）
            on_change (Callable): サムネイルに変化があった場合に呼び出されるハンドラ
        """
        super().__init__(master, orientation="horizontal", **kwargs)

        # 高さを調整
        self.configure(height=thumbnail_height + 2 * WIDGET_PADDING)

        # 内部状態
        self._thumbnail_height = thumbnail_height
        self._items: list[ctk.CTkFrame] = []
        self._on_change = on_change

        # 番兵アイテムを追加
        sentinel_item = SentinelItem(self, thumbnail_height)
        self._items.append(sentinel_item)
        sentinel_item.grid(row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING)

    def add_image(self, image: Image.Image):
        """
        画像（アイテム）を追加

        Args:
            image (Image): 追加したい PIL 画像
        """
        # アイテムを生成・GUI配置
        item = ThumbnailItem(self, image, self._thumbnail_height)
        item.grid(
            row=0, column=len(self._items) - 1, padx=WIDGET_PADDING, pady=WIDGET_PADDING
        )

        # アイテムリストに追加
        self._items.insert(-1, item)

        # 番兵をずらす
        self._items[-1].grid(column=len(self._items))

        # リスト変更をコールバックで通知
        self._on_change(self.original_frames)

    def delete_image(self, removal_item: ctk.CTkFrame):
        """
        画像（アイテム）を削除

        Args:
            item (ThumbnailItem): 削除対象アイテム
        """
        # 番兵アイテムは削除不可
        if isinstance(removal_item, SentinelItem):
            return

        # アイテムリストから除外
        removal_index = self._items.index(removal_item)
        self._items.pop(removal_index)

        # アイテムを CTk 上から削除
        removal_item.destroy()
        del removal_item

        # 削除したぶん GUI 上で詰める
        for idx, item in enumerate(self._items):
            if idx >= removal_index:
                item.grid_configure(column=idx)

        # リスト変更をコールバックで通知
        self._on_change(self.original_frames)

    def swap(self, idx_A: int, idx_B: int):
        """
        要素の順序を入れ替える

        Args:
            idx_A (int): 入れ替え対象インデックス(A)
            idx_B (int): 入れ替え対象インデックス(B)
        """
        # 番兵アイテムとの入れ替えは不可
        is_sentinel_A = isinstance(self._items[idx_A], SentinelItem)
        is_sentinel_B = isinstance(self._items[idx_B], SentinelItem)
        if is_sentinel_A or is_sentinel_B:
            return

        # リスト上の順序を入れ替え
        self._items[idx_A], self._items[idx_B] = (
            self._items[idx_B],
            self._items[idx_A],
        )

        # グリッド配置を修正
        self._items[idx_A].grid_configure(column=idx_A)
        self._items[idx_B].grid_configure(column=idx_B)

        # リスト変更をコールバックで通知
        self._on_change(self.original_frames)

    @property
    def original_frames(self) -> List[Image.Image]:
        """
        縮小前のフレーム（画像）を得る

        Returns:
            List[Image.Image]: 縮小前のフレーム
        """
        return [
            item.original_image
            for item in self._items
            if isinstance(item, ThumbnailItem)
        ]
