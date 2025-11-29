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
                    window_handle.value,
                    CAPTURE_FRAME_BUFFER_DURATION_IN_SEC,
                    None,
                    None,
                )
                self._window_handle = window_handle
            except Exception as e:
                self._session = None
                self._window_handle = None
                raise

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
        # セッションが未初期化なら空画像を返す
        if self._session is None:
            raise RuntimeError("Session is not initialized")

        # 相対時刻を正規化
        if relative_time_in_sec is None:
            relative_time_in_sec = 0.0

        # キャプチャ
        # NOTE
        #   有効なフレームが来るまで繰り返しリトライする
        TRY_LIMIT_IN_SEC = 2.0
        TRY_COUNT = 20
        width, height, frame_bytes = (None, None, None)
        for _ in range(TRY_COUNT + 1):
            width, height, frame_bytes = self._session.GetFrameByTime(
                relative_time_in_sec
            )
            if frame_bytes is not None:
                break
            else:
                sleep(TRY_LIMIT_IN_SEC / TRY_COUNT)

        # タイムアウト
        if width is None or height is None or frame_bytes is None:
            raise RuntimeError(
                f"Failed to captures valid frame in {TRY_LIMIT_IN_SEC} sec"
            )

        # 正常終了
        return AISImage.from_bytes(width, height, frame_bytes)

    def capture_animation(
        self, fps: float | None = None, duration_in_sec: float | None = None
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
