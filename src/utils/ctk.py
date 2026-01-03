# std
import warnings
from typing import Callable, Literal

# PIL
from PIL.ImageTk import PhotoImage

# Tk/CTk
import customtkinter as ctk
from tkinter import Event
import tkinter.messagebox as mb

# utils
from utils.constants import DEFAULT_FONT_FAMILY, APP_NAME_JP
from utils.ais_logging import LogLevel, write_log


def silent_configure(widget: ctk.CTkBaseClass, **kwargs):
    """
    widget に対して configure を呼び出して **kwargs を渡す。
    ただし configure 内で発生した警告は抑制される。
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        widget.configure(**kwargs)


def configure_presence(widget: ctk.CTkBaseClass, content: PhotoImage | str):
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
    level: LogLevel,
    message: str,
    *,
    exception: Exception | None = None,
    duration_ms: int = 2000,
    on_click_handler: Callable[[Event], None] | None = None,
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

    # ラベル表示用文字列を生成
    if exception is None:
        label_str = message
    else:
        label_str = f"{message}\nwhat: {exception}"

    # 通知ラベルを生成
    # NOTE
    #   ラベルの四隅の外側はテーマ色でフィルされてしまうので、角丸のないラベルを使用する(corner_radius=0)。
    #   ユーザー向け通知
    status_label = ctk.CTkLabel(
        widget,
        text=label_str,
        fg_color=fg_color,
        text_color="white",
        corner_radius=0,
        font=default_font,
    )
    status_label.place(relx=0.5, rely=0.5, anchor="center")
    if on_click_handler is not None:
        status_label.bind("<Button-1>", on_click_handler)

    # ログにも流す
    write_log(level, message, exception=exception, num_frame_skip=1)

    # 通知ラベルは一定時間後に自動破棄
    widget.after(duration_ms, status_label.destroy)


def show_error_dialog(message: str, exception: Exception | None = None):
    """
    エラーダイアログを表示する。
    デバッグ情報として e の説明文字列を添付する
    """
    # ダイアログ表示用文字列を生成
    if exception is None:
        dialog_str = message
    else:
        dialog_str = f"{message}\nwhat: {exception}"

    # エラーダイアログを表示
    mb.showerror(APP_NAME_JP, dialog_str)

    # ロガーにも流す
    write_log("error", message, exception=exception, num_frame_skip=1)


def place_window_to_display_center(
    window: ctk.CTk | ctk.CTkToplevel, window_width: int, window_height: int
):
    """
    window をディスプレイの中央に配置する
    """
    window.update_idletasks()
    window_scale = window._get_window_scaling()
    raw_screen_width = round(window.winfo_screenwidth() * window_scale)
    raw_screen_height = round(window.winfo_screenheight() * window_scale)
    raw_window_width = round(window_width * window_scale)
    raw_window_height = round(window_height * window_scale)
    splash_window_x = (raw_screen_width - raw_window_width) // 2
    splash_window_y = (raw_screen_height - raw_window_height) // 2
    window.geometry(
        f"{window_width}x{window_height}+{splash_window_x}+{splash_window_y}"
    )
