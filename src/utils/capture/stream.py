# std
from typing import Self

# utils
from utils.image import AISImage
from utils.capture.target import WindowHandle, get_nime_window_text
from utils.capture.backend import *
from utils.capture.buffer import *


class CaptureStream:
    """
    キャプチャストリーム
    アプリケーションから使いやすいようにキャプチャ機能がまとめられたクラス。
    """

    def __init__(self):
        """
        コンストラクタ
        """
        self._backend = CaptureBackendDummy()
        self._buffer = CaptureBufferDummy()

    def set_strategy(self, backend_type: type | None, buffer_type: type | None) -> Self:
        """
        ストラテジーを変更する。
        None は「変更無し」の意味。
        """
        # バックエンドの変更が必要か
        if backend_type is None:
            backend_changed = False
            actual_backend_type = type(self._backend)
        else:
            backend_changed = not isinstance(self._backend, backend_type)
            actual_backend_type = backend_type

        # バッファの変更が必要か
        if buffer_type is None:
            buffer_changed = False
            actual_buffer_type = type(self._buffer)
        else:
            buffer_changed = not isinstance(self._buffer, buffer_type)
            actual_buffer_type = buffer_type

        # 変更なければ何もしない
        if not backend_changed and not buffer_changed:
            return self

        # 既存インスタンスを一度 release
        self.release()

        # impl を生成
        if issubclass(actual_backend_type, CaptureBackendDummy):
            self._backend = CaptureBackendDummy()
        elif issubclass(actual_backend_type, CaptureBackendDxcam):
            self._backend = CaptureBackendDxcam()
        else:
            raise TypeError(f"Invalid actual_backend_type({actual_backend_type})")

        # buffer を生成
        if issubclass(actual_buffer_type, CaptureBufferDummy):
            self._buffer = CaptureBufferDummy()
        if issubclass(actual_buffer_type, CaptureBufferInstant):
            self._buffer = CaptureBufferInstant(lambda: self._backend.capture())
        else:
            raise TypeError(f"Invalid actual_buffer_type({actual_buffer_type})")

        # 正常終了
        return self

    def set_capture_window(self, window_handle: WindowHandle | None) -> None:
        """
        キャプチャ対象のウィンドウを変更する
        """
        self._backend.set_capture_window(window_handle)

    @property
    def capture_window(self) -> WindowHandle | None:
        """
        現在のキャプチャ対象ウィンドウのハンドルを取得する
        """
        return self._backend.capture_window

    @property
    def nime_window_text(self) -> str:
        """
        現在のキャプチャ対象のアニメ名を取得する
        呼び出し簡略化のためのユーティリティ関数
        """
        if self._backend.capture_window is None:
            return "None"
        else:
            return get_nime_window_text(self._backend.capture_window)

    def get_image(
        self,
        *,
        frame_index: int | None = None,
        relative_time_in_sec: float | None = None,
        abs_time_in_sec: float | None = None,
    ) -> AISImage:
        """
        キャプチャを実行する
        """
        return self._buffer.get_image(
            frame_index=frame_index,
            relative_time_in_sec=relative_time_in_sec,
            abs_time_in_sec=abs_time_in_sec,
        )

    def release(self) -> None:
        """
        内部リソースを開放する。
        インスタンスを del する直前に呼び出すことで、確実に内部リソースを開放できる。
        """
        self._buffer.release()
        self._backend.release()
