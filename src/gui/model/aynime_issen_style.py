# model
from gui.model.capture import CaptureModel
from gui.model.contents_cache import ImageModel


class AynimeIssenStyleModel:
    """
    えぃにめ一閃流奥義「一閃」のモデル
    """

    def __init__(self) -> None:
        """
        コンストラクタ
        """
        self.capture = CaptureModel()
        self.window_selection = ImageModel()
        self.still = ImageModel()
