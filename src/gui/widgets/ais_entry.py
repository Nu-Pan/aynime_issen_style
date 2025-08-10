# std
from typing import Callable, List

# ctk
import customtkinter as ctk
import tkinter as tk

# utils
from utils.constants import DEFAULT_FONT_FAMILY


class AISEntry(ctk.CTkEntry):
    """
    使いやすくした CTkEntry
    """

    def __init__(self, master, **kwargs):
        """
        コンストラクタ
        """
        # 変数
        self._var = tk.StringVar()
        self._var.set("")

        # 基底コンストラクタ
        super().__init__(master, textvariable=self._var, **kwargs)

        # フォントを設定
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)
        self.configure(font=default_font)

        # ハンドラリスト
        self._handlers: List[Callable[[str], None]] = []

        # StringVar に対する write 監視
        self._var.trace_add("write", self._trace_write)

    def set_text(self, text: str) -> None:
        """
        テキストを変更
        """
        self._var.set(text)

    @property
    def text(self) -> str:
        """
        テキストを取得
        """
        return self._var.get()

    def register_handler(self, handler: Callable[[str], None]):
        """
        テキストに変更があった際に呼び出されるハンドラを登録
        """
        self._handlers.append(handler)

    def _trace_write(self, *_):
        """
        テキストに変更があったときに呼び出されるハンドラ
        """
        for handler in self._handlers:
            handler(self.text)
