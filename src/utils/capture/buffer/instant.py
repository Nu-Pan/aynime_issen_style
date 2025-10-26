# utils
from utils.capture.buffer.base import CaptureBuffer

# utils
from utils.image import AISImage
from utils.capture.buffer.base import CaptureHandler


class CaptureBufferInstant(CaptureBuffer):
    """
    キャプチャバッファー
    バッファリングせずに即時キャプチャする
    """

    def __init__(self, capture_handler: CaptureHandler):
        super().__init__()
        self._capture_handler = capture_handler

    def get_image(
        self,
        *,
        frame_index: int | None,
        relative_time_in_sec: float | None,
        abs_time_in_sec: float | None,
    ) -> AISImage:
        # NOTE
        #   バッファリング機構を持たないので、引数を無視してその場でキャプチャして返す
        return self._capture_handler()

    def release(self) -> None:
        # NOTE
        #   状態を持たないので何もしなくて良い
        pass
