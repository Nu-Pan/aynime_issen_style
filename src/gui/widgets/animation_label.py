# std
from typing import List, Optional

# PIL
from PIL import Image, ImageTk

# Tk/CTk
import customtkinter as ctk

# utils
from utils.pil import IntegratedImage
from utils.ctk import silent_configure


class AnimationLabel(ctk.CTkLabel):
    """
    連番静止画をアニメーション再生する用のラベル
    """

    def __init__(
        self, master: ctk.CTkBaseClass, blank_text: Optional[str] = None, **kwargs
    ):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # 内部状態を適当に初期化
        self.set_frames()
        self.set_frame_rate(24)
        self._frame_index = 0
        if blank_text is None:
            self._blank_text = "Animation Preview"
        else:
            self._blank_text = blank_text

        # リサイズハンドラ
        self.bind("<Configure>", self._on_resize)

        # 更新処理をキック
        self._next_frame_handler()

    def set_frames(self, frames: List[IntegratedImage] = []):
        """
        アニメーション表示するフレーム（画像）群を設定する

        Args:
            frames (List[Union[Image.Image, ImageTk.PhotoImage]]): 表示したいフレーム（画像）群
        """
        # 全ての画像を PIL Image として保持
        self._original_frames: List[IntegratedImage] = []
        for frame in frames:
            if isinstance(frame, IntegratedImage):
                self._original_frames.append(frame)
            else:
                raise TypeError(f"Invalid type of frame({type(frame)})")

        # ちょうどいいサイズにする
        self._on_resize(None)

    @property
    def frames(self) -> List[IntegratedImage]:
        """
        設定されているフレーム（画像）群を取得する

        Returns:
            List[Image.Image]: 設定されているフレーム（画像）群
        """
        return self._original_frames

    def set_frame_rate(self, frame_rate: int):
        """
        アニメーションのフレームレートを設定

        Args:
            frame_rate (int): アニメーションのフレームレート
        """
        self._interval_in_ms = int(1000 / frame_rate)

    @property
    def interval_in_ms(self) -> int:
        """
        更新間隔（ミリ秒）

        Returns:
            int: 更新間隔（ミリ秒）
        """
        return self._interval_in_ms

    def _next_frame_handler(self):
        """
        表示状態を次のフレームに進めるハンドラ
        """
        # 表示を更新
        if len(self._preview_frames) == 0:
            silent_configure(self, image="", text=self._blank_text)
        else:
            self._frame_index = (self._frame_index + 1) % len(self._preview_frames)
            silent_configure(
                self, image=self._preview_frames[self._frame_index], text=""
            )

        # 次の更新処理をキック
        self.after(self._interval_in_ms, self._next_frame_handler)

    def _on_resize(self, _):
        """
        リサイズハンドラ
        """
        # 適切なサイズを解決
        actual_width = self.winfo_width()
        actual_height = self.winfo_height()

        # 表示用のサイズにリサイズ
        self._preview_frames: List[ImageTk.PhotoImage] = []
        for original_frame in self._original_frames:
            pil_frame = original_frame.preview(actual_width, actual_height)
            tk_frame = ImageTk.PhotoImage(pil_frame)
            self._preview_frames.append(tk_frame)
