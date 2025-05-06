from dataclasses import dataclass
from typing import Generator, Union, Callable, Any
import re
import threading
import queue
import warnings
from inspect import cleandoc
from pathlib import Path
import subprocess

import customtkinter as ctk

import win32con, win32gui, win32api
import dxcam_cpp as dxcam


@dataclass
class DXGIOutputInfo:
    """
    DXGI のアウトプット（モニター）情報を保持するクラス
    """

    adapter_index: int
    output_index: int
    width: int
    height: int
    primary: bool

    def __str__(self) -> str:
        """
        DXGI アウトプットの情報を文字列として返す

        Returns:
            str: DXGI アウトプットの情報の文字列
        """
        # 必ず表示するベース部分
        sub_strs = [
            f"GPU{self.adapter_index}",
            f"Monitor{self.output_index}",
            f"{self.width}x{self.height}",
        ]

        # プライマリモニターの場合
        if self.primary:
            sub_strs += ["Primary"]

        # 正常終了
        return " ".join(sub_strs)


def enumerate_dxgi_outputs() -> Generator[DXGIOutputInfo, None, None]:
    """
    DXGI のアウトプット（モニター）情報を列挙する

    Raises:
        RuntimeError: 何らかの問題が発生した場合

    Yields:
        Generator[DXGIOutputInfo, None, None]: モニター情報のジェネレータ
            有効なモニターの情報を順番に返す
    """

    """
    :return: DXGI アウトプットの情報のリスト
    """
    # DXGI のアウトプット情報を取得
    for output_str in dxcam.output_info().splitlines():
        # GPU 番号をパース
        m = re.search(r"Device\[(\d)+\]", output_str)
        if m is None:
            raise RuntimeError("Failed to parse DXGI output info(Device).")
        else:
            adapter_index = int(m.group(1))

        # モニター番号をパース
        m = re.search(r"Output\[(\d)+\]", output_str)
        if m is None:
            raise RuntimeError("Failed to parse DXGI output info(Output).")
        else:
            output_index = int(m.group(1))

        # 解像度をパース
        m = re.search(r"Res:\((\d+), (\d+)\)", output_str)
        if m is None:
            raise RuntimeError("Failed to parse DXGI output info(Res).")
        else:
            width = int(m.group(1))
            height = int(m.group(2))

        # プライマリモニターかどうかをパース
        m = re.search(r"Primary:(\w+)", output_str)
        if m is None:
            raise RuntimeError("Failed to parse DXGI output info(Primary).")
        else:
            if m.group(1) == "True":
                primary = True
            elif m.group(1) == "False":
                primary = False
            else:
                raise RuntimeError("Failed to parse DXGI output info(Primary).")

        # 構造体に固めて返す
        yield DXGIOutputInfo(
            adapter_index=adapter_index,
            output_index=output_index,
            width=width,
            height=height,
            primary=primary,
        )


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

    # pwershell でやる
    subprocess.run(
        [
            "powershell",
            "-NoLogo",
            "-NoProfile",
            "Set-Clipboard",
            "-LiteralPath",
            str(file_path),
        ],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def register_global_hotkey_handler(
    ctk_kind: Union[ctk.CTk, ctk.CTkBaseClass], handler: Callable[[Any], None], *args
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
    wc.hInstance = win32api.GetModuleHandle(None)
    wc.lpszClassName = "AynimeIssenStyleHotKeyMessageOnlyWindow"
    wc.lpfnWndProc = window_procedure
    class_atom = win32gui.RegisterClass(wc)
    msg_hwnd = win32gui.CreateWindowEx(
        0, class_atom, None, 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None
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
