# std
from time import sleep

# utils
from utils.constants import CAPTURE_FRAME_BUFFER_DURATION_IN_SEC
from utils.image import AISImage, AspectRatio
from utils.capture.target import WindowHandle, get_nime_window_text
from utils.user_properties import USER_PROPERTIES

# ayc
import aynime_capture as ayc

from utils.metadata import AspectRatioPattern, ResolutionPattern


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
        # NOTE
        #   RAW 保存解像度の最低保証値としてフル HD をプリロードしていることに相当する
        self._max_width = USER_PROPERTIES.get(
            "capture_stream_preload_max_width",
            1920,
        )
        self._max_height = USER_PROPERTIES.get(
            "capture_stream_preload_max_height",
            1080,
        )
        self._session = None

    def restart_session(self) -> None:
        """
        現在の内部状態に基づいてセッションを破棄・再スタートする。
        """
        self.release()
        if self._window_handle is not None:
            try:
                self._session = ayc.Session(
                    self._window_handle.value,
                    CAPTURE_FRAME_BUFFER_DURATION_IN_SEC,
                    self._max_width,
                    self._max_height,
                )
            except Exception as e:
                self._session = None
                raise

    def set_capture_window(self, window_handle: WindowHandle | None) -> None:
        """
        キャプチャ対象のウィンドウを変更する
        """
        if window_handle is None:
            self._window_handle = None
            self.release()
        elif self._window_handle is None or window_handle != self._window_handle:
            self._window_handle = window_handle
            self.restart_session()

    def set_max_size(
        self,
        max_width: int | None,
        max_height: int | None,
    ) -> None:
        """
        キャプチャの最大サイズを変更する
        複数箇所で異なる最大サイズを要求されるはずなので、それらを key で区別して個別に保持する。
        それらの中でもっとも大きいサイズが要求として選択される。
        """
        # 最大サイズ情報を更新
        # NOTE
        #   None は無指定とみなして無視
        #   プリロードされている値があるはずなので、単純な比較で良い
        does_restart = False
        if max_width is not None and max_width > self._max_width:
            self._max_width = max_width
            does_restart = True
        if max_height is not None and max_height > self._max_height:
            self._max_height = max_height
            does_restart = True

        # セッションリスタート
        if does_restart:
            self.restart_session()

    def set_max_size_pattern(
        self,
        aspect_ratio_pattern: AspectRatioPattern,
        resize_desc_patetrn: ResolutionPattern,
    ) -> None:
        """
        キャプチャの最大サイズを変更する
        パターン指定版
        """
        # ResizeDescPattern
        if resize_desc_patetrn == ResolutionPattern.E_RAW:
            max_width = None
        else:
            max_width = int(resize_desc_patetrn.value)

        # AspectRatioPattern
        if max_width is None or aspect_ratio_pattern == AspectRatioPattern.E_RAW:
            max_height = None
        else:
            aspect_ratio = AspectRatio.from_pattern(aspect_ratio_pattern)
            if aspect_ratio.width is None:
                raise RuntimeError("Logic Error")
            else:
                arw = aspect_ratio.width
            if aspect_ratio.height is None:
                raise RuntimeError("Logic Error")
            else:
                arh = aspect_ratio.height
            max_height = round(max_width * arh / arw)

        # 通常版を呼び出す
        self.set_max_size(max_width, max_height)

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
            text, _ = get_nime_window_text(self._window_handle)
            return text

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

    def capture_video(
        self, fps: float | None = None, duration_in_sec: float | None = None
    ) -> list[AISImage]:
        """
        動画（連番静止画）をキャプチャする
        """
        # セッション構築前の呼び出しはエラー
        if self._session is None:
            raise ValueError("Capture session not started")

        # 直近のスナップショットを取得
        frames: list[AISImage] = []
        with ayc.Snapshot(self._session, fps, duration_in_sec) as snapshot:
            for frame_index in range(snapshot.size):
                frame_args = snapshot.GetFrame(frame_index)
                ais_image = AISImage.from_bytes(*frame_args)
                frames.append(ais_image)

        # 正常終了
        return frames

    def release(self) -> None:
        """
        内部リソースを開放する。
        インスタンスを del する直前に呼び出すことで、確実に内部リソースを開放できる。
        """
        if self._session is not None:
            self._session.Close()
            self._session = None
