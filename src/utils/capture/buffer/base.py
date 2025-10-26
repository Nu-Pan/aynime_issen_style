# std
from abc import ABC, abstractmethod
from typing import Callable

# utils
from utils.image import AISImage

type CaptureHandler = Callable[[], AISImage]


class CaptureBuffer(ABC):
    """
    キャプチャバッファー
    内部でキャプチャ結果をバッファリングし、近い過去のキャプチャにアクセス可能にする。
    """

    def set_capture_handler(self, handler: CaptureHandler):
        """
        キャプチャーハンドラーを設定する
        バッファには handler から得た画像が詰め込まれる。
        """
        ...

    @abstractmethod
    def get_image(
        self,
        *,
        frame_index: int | None,
        relative_time_in_sec: float | None,
        abs_time_in_sec: float | None,
    ) -> AISImage:
        """
        画像を１枚取得する
        引数を渡さない場合、最新の１枚を返す。
        """
        ...

    @abstractmethod
    def release(self) -> None:
        """
        明示的にリソースを解放する。
        これを呼び出さないでインスタンスを再生成した場合、その成功は保証されない。
        """
        ...
