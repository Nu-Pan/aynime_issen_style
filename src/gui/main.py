# std
import sys

# Tk/CTk
import customtkinter as ctk
import tkinter.messagebox as mb

# utils
from utils.pyinstaller import is_frozen
from utils.std import redirect_to_file
from utils.windows import SystemWideMutex
from utils.constants import APP_NAME_EN, APP_NAME_JP

# local
from gui.aynime_issen_style_app import AynimeIssenStyleApp

if __name__ == "__main__":
    # ログファイルリダイレクト設定
    if is_frozen():
        redirect_to_file()

    # カラーテーマを設定
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    # 二重起動は禁止
    # NOTE
    #   ここで止めないとホットキー登録でコケて、ユーザーにとって理解しにくいエラーが出る
    system_wide_mutex = SystemWideMutex(APP_NAME_EN)
    if system_wide_mutex.already_exists:
        mb.showerror(APP_NAME_JP, "アプリはすでに起動しています")
        sys.exit(-1)

    # CTk アプリを生成・開始
    app = AynimeIssenStyleApp()
    app.mainloop()

    # 正常終了
    sys.exit(0)
