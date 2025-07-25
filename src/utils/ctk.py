# std
import warnings
from typing import Callable, Optional, Union

# PIL
from PIL.ImageTk import PhotoImage

# Tk/CTk
import customtkinter as ctk
from tkinter import Event

# local
from utils.constants import DEFAULT_FONT_NAME, WIDGET_PADDING


def silent_configure(widget: ctk.CTkBaseClass, **kwargs):
    """
    widget に対して configure を呼び出して **kwargs を渡す。
    ただし configure 内で発生した警告は抑制される。
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        widget.configure(**kwargs)


def configure_presence(widget: ctk.CTkBaseClass, content: Union[PhotoImage, str]):
    """
    widget に対して configure を呼び出して content を設定する。
    ただし configure 内で発生した警告は抑制される。
    """
    if isinstance(content, PhotoImage):
        silent_configure(widget, image=content, text="")
    elif isinstance(content, str):
        silent_configure(widget, image="", text=content)
    else:
        raise TypeError()


def show_notify(
    widget: ctk.CTkBaseClass,
    message: str,
    duration_ms: int = 2000,
    on_click_handler: Optional[Callable[[Event], None]] = None,
) -> None:
    """
    通知ラベルを表示する
    duration_ms の間、message が表示される。

    Args:
        widget (CTkBaseClass): 表示対象ウィジェット
        message (str): メッセージ文字列
        duration_ms (int, optional): 表示時間（ミリ秒）. Defaults to 2000.
    """
    # フォントを生成

    default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

    # 通知ラベルを生成
    # NOTE
    #   ラベルの四隅の外側はテーマ色でフィルされてしまうので、角丸のないラベルを使用する(corner_radius=0)。
    status_label = ctk.CTkLabel(
        widget,
        text=message,
        fg_color="#3a8d3f",
        text_color="white",
        corner_radius=0,
        font=default_font,
    )
    status_label.place(relx=0.5, rely=0.5, anchor="center")
    status_label.configure(padx=WIDGET_PADDING, pady=WIDGET_PADDING)
    if on_click_handler is not None:
        status_label.bind("<Button-1>", on_click_handler)

    # 通知ラベルは一定時間後に自動破棄
    widget.after(duration_ms, status_label.destroy)
