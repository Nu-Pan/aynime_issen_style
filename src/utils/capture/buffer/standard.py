# utils
from utils.capture.buffer.base import CaptureBuffer

# utils
from utils.image import AISImage


class CaptureBufferStandard(CaptureBuffer):
    """
    キャプチャバッファー
    過去 N 秒間のフレームを保持する
    """

    def __init__(self, frame_rate: int, length_in_sec: int):
        super().__init__()
        self._frame_rate = frame_rate
        self._length_in_sec = length_in_sec

    def get_image(
        self,
        *,
        frame_index: int | None,
        relative_time_in_sec: float | None,
        abs_time_in_sec: float | None,
    ) -> AISImage:
        return AISImage.empty()

    def release(self) -> None:
        # NOTE
        #   状態を持たないので何もしなくて良い
        pass
