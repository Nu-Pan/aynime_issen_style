# std
import sys
import logging

# Tk/CTk
import customtkinter as ctk

# utils
from utils.windows import SystemWideMutex
from utils.constants import APP_NAME_EN
from utils.ctk import show_error_dialog
from utils.logging import setup_logging
from utils.version_constants import COMMIT_HASH, BUILD_DATE

# gui
from gui.aynime_issen_style_app import AynimeIssenStyleApp
from gui.model.contents_cache import standardize_nime_raw_dile

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

    # 不要な RAW ファイルを削除
    standardize_nime_raw_dile()

    # CTk アプリを生成
    app = AynimeIssenStyleApp()

    # ロギング挙動を設定
    setup_logging(app)

    # バージョン情報をログにダンプ
    logging.info(f"COMMIT_HASH = {COMMIT_HASH}")
    logging.info(f"BUILD_DATE = {BUILD_DATE}")

    # メインループ
    app.mainloop()

    # 正常終了
    sys.exit(0)
