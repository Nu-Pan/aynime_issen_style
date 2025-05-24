# std
import warnings

# Tk/CTk
import customtkinter as ctk


def silent_configure(widget: ctk.CTkBaseClass, **kwargs):
    """
    widget に対して configure を呼び出して **kwargs を渡す。
    ただし configure 内で発生した警告は抑制される。
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        widget.configure(**kwargs)
