# std
from typing import Self

# PIL
from PIL import Image

# utils
from utils.constants import CAPTURE_FRAME_BUFFER_HOLD_IN_SEC
from utils.image import AISImage
from utils.capture.target import WindowHandle, get_nime_window_text

# ayc
import aynime_capture as ayc


class CaptureStream:
    """
    キャプチャストリーム
    アプリケーションから使いやすいようにキャプチャ機能がまとめられたクラス。
    """

    def __init__(self):
        """
        コンストラクタ
        """
        self._window_handle = None
        self._session = None

    def set_capture_window(self, window_handle: WindowHandle | None) -> None:
        """
        キャプチャ対象のウィンドウを変更する
        """
        # 既存セッションを停止
        self.release()

        # 新規セッションをスタート
        if window_handle is not None:
            self._window_handle = window_handle
            self._session = ayc.Session(
                window_handle.value, CAPTURE_FRAME_BUFFER_HOLD_IN_SEC
            )

    @property
    def capture_window(self) -> WindowHandle | None:
        """
        現在のキャプチャ対象ウィンドウのハンドルを取得する
        """
        return self._window_handle

    @property
    def nime_window_text(self) -> str:
        """
        現在のキャプチャ対象のアニメ名を取得する
        呼び出し簡略化のためのユーティリティ関数
        """
        if self._window_handle is None:
            return "None"
        else:
            return get_nime_window_text(self._window_handle)

    def get_image(
        self,
        relative_time_in_sec: float | None = None,
    ) -> AISImage:
        """
        キャプチャを実行する
        """
        if self._session is None:
            return AISImage.empty()
        else:
            if relative_time_in_sec is None:
                relative_time_in_sec = 0.0
            width, height, frame_bytes = self._session.GetFrameByTime(
                relative_time_in_sec
            )
            pil_image = Image.frombuffer(
                "RGBA", (width, height), frame_bytes, "raw", "BGRA", 0, 1
            )
            return AISImage(pil_image)

    def release(self) -> None:
        """
        内部リソースを開放する。
        インスタンスを del する直前に呼び出すことで、確実に内部リソースを開放できる。
        """
        self._window_handle = None
        if self._session is not None:
            self._session.Close()
            self._session = None
