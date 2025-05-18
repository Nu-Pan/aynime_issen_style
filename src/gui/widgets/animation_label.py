from typing import List, Union
import warnings

from PIL import Image, ImageTk

from tkinter import Event
import customtkinter as ctk

from utils.pil import isotropic_downscale_image_in_rectangle


class AnimationLabel(ctk.CTkLabel):
    """
    連番静止画をアニメーション再生する用のラベル
    """

    def __init__(self, master: ctk.CTkBaseClass, **kwargs):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # 内部状態を適当に初期化
        self.set_frames()
        self.set_frame_rate(24)
        self._frame_index = 0

        # リサイズハンドラ
        self.bind("<Configure>", self._on_resize)

        # 更新処理をキック
        self._next_frame_handler()

    def set_frames(self, frames: List[Image.Image] = []):
        """
        アニメーション表示するフレーム（画像）群を設定する

        Args:
            frames (List[Union[Image.Image, ImageTk.PhotoImage]]): 表示したいフレーム（画像）群
        """
        # 全ての画像を PIL Image として保持
        self._original_frames = []
        for frame in frames:
            if isinstance(frame, Image.Image):
                self._original_frames.append(frame)
            else:
                raise TypeError(f"Invalid type of frame({type(frame)})")

        # ちょうどいいサイズにする
        self._on_resize(None)

    def set_frame_rate(self, frame_rate: int):
        """
        アニメーションのフレームレートを設定

        Args:
            frame_rate (int): アニメーションのフレームレート
        """
        self._interval_in_ms = int(1000 / frame_rate)

    def _next_frame_handler(self):
        """
        表示状態を次のフレームに進めるハンドラ
        """
        # 表示を更新
        if len(self._frames) == 0:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Warning: Given image is not CTkImage",
                    category=UserWarning,
                )
                self.silent_configure(image="", text="Animation Preview")
        else:
            self._frame_index = (self._frame_index + 1) % len(self._frames)
            self.silent_configure(image=self._frames[self._frame_index], text="")

        # 次の更新処理をキック
        self.after(self._interval_in_ms, self._next_frame_handler)

    def _on_resize(self, _):
        """
        リサイズハンドラ
        """
        # 適切なサイズを解決
        actual_width = self.winfo_width()
        actual_height = self.winfo_height()

        # リサイズ
        self._frames: List[ImageTk.PhotoImage] = []
        for original_frame in self._original_frames:
            pil_frame = isotropic_downscale_image_in_rectangle(
                original_frame, actual_width, actual_height
            )
            tk_frame = ImageTk.PhotoImage(pil_frame)
            self._frames.append(tk_frame)

    def silent_configure(self, **kwargs):
        """
        警告抑制付き configure
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            self.configure(**kwargs)
