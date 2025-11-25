# std
import warnings
from typing import Callable, Optional, Union, List, Literal
import logging

# PIL
from PIL.ImageTk import PhotoImage

# Tk/CTk
import customtkinter as ctk
from tkinter import Event
import tkinter.messagebox as mb

# utils
from utils.constants import DEFAULT_FONT_FAMILY, WIDGET_PADDING, APP_NAME_JP
from utils.std import traceback_str


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
        raise TypeError(f"Invalid type({type(content)})")


def show_notify_label(
    widget: ctk.CTkBaseClass,
    level: Literal["info", "warning", "error"],
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
    default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)

    # 通知色を解決
    match level.lower():
        case "info":
            fg_color = "#3a8d3f"
        case "warning":
            fg_color = "#F5A623"
        case "error":
            fg_color = "#D32F2F"
        case _:
            raise ValueError(f"Invalid level {level}")

    # 通知ラベルを生成
    # NOTE
    #   ラベルの四隅の外側はテーマ色でフィルされてしまうので、角丸のないラベルを使用する(corner_radius=0)。
    status_label = ctk.CTkLabel(
        widget,
        text=message,
        fg_color=fg_color,
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


def show_error_dialog(
    message: str, exception: Union[Exception, List[Exception], None] = None
):
    """
    エラーダイアログを表示する。
    デバッグ情報として e の説明文字列を添付する
    """
    # 例外文字列を生成
    if exception is None:
        tb_str = ""
    elif isinstance(exception, Exception):
        tb_str = traceback_str(exception)
    elif isinstance(exception, list):
        tb_str = ""
        for e in exception:
            if isinstance(e, Exception):
                tb_str += traceback_str(e)
            else:
                tb_str += str(e)
    else:
        tb_str = str(e)

    # エラーダイアログを表示
    mb.showerror(
        APP_NAME_JP,
        f"{message}\n{tb_str}",
    )
