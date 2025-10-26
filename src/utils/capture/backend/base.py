# std
from abc import ABC, abstractmethod

# utils
from utils.image import AISImage
from utils.capture.target import WindowHandle


class CaptureBackend(ABC):
    """
    キャプチャバックエンド基底クラス
    画像１枚をキャプチャする処理を担当する。
    キャプチャ結果のマネジメントは責任範囲外。
    """

    def __init__(self):
        """
        コンストラクタ
        """
        self._window_handle = None

    def set_capture_window(self, window_handle: WindowHandle | None) -> None:
        """
        キャプチャ対象ウィンドウを設定する
        """
        self._window_handle = window_handle

    @property
    def capture_window(self) -> WindowHandle | None:
        """
        現在設定されているキャプチャ対象ウィンドウを取得する
        """
        return self._window_handle

    @abstractmethod
    def capture(self) -> AISImage:
        """
        キャプチャを行い画像を返す
        """
        ...

    @abstractmethod
    def release(self) -> None:
        """
        明示的にリソースを解放する
        これを呼び出さないでインスタンスを再生成した場合、その成功は保証されない。
        """
        ...
