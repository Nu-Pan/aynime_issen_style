# std
import sys
import threading

# Tk/CTk
import customtkinter as ctk

# utils
from utils.windows import SystemWideMutex
from utils.constants import APP_NAME_EN
from utils.ctk import show_error_dialog
from utils.ais_logging import setup_logging, setup_logging_ctk, write_log
from utils.version_constants import COMMIT_HASH, BUILD_DATE

# gui
from gui.aynime_issen_style_app import AynimeIssenStyleApp
from gui.splash_app import SplashWindow
from gui.model.contents_cache import standardize_nime_raw_dile


def _startup_job():
    """
    アプリ起動前に実行される処理
    """
    # nime, raw を整理
    standardize_nime_raw_dile()


def main():
    """
    メイン関数
    """
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

    # ロギング挙動を設定
    setup_logging()

    # バージョン情報をログにダンプ
    write_log("info", f"COMMIT_HASH = {COMMIT_HASH}")
    write_log("info", f"BUILD_DATE = {BUILD_DATE}")

    # 本体の CTk アプリを生成
    ais_app = AynimeIssenStyleApp()
    setup_logging_ctk(ais_app)
    ais_app.withdraw()

    # バックグラウンドジョブ実行とスプラッシュ表示
    startup_thread = threading.Thread(
        target=_startup_job, name="_startup_job", daemon=True
    )
    startup_thread.start()
    _splash = SplashWindow(ais_app, lambda: not startup_thread.is_alive())

    # CTk アプリの mainloop を開始
    try:
        ais_app.mainloop()
    finally:
        ais_app.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
