# std
from datetime import datetime
import io
import logging
from logging.handlers import TimedRotatingFileHandler
from typing import Any, List
import sys
import threading
import asyncio

# tk
import tkinter.messagebox
import customtkinter as ctk

# utils
from utils.constants import LOG_DIR_PATH


class _LoggingRedirector(io.TextIOBase):
    """
    stdout, stderr に成り代わることで、書き込みを logging に流す用のクラス
    """

    def __init__(self, dest_logger: logging.Logger, log_level: int):
        """
        コンストラクタ
        """
        self._dest_logger = dest_logger
        self._log_level = log_level
        self._buf: str = ""

    def writable(self) -> bool:
        """
        True なら書き込み可能
        """
        return True

    def write(self, s: Any) -> int:
        """
        書き込み
        """
        # 引数をバッファに追加
        self._buf += s if isinstance(s, str) else str(s)

        # 改行単位でロガーに流す
        while True:
            nl_idx = self._buf.find("\n")
            if nl_idx < 0:
                break
            line = self._buf[:nl_idx]
            self._buf = self._buf[nl_idx + 1 :]
            self._dest_logger.log(self._log_level, line)

        # 文字数を返す
        return len(s)

    def flush(self) -> None:
        """
        吐き出し
        バッファに溜まったままの文字列を出力する
        """
        if self._buf:
            self._dest_logger.log(self._log_level, self._buf)
            self._buf = ""


def _uncaught_exception_hook(exc_type, exc, tb):
    """
    未補足例外カスタムフック関数
    メインスレッド用
    """
    logging.critical("Uncaught exception", exc_info=(exc_type, exc, tb))


def _thread_uncaught_exception_hook(args: threading.ExceptHookArgs):
    """
    未補足例外カスタムフック関数
    threading 用
    """
    # 例外発生スレッド名を正規化
    if args.thread is None:
        thread_name = "None"
    else:
        thread_name = args.thread.name

    args.exc_type

    # 例外オブジェクトを正規化
    if args.exc_value is None:
        exc_value = Exception("None")
    else:
        exc_value = args.exc_value

    # critical でログに流す
    logging.critical(
        "Uncaught thread exception (name=%s)",
        thread_name,
        exc_info=(args.exc_type, exc_value, args.exc_traceback),
    )


def _asyncio_exception_handler(loop, context):
    """
    未補足例外カスタムフック関数
    asyncio 用
    """
    msg = context.get("message", "Unhandled asyncio exception")
    exc = context.get("exception")
    logging.error("asyncio: %s", msg, exc_info=exc)


def _tkinter_exception_handler(exc, val, tb):
    """
    未補足例外カスタムフック関数
    tkinter 用
    """
    logging.getLogger("tk").error("Tk callback exception", exc_info=(exc, val, tb))
    try:
        tkinter.messagebox.showerror("エラー", "予期せぬエラーが発生しました。")
    except Exception:
        pass


def setup_logging(ctk_app: ctk.CTk):
    """
    ログ周りのセットアップを行う
    エントリーポイントで真っ先に呼び出すこと
    すべてのメッセージ出力 logging に集約したうえで、コンソール・ファイルに tee する。
    """
    # 定数
    LOGGING_LEVEL = logging.DEBUG

    # エイリアス
    root_logger = logging.getLogger()

    # 警告をキャプチャ対象に含める
    logging.captureWarnings(True)

    # ログレベルを設定
    root_logger.setLevel(LOGGING_LEVEL)

    # ログファイルパス
    log_file_stem = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = LOG_DIR_PATH / f"{log_file_stem}.log"

    # ログディレクトリを生成
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

    # フォーマットを生成
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ファイルハンドラーをログシステムに追加
    rotation_file_handler = TimedRotatingFileHandler(
        log_file_path,
        when="midnight",
        interval=1,
        backupCount=5,
        encoding="utf-8",
        delay=True,
    )
    rotation_file_handler.setFormatter(formatter)
    rotation_file_handler.setLevel(LOGGING_LEVEL)
    root_logger.addHandler(rotation_file_handler)

    # stdout, stderr を logging に流す
    sys.stdout = _LoggingRedirector(logging.getLogger("stdout"), logging.INFO)
    sys.stderr = _LoggingRedirector(logging.getLogger("stderr"), logging.ERROR)

    # 未補足例外のフックを設定
    sys.excepthook = _uncaught_exception_hook
    threading.excepthook = _thread_uncaught_exception_hook
    try:
        asyncio.get_event_loop().set_exception_handler(_asyncio_exception_handler)
    except Exception:
        pass
    ctk_app.report_callback_exception = _tkinter_exception_handler

    # ロギング開始をログ
    logging.getLogger(__name__).info("Logging initialized. file=%s", log_file_path)

    # 正常終了
    return
