# std
from typing import Callable
import time

# ctk
import customtkinter as ctk

# utils
from utils.constants import DEFAULT_FONT_FAMILY, WIDGET_MIN_WIDTH, WIDGET_MIN_HEIGHT


class AISEntry(ctk.CTkEntry):
    """
    使いやすくした CTkEntry
    """

    def __init__(self, master, **kwargs):
        """
        コンストラクタ
        """
        # 基底コンストラクタ
        super().__init__(
            master, width=WIDGET_MIN_WIDTH, height=WIDGET_MIN_HEIGHT, **kwargs
        )

        # フォントを設定
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)
        self.configure(font=default_font)

        # ハンドラリスト
        self._handlers: list[Callable[[str], None]] = []

        # Entry の内容変更監視
        self._polled_value = ""
        self._next_notify_time = None
        self.after(100, self._poll_edit)

    @property
    def text(self) -> str:
        """
        テキストを取得
        """
        return self.get()

    def register_handler(self, handler: Callable[[str], None]):
        """
        テキストに変更があった際に呼び出されるハンドラを登録
        """
        self._handlers.append(handler)

    def _poll_edit(self) -> None:
        """
        テキスト変更ポーリング関数
        変更が発生した後少ししてからモデルに反映する
        """
        # 変更内容に変更があった場合は、モデル適用時刻を更新
        if self.text != self._polled_value:
            self._polled_value = self.text
            self._next_notify_time = time.time() + 0.5

        # 予定時刻を過ぎたら通知
        if self._next_notify_time is not None and time.time() > self._next_notify_time:
            self._next_notify_time = None
            for handler in self._handlers:
                handler(self.text)

        # 次のポーリング
        self.after(100, self._poll_edit)
