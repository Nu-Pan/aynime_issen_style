# std
from typing import Generator, List, Union, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
import time

# win32
import win32gui, win32ui, win32con
from PIL import Image

# dxcam
import dxcam_cpp as dxcam

# utils
from utils.windows import enumerate_dxgi_outputs
from utils.image import AISImage


@dataclass
class WindowHandle:
    """
    ウィンドウ識別子を保持するクラス
    """

    value: int


class CaptureContext(ABC):
    """
    キャプチャコンテキスト純粋仮想基底クラス
    マルチプラットフォーム対応の可能性に備えて残してあるが、現状は Windows 版しか対応してないので存在する意味は無い。
    """

    @abstractmethod
    def enumerate_windows(self) -> Generator[WindowHandle, None, None]:
        """
        キャプチャ対象のウィンドウを列挙する
        """
        ...

    @abstractmethod
    def set_capture_window(self, window_handle: WindowHandle) -> None:
        """
        キャプチャ対象のウィンドウを変更する
        """
        ...

    @property
    @abstractmethod
    def current_window_name(self) -> Optional[str]:
        """
        現在のキャプチャ対象のウィンドウ名を取得
        """
        ...

    @abstractmethod
    def get_window_name(self, window_handle: WindowHandle) -> str:
        """
        指定ウィンドウのウィンドウ名を取得
        """
        ...

    @abstractmethod
    def capture(self) -> AISImage:
        """
        キャプチャを実行する
        """
        ...

    @abstractmethod
    def release(self) -> None:
        """
        内部リソースを開放する。
        dxcam-cpp のダメ挙動に対処するために必要なダメ関数。
        インスタンスを del する直前に呼び出すことで、確実に内部リソースを開放できる。
        """
        ...
