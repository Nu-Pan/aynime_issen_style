# std
from typing import List, Optional

# PIL
from PIL.ImageTk import PhotoImage

# Tk/CTk
import customtkinter as ctk

# utils
from utils.ctk import configure_presence
from utils.pil import ResizeDesc, AspectRatioPattern

# gui
from gui.model.aynime_issen_style import AynimeIssenStyleModel
from gui.model.contents_cache import ImageLayer


class AnimationLabel(ctk.CTkLabel):
    """
    連番静止画をアニメーション再生する用のラベル
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        model: AynimeIssenStyleModel,
        blank_text: Optional[str] = None,
        **kwargs
    ):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # 現在表示している画像
        # NOTE
        #   現在表示している PhotoImage のインスタンスをウィジェットから取ることはできない。
        #   そのため、この階層でキャッシュ情報を保持しておく
        self._current_frame = None

        # 内部状態を適当に初期化
        self._model = model
        self._frame_index = 0
        if blank_text is None:
            self._blank_text = "Animation Preview"
        else:
            self._blank_text = blank_text

        # リサイズハンドラ
        self.bind("<Configure>", self._on_resize)

        # 更新処理をキック
        self._next_frame_handler()

    def _next_frame_handler(self):
        """
        表示状態を次のフレームに進めるハンドラ
        """
        # 有効なフレームの有無で分岐
        if self._model.video.num_enable_frames == 0:
            # 代替テキストを表示
            configure_presence(self, self._blank_text)
        else:
            # 次の有効フレームまでシーク
            while True:
                self._frame_index += 1
                if self._frame_index >= self._model.video.num_total_frames:
                    self._frame_index = 0
                if self._model.video.get_enable(self._frame_index):
                    break

            # プレビュー画像を取得・表示
            new_frame = self._model.video.get_frame(
                ImageLayer.PREVIEW, self._frame_index
            )
            if new_frame != self._current_frame:
                if isinstance(new_frame, PhotoImage):
                    configure_presence(self, new_frame)
                    self._current_frame = new_frame
                else:
                    configure_presence(self, self._blank_text)
                    self._current_frame = None

        # 次の更新処理をキック
        self.after(1000 // self._model.video.frame_rate, self._next_frame_handler)

    def _on_resize(self, _):
        """
        リサイズハンドラ
        """
        # 適切なサイズを解決
        actual_width = self.winfo_width()
        actual_height = self.winfo_height()
        self._model.video.set_size(
            ImageLayer.PREVIEW,
            ResizeDesc(AspectRatioPattern.E_RAW, actual_width, actual_height),
        )
