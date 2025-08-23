# std
import sys

# Tk/CTk
import customtkinter as ctk

# utils
from utils.windows import SystemWideMutex
from utils.constants import APP_NAME_EN
from utils.ctk import show_error_dialog
from utils.logging import setup_logging

# local
from gui.aynime_issen_style_app import AynimeIssenStyleApp

if __name__ == "__main__":
    # カラーテーマを設定
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    # 二重起動は禁止
    # NOTE
    #   ここで止めないとホットキー登録でコケて、ユーザーにとって理解しにくいエラーが出る
    system_wide_mutex = SystemWideMutex(APP_NAME_EN)
    if system_wide_mutex.already_exists:
        show_error_dialog("アプリはすでに起動しています")
        sys.exit(-1)

    # CTk アプリを生成
    app = AynimeIssenStyleApp()

    # ロギング挙動を設定
    setup_logging(app)

    # メインループ
    app.mainloop()

    # 正常終了
    sys.exit(0)
