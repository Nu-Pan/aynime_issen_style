# std
import sys
import threading
from inspect import cleandoc

# Tk/CTk
import customtkinter as ctk
import tkinter.messagebox as mb

# utils
from utils.windows import SystemWideMutex
from utils.constants import APP_NAME_EN, APP_NAME_JP
from utils.ctk import show_error_dialog
from utils.ais_logging import setup_logging, setup_logging_ctk, write_log
from utils.version_constants import COMMIT_HASH, BUILD_DATE
from utils.video_encoder import ensure_ffmpeg, ensure_gifsicle
from utils.user_properties import USER_PROPERTIES

# gui
from gui.aynime_issen_style_app import AynimeIssenStyleApp
from gui.splash_app import SplashWindow
from gui.model.contents_cache import standardize_nime_raw_dile
from gui.frames.status_frame import StatusFrame, LicenseFrame, SOFTWARE_LICENSE_ENTRIES


def _startup_job():
    """
    アプリ起動前に実行される処理
    """
    # nime, raw を整理
    standardize_nime_raw_dile()
    # 外部ツールをインストール
    ensure_ffmpeg()
    ensure_gifsicle()


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

    # 外部ツール使用の通知を出す
    if USER_PROPERTIES.get("show_web_tool_notice", True):
        web_tools_str = ", ".join(
            [k for k in SOFTWARE_LICENSE_ENTRIES if k != APP_NAME_JP]
        )
        # fmt: off
        mb.showinfo(
            APP_NAME_JP,
            cleandoc(f"""
            {APP_NAME_JP} は {web_tools_str} をダウンロードして使用します。
            詳細は「{StatusFrame.UI_TAB_NAME} > {LicenseFrame.UI_TAB_NAME}」を参照。
            """)
        )
        # fmt: on
        USER_PROPERTIES.set("show_web_tool_notice", False)

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
        USER_PROPERTIES.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
