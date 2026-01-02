# std
import datetime
import io
import logging
from logging.handlers import TimedRotatingFileHandler
from time import perf_counter
from typing import Any, Callable, Literal, Self
import sys
import threading
import asyncio
import warnings
from pathlib import Path
import os
import traceback

# tk
import tkinter.messagebox
import customtkinter as ctk

# utils
from utils.constants import LOG_DIR_PATH


def _warnings_formatter(message, category, filename, lineno, line=None):
    """
    warnings モジュール用カスタムフォーマッタ
    vscode の Log モードに合わせたフォーマット
    そのうえで１行にまとめている
    """
    base = os.path.basename(filename)
    text = str(message).replace("\r", " ").replace("\n", " ").strip()
    return f"{base}:{lineno}: {category.__name__}: {text}"


def _get_actual_stream(
    stream: io.TextIOWrapper | None = None,
) -> io.TextIOWrapper | None:
    """
    書き込み可能な stream だけを非 None にするヘルパ
    """
    if getattr(stream, "write", None):
        return stream
    else:
        return None


class _LoggingTee(io.TextIOBase):
    """
    stdout, stderr に成り代わることで、書き込みを logging に流す用のクラス
    """

    def __init__(
        self,
        dest_logger: logging.Logger,
        log_level: int,
        mirror_stream: io.TextIOWrapper | None = None,
    ):
        """
        コンストラクタ
        """
        # 引数を保存
        self._dest_logger = dest_logger
        self._log_level = log_level
        self._buffer: str = ""
        self._mirror_stream = mirror_stream

    def writable(self) -> bool:
        """
        True なら書き込み可能
        """
        return True

    def write(self, s: Any) -> int:
        """
        書き込み
        """
        # 先にコンソールに流す
        if self._mirror_stream is not None:
            try:
                self._mirror_stream.write(s)
                self._mirror_stream.flush()
            except Exception:
                pass

        # 改行単位でロガーに流す
        self._buffer += s if isinstance(s, str) else str(s)
        while True:
            nl_idx = self._buffer.find("\n")
            if nl_idx < 0:
                break
            line = self._buffer[:nl_idx]
            self._buffer = self._buffer[nl_idx + 1 :]
            self._dest_logger.log(self._log_level, line)

        # 文字数を返す
        return len(s)

    def flush(self) -> None:
        """
        吐き出し
        バッファに溜まったままの文字列を出力する
        """
        # コンソール
        if self._mirror_stream is not None:
            try:
                self._mirror_stream.flush()
            except Exception:
                pass

        # ロガー
        if self._buffer:
            self._dest_logger.log(self._log_level, self._buffer)
            self._buffer = ""


def _uncaught_exception_hook(exc_type, exc, tb):
    """
    未補足例外カスタムフック関数
    メインスレッド用
    """
    write_log(
        "error", __name__, "Uncaught exception (by sys.excepthook)", exception=exc
    )


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
    write_log(
        "critical",
        __name__,
        f"Uncaught exception (by threading.excepthook, thread name={thread_name})",
        exception=exc_value,
    )


def _asyncio_exception_handler(loop, context):
    """
    未補足例外カスタムフック関数
    asyncio 用
    """
    msg = context.get("message", "Unhandled asyncio exception")
    exc = context.get("exception")
    write_log(
        "critical",
        __name__,
        f"Uncaught exception(by asyncio set_exception_handler, message={msg})",
        exception=exc,
    )


class TkInterExceptionHandler:

    def __init__(self, log_file_path: Path):
        """
        コンストラクタ
        """
        self._log_file_path = log_file_path

    def __call__(self, exc, val, tb):
        """
        未補足例外カスタムフック関数
        tkinter 用
        """
        write_log(
            "critical",
            str(__class__),
            "Uncaught exception (by CTk report_callback_exception)",
            exception=exc,
        )
        try:
            tkinter.messagebox.showerror(
                "エラー",
                f"何かが失敗したよ。開発者にログファイルを送ってね。\n{self._log_file_path}",
            )
        except Exception:
            pass


def setup_logging():
    """
    ログ周りのセットアップを行う
    エントリーポイントで真っ先に呼び出すこと
    すべてのメッセージ出力 logging に集約したうえで、コンソール・ファイルに tee する。
    """
    # 定数
    LOGGING_LEVEL = logging.INFO

    # ログディレクトリを生成
    LOG_DIR_PATH.mkdir(parents=True, exist_ok=True)

    # エイリアス
    root_logger = logging.getLogger()

    # warnings の設定
    logging.addLevelName(logging.WARNING, "WARN")
    logging.captureWarnings(True)
    warnings.formatwarning = _warnings_formatter

    # ルートロガーの設定を変更
    root_logger.setLevel(LOGGING_LEVEL)

    # フォーマットを生成
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d [%(levelname)-5s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ファイルハンドラーをログシステムに追加
    rotation_file_handler = TimedRotatingFileHandler(
        LOG_DIR_PATH / "latest.log",
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
        delay=False,
        utc=False,
        atTime=datetime.time(0, 0),
        errors=None,
    )
    rotation_file_handler.setFormatter(formatter)
    rotation_file_handler.setLevel(LOGGING_LEVEL)
    rotation_file_handler.namer = lambda name: name.replace("latest.log.", "") + ".log"
    root_logger.addHandler(rotation_file_handler)

    # 実際の stdout, stderr を解決
    actual_stdout = _get_actual_stream(sys.__stdout__)
    actual_stderr = _get_actual_stream(sys.__stderr__)

    # stdout, stderr を logging に流す
    sys.stdout = _LoggingTee(logging.getLogger("stdout"), logging.INFO, actual_stdout)
    sys.stderr = _LoggingTee(logging.getLogger("stderr"), logging.ERROR, actual_stderr)

    # logging をコンソールに流す
    if actual_stdout or actual_stderr:
        stream_handler = logging.StreamHandler(actual_stdout or actual_stderr)
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(LOGGING_LEVEL)
        stream_handler.addFilter(lambda record: record.name not in ("stdout", "stderr"))
        root_logger.addHandler(stream_handler)

    # 未補足例外のフックを設定
    sys.excepthook = _uncaught_exception_hook
    threading.excepthook = _thread_uncaught_exception_hook
    try:
        asyncio.get_event_loop().set_exception_handler(_asyncio_exception_handler)
    except Exception:
        pass

    # ロギング開始をログ
    write_log("info", __name__, f"Logging initialized. file={LOG_DIR_PATH}")

    # 正常終了
    return


def setup_logging_ctk(ctk_app: ctk.CTk):
    """
    ログ周りのセットアップを行う
    エントリーポイントで真っ先に呼び出すこと
    CTk 関係だけやる
    """
    ctk_app.report_callback_exception = TkInterExceptionHandler(LOG_DIR_PATH)


def traceback_str(exception: Exception) -> str:
    """
    excetpion からトレースバック文字列を生成する
    """
    return "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    )


LogLevel = Literal["info", "warning", "error", "critical"]


def write_log(
    level: LogLevel,
    category: str | None,
    message: str,
    *,
    exception: Exception | BaseException | None = None,
) -> None:
    """
    logging を使ってログを書き込む。
    """
    # 例外をメッセージに組み入れる
    if isinstance(exception, Exception):
        message += "\n" + traceback_str(exception)
    elif isinstance(exception, BaseException):
        message += "\n" + str(exception)

    # 複数行メッセージの場合、見やすいように整形
    # NOTE
    #   このログの２行目以降に空白４文字のインデントで表示する
    if "\n" in message:
        message = "\n" + "\n".join(" " * 4 + l for l in message.split("\n"))

    # ログレベルで呼び分け
    logger = logging.getLogger(category)
    if level == "info":
        logger.info(message)
    elif level == "warning":
        logger.warning(message)
    elif level == "error":
        logger.error(message)
    else:  # critical
        # NOTE 異常系で呼ばれる可能性があるので、例外は投げない
        logger.critical(level, message)


class PerfLogger:
    """
    with 区間の経過時間をダンプする用のロガー
    """

    def __init__(
        self, label: str, formatter: Callable[[float], str] = lambda x: f"{x:.2f} sec"
    ):
        self._label = label
        self._formatter = formatter
        self._start = None

    def __enter__(self) -> Self:
        """
        with 句開始
        """
        self._start = perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        with 句終了
        """
        if exc_type is None and self._start is not None:
            elapsed_str = self._formatter(perf_counter() - self._start)
            write_log("info", str(__class__), f"{self._label}: {elapsed_str}")
