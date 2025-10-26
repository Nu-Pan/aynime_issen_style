# utils
from utils.capture.buffer.base import CaptureBuffer

# utils
from utils.image import AISImage


class CaptureBufferDummy(CaptureBuffer):
    """
    キャプチャバッファー
    何もしないダミー実装
    """

    def __init__(self):
        super().__init__()

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
