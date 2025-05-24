from typing import Callable, List, Union, Iterable
import time
import sys
from math import sqrt

from PIL import Image, ImageTk

from tkinter import Event

import customtkinter as ctk

from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.pil import make_disabled_image, calc_ssim


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

        # 内部状態
        self._enabled = True
        self._last_swap_time = 0.0
        self._mlb_press_pos = (0, 0)

        # サムネイルサイズを解決
        thumbnail_width = int(pil_image.width * thumbnail_height / pil_image.height)
        thumbnail_size = (thumbnail_width, thumbnail_height)

        # サムネイル画像（有効時）を生成
        pil_enable_image = pil_image.copy()
        pil_enable_image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
        self._tk_enable_image = ctk.CTkImage(
            light_image=pil_enable_image,
            dark_image=pil_enable_image,
            size=(thumbnail_width, thumbnail_height),
        )

        # サムネイル画像（無効時）を生成
        pil_disable_image = make_disabled_image(pil_image)
        pil_disable_image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
        self._tk_disable_image = ctk.CTkImage(
            light_image=pil_disable_image,
            dark_image=pil_disable_image,
            size=(thumbnail_width, thumbnail_height),
        )

        # ドラッグをハンドルするためのボタン
        self._button = ctk.CTkButton(
            self,
            image=self._tk_enable_image,
            text="",
            width=thumbnail_width,
            height=thumbnail_height,
            fg_color="transparent",
            hover=False,
        )
        self._button.pack()

        # マウスイベント
        # NOTE
        #   並び替え・有効無効切り替え・削除
        self._button.bind("<ButtonPress-1>", self._begin_drag)
        self._button.bind("<B1-Motion>", self._on_drag)
        self._button.bind("<ButtonRelease-1>", self._end_drag)
        self._button.bind("<Button-3>", self._on_click_right)

    def _begin_drag(self, event: Event):
        """
        ドラッグ開始

        Args:
            event (Event): イベント
        """
        self._mlb_press_pos = (event.x_root, event.y_root)

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
        # ドラッグ挙動の場合は何もしない
        mlb_current_pos = (event.x_root, event.y_root)
        diff = max(
            [abs(v1 - v2) for v1, v2 in zip(self._mlb_press_pos, mlb_current_pos)]
        )
        torelance = min(self._button.winfo_width(), self._button.winfo_height()) / 2
        if diff < torelance:
            self.set_enable(not self._enabled)

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

    def set_enable(self, state: bool, does_notify: bool = True):
        """
        このアイテムの有効・無効を切り替える

        Args:
            state (bool): True なら有効
            does_notify (bool): True なら親ウィジェットに変更を通知する
        """
        # 状態に変更が無い場合は何もしない
        if state == self._enabled:
            return

        # 状態を変更して画像を差し替え
        self._enabled = state
        if self._enabled:
            self._button.configure(image=self._tk_enable_image)
        else:
            self._button.configure(image=self._tk_disable_image)

        # 親ウィジェットに通知
        if does_notify:
            self._master._on_change()

    @property
    def enabled(self) -> bool:
        """
        このアイテムが有効であるかどうか

        Returns:
            bool: 有効なら True
        """
        return self._enabled


class ThumbnailBar(ctk.CTkScrollableFrame):
    """
    画像（アイテム）サムネイルを横並びでリスト表示可能なウィジェット
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        thumbnail_height: int,
        on_change: Callable[[], None],
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
        self._parent_on_change = on_change

        # 番兵アイテムを追加
        sentinel_item = SentinelItem(self, thumbnail_height)
        self._items.append(sentinel_item)
        sentinel_item.grid(row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING)

        # マウスホイール横スクロール設定
        self._parent_canvas.bind("<Enter>", self._mouse_enter)
        self._parent_canvas.bind("<Leave>", self._mouse_leave)

    def _on_change(self):
        """
        サムネリストに変更が合った時に呼び出されるハンドラ
        """
        # 親ウィジェットに通知
        self._parent_on_change()

    def add_image(self, images: Iterable[Image.Image]):
        """
        画像（アイテム）を追加

        Args:
            image (Image): 追加したい PIL 画像
        """
        # 順番に追加
        for image in images:
            # アイテムを生成・GUI配置
            item = ThumbnailItem(self, image, self._thumbnail_height)
            item.grid(
                row=0,
                column=len(self._items) - 1,
                padx=WIDGET_PADDING,
                pady=WIDGET_PADDING,
            )

            # アイテムリストに追加
            self._items.insert(-1, item)

            # 番兵をずらす
            self._items[-1].grid(column=len(self._items))

        # リスト変更をコールバックで通知
        self._on_change()

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
        self._on_change()

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
        self._on_change()

    def clear_images(self):
        """
        保持している全ての画像を削除
        """
        # 新しい画像リストを構築＆サムネを解体
        new_items = []
        for item in self._items:
            if isinstance(item, SentinelItem):
                new_items.append(item)
            elif isinstance(item, ThumbnailItem):
                item.destroy()
            else:
                raise TypeError()

        # 画像リストを更新
        self._items = new_items

        # リスト変更をコールバックで通知
        self._on_change()

    def clear_disable_images(self):
        """
        無効化されている画像を削除
        """
        # 新しい画像リストを構築＆サムネを解体
        new_items = []
        for item in self._items:
            if isinstance(item, SentinelItem):
                new_items.append(item)
            elif isinstance(item, ThumbnailItem):
                if item.enabled:
                    new_items.append(item)
                else:
                    item.destroy()
            else:
                raise TypeError()

        # 画像リストを更新
        self._items = new_items

        # リスト変更をコールバックで通知
        self._on_change()

    def disable_dupe_images(self, threshold: float):
        """
        重複する画像を無効化する
        時間方向に１つ前のフレームとの類似度が threshold を超える画像が無効化される。
        別の言い方をすれば N 枚連続する類似フレームの 1 枚目だけが残るということ。

        Args:
            threshold (float):
                類似判定しきい値
                値域は [0.0, 1.0]
        """
        # 一旦、全てのフレームを有効化
        for item in self._items:
            if isinstance(item, ThumbnailItem):
                item.set_enable(True, False)

        # 全フレームに対して個別に呼び出し
        for idx_B in range(1, len(self._items)):
            # 前方に向かって有効フレームを探索
            idx_A = idx_B - 1
            while idx_A > 0:
                item_A = self._items[idx_A]
                if isinstance(item_A, ThumbnailItem):
                    if item_A.enabled:
                        break
                idx_A -= 1

            # 前フレーム
            item_A = self._items[idx_A]
            if isinstance(item_A, ThumbnailItem):
                image_A = item_A.original_image
            else:
                continue

            # 次フレーム
            item_B = self._items[idx_B]
            if isinstance(item_B, ThumbnailItem):
                image_B = item_B.original_image
            else:
                continue

            # 類似度を元に有効・無効を設定
            similarity = calc_ssim(image_A, image_B)
            item_B.set_enable(similarity < threshold, False)

        # 変更を通知
        self._on_change()

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
            if isinstance(item, ThumbnailItem) and item.enabled
        ]

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
