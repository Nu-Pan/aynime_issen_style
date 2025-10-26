# utils
from utils.image import AISImage
from utils.capture.backend.base import WindowHandle, CaptureBackend


class CaptureBackendDummy(CaptureBackend):
    """
    キャプチャバックエンド
    何もしないダミー実装
    """

    def __init__(self):
        super().__init__()

    def capture(self) -> AISImage:
        return AISImage.empty()

    def release(self) -> None:
        """
        明示的にリソースを解放する
        これを呼び出さないとリソースが解放されないので次の初期化が失敗するかも。
        """
        pass
