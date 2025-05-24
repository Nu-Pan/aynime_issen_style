# std
import sys
import os
from pathlib import Path


def is_frozen() -> bool:
    """
    PyInstaller にって凍結されたバイナリ内での実行であるかを調べる

    Returns:
        bool: 凍結バイナリなら True
    """
    return getattr(sys, "frozen", False)


def resource_path(relative_path: str) -> str:
    """
    ファイル relative_path のリソースパスを生成する。
    「直接実行した場合」と「 pyinstaller で凍結された exe から実行された場合」の差異を吸収するための関数。

    Args:
        relative_path (str): 入力ファイル相対パス

    Returns:
        str: リソースパス
            pyinstaller で生成した exe から実行された場合は処理されたパスが返される。
            直接実行時は relative_path が絶対パス化されて返される。
    """
    if is_frozen():
        return os.path.join(sys._MEIPASS, relative_path)  # type: ignore
    else:
        return os.path.join(Path.cwd(), relative_path)
