# utils
from utils.capture_context import WindowHandle
from utils.capture_context_windows import CaptureContextWindows

# model
from gui.model.contents_cache import ImageModel, VideoModel, PlaybackMode


class AynimeIssenStyleModel:
    """
    えぃにめ一閃流奥義「一閃」のモデル
    """

    def __init__(self) -> None:
        """
        コンストラクタ
        """
        self.capture = CaptureContextWindows()
        self.window_selection_image = ImageModel()
        self.still = ImageModel()
        self.video = VideoModel()
        self.playback_mode = PlaybackMode.FORWARD
