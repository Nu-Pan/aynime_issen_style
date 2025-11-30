# std
from typing import Callable, Any
import threading
import queue
import warnings
from inspect import cleandoc
from pathlib import Path
import struct
import re

# TK/CTk
import customtkinter as ctk

# win32
import ctypes
from ctypes import wintypes
import win32con, win32gui, win32api, win32event, winerror, win32clipboard


def file_to_clipboard(file_path: Path) -> None:
    """
    file_path の指すファイルをクリップボードに乗せて、
    エクスプローラー上でペースト可能な状態にする。

    Args:
        file_path (Path): クリップボードに乗せたいファイルのパス

    Raises:
        FileNotFoundError: file_path が存在しない場合
    """
    # ファイルの存在をチェック
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))

    # データを組み立てる
    # NOTE
    #   DROPFILES ヘッダ (sizeof=20, wide char)
    #   パス列 (UTF-16LE, ダブル終端)
    dropfiles = struct.pack("IiiII", 20, 0, 0, 0, 1)
    files = (str(file_path) + "\0\0").encode("utf-16le")
    data = dropfiles + files

    # クリップボードを開いて CF_HDROP をセット
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_HDROP, data)
    finally:
        win32clipboard.CloseClipboard()


def register_global_hotkey_handler(
    ctk_kind: ctk.CTk | ctk.CTkBaseClass, handler: Callable[[Any], None], *args
) -> None:
    """
    グローバルホットキー `Ctrl+Alt+P` をトリガーに handler が呼ばれるように設定する。

    ctk ウィジェットのハンドラを呼び出すことを念頭に置いている。

    グローバルホットキーの監視及び handler の呼び出しは別スレッドから行われるが、
    ctk_kinnd.after 経由でディスパッチされるため、同期関係は問題ない。

    Args:
        ctk_kind (Union[ctk.CTk, ctk.CTkBaseClass]): 親 CTk ウィジェット
        handler (Callable[[Any], None]): ホットキーハンドラー
    """
    # 定数
    MOD = win32con.MOD_CONTROL | win32con.MOD_ALT
    VK_P = ord("P")  # 必ず大文字
    HOTKEY_ID = 1

    # グローバルホットキー押下イベント通知キュー
    # NOTE
    #   ctk の機能を win32 スレッドから呼び出すとクラッシュする（ctk はマルチスレッド非対応）
    #   そのため、このキューを介してメインスレッドへホットキー押下を通知する。
    ghk_event_queue = queue.SimpleQueue()

    # win32 から呼び出されるプロシジャー
    def window_procedure(hWnd, msg, wParam, lParam):
        if msg == win32con.WM_HOTKEY and wParam == HOTKEY_ID:
            ghk_event_queue.put(None)
        return win32gui.DefWindowProc(hWnd, msg, wParam, lParam)

    # メッセージウィンドウを作成
    wc = win32gui.WNDCLASS()
    wc.hInstance = win32api.GetModuleHandle(None)  # type: ignore
    wc.lpszClassName = "AynimeIssenStyleHotKeyMessageOnlyWindow"  # type: ignore
    wc.lpfnWndProc = window_procedure  # type: ignore
    class_atom = win32gui.RegisterClass(wc)
    msg_hwnd = win32gui.CreateWindowEx(
        0, class_atom, None, 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None  # type: ignore
    )

    # ホットキーを登録
    win32gui.RegisterHotKey(msg_hwnd, HOTKEY_ID, MOD, VK_P)

    # 保留メッセージのポンプ処理をデーモンスレッドで実行
    threading.Thread(target=win32gui.PumpWaitingMessages, daemon=True).start()

    # グローバルホットキーイベントポーリング関数
    def poll_ghk_event():
        if not ghk_event_queue.empty():
            ghk_event_queue.get()
            try:
                handler(*args)
            except Exception as e:
                warn_text = f"""
                Unexpected exception raised in poll_ghk_event.
                Swallowing this and continue.
                Exception detail:
                {args}
                """
                warnings.warn(cleandoc(warn_text))
        ctk_kind.after(10, poll_ghk_event)

    # ポーリング処理をキック
    ctk_kind.after(0, poll_ghk_event)


class SystemWideMutex:
    """
    システムワイドのミューテックスを表すクラス
    """

    def __init__(self, name: str):
        """
        コンストラクタ

        Args:
            name (str): ミューテックス名
        """
        self._handle = win32event.CreateMutex(None, False, "Global\\" + name)  # type: ignore
        self._last_error = win32api.GetLastError()

    @property
    def already_exists(self) -> bool:
        """
        すでに同名のミューテックスが存在しているか調べる

        Returns:
            bool: すでに同名のミューテックスが存在しているなら True
        """
        return self._last_error == winerror.ERROR_ALREADY_EXISTS


def is_cloaked(hwnd: int) -> bool:
    """
    hwnd が指すウィンドウがクローク状態なら True を返す
    """
    DWMWA_CLOAKED = 14
    cloaked = wintypes.DWORD()
    res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
    )
    return res == 0 and cloaked.value != 0


def sanitize_text(text: str) -> str:
    """
    text を「無毒化」する
    無毒化されたテキストは、ファイル名に含めることができる。
    """
    # Windows パス的な禁止文字を削除
    text = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "　", text)

    # 見た目空白な文字を ASCII 半角スペースに統一
    # NOTE
    #   NBSP, 全角, 2000-系, 202F, 205F, 1680
    text = re.sub(r"[\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]", " ", text)

    # ゼロ幅系を削除
    # NOTE
    #   ZWSP/ZWNJ/ZWJ/WORD JOINER/BOM
    #   歴史的に空白扱いの MVS
    text = re.sub(r"[\u200B-\u200D\u2060\uFEFF\u180E]", "", text)

    # ソフトハイフンを削除
    # NOTE
    #   通常は印字されず「改行位置の候補」だけを意味する。
    #   可視の意図はないので 削除。
    text = re.sub(r"\u00AD", "", text)

    # 区切り文字を ASCII のハイフンで統一
    # NOTE
    #   \u2013 = en dash
    #   \u2014 = em dash
    #   \u2015 = horizontal bar
    #   \u007C = vertical bar (ASCII |)
    #   \uFF5C = fullwidth vertical bar
    #   \u2011 = non-breaking hyphen
    text = re.sub(r"[\u2013\u2014\u2015\u007C\uFF5C\u2011]", "-", text)

    # アンダースコア --> 半角空白
    text = text.replace("_", " ")

    # ２つ以上連続する空白を 1 文字に短縮
    text = re.sub(r" {2,}", " ", text)

    # 前後の空白系文字を削除
    text = text.strip().rstrip()

    # 正常終了
    return text
