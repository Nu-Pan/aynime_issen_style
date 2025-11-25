# std
from typing import Self
from time import sleep

# PIL
from PIL import Image

# utils
from utils.constants import CAPTURE_FRAME_BUFFER_DURATION_IN_SEC
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
            try:
                self._session = ayc.Session(
                    window_handle.value, CAPTURE_FRAME_BUFFER_DURATION_IN_SEC
                )
                self._window_handle = window_handle
            except Exception as e:
                self._session = None
                self._window_handle = None
                raise

        # 最初の１枚が来るまで待つ
        if self._session:
            TRY_LIMIT_IN_SEC = 2.0
            TRY_COUNT = 10
            width, height, frame_bytes = (None, None, None)
            for _ in range(TRY_COUNT):
                try:
                    width, height, frame_bytes = self._session.GetFrameByTime(0.0)
                except RuntimeError as e:
                    sleep(TRY_LIMIT_IN_SEC / TRY_COUNT)
                    continue
            if frame_bytes is None:
                raise RuntimeError(f"Fist frame not arrived in {TRY_LIMIT_IN_SEC} sec")

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

    def capture_still(
        self,
        relative_time_in_sec: float | None = None,
    ) -> AISImage:
        """
        スチル画像をキャプチャする
        """
        if self._session is None:
            return AISImage.empty()
        else:
            if relative_time_in_sec is None:
                relative_time_in_sec = 0.0
            width, height, frame_bytes = self._session.GetFrameByTime(
                relative_time_in_sec
            )
            return AISImage.from_bytes(width, height, frame_bytes)

    def capture_animation(
        self, fps: int | None = None, duration_in_sec: float | None = None
    ) -> list[AISImage]:
        """
        アニメ―ション（連番静止画）をキャプチャする
        """
        if self._session is None:
            return []
        else:
            frames: list[AISImage] = []
            with ayc.Snapshot(self._session, fps, duration_in_sec) as snapshot:
                for frame_index in range(snapshot.size):
                    frame_args = snapshot.GetFrame(frame_index)
                    ais_image = AISImage.from_bytes(*frame_args)
                    frames.append(ais_image)
            return frames

    def release(self) -> None:
        """
        内部リソースを開放する。
        インスタンスを del する直前に呼び出すことで、確実に内部リソースを開放できる。
        """
        self._window_handle = None
        if self._session is not None:
            self._session.Close()
            self._session = None
