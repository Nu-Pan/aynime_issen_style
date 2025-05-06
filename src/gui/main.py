import customtkinter as ctk

from aynime_issen_style_app import AynimeIssenStyleApp
from utils.pyinstaller import is_frozen
from utils.std import redirect_to_file
import logging

if __name__ == "__main__":
    # ログファイルリダイレクト設定
    if is_frozen():
        redirect_to_file()

    # カラーテーマを設定
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    # CTk アプリを生成・開始
    app = AynimeIssenStyleApp()
    app.mainloop()
