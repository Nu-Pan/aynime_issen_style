# std
from typing import Optional

# TK/CTk
import customtkinter as ctk

# utils
from utils.constants import DEFAULT_FONT_FAMILY
from utils.ctk import silent_configure, configure_presence
from utils.image import ResizeDesc, AspectRatioPattern, AISImage

# model
from gui.model.contents_cache import ImageModel, ImageLayer, ImageModelEditSession


class StillLabel(ctk.CTkLabel):
    """
    画像表示用のフレーム
    設定された画像をアスペクト比を維持したまま全体が映るようにダウンスケールして表示する
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        image_model: ImageModel,
        blank_text: str,
        **kwargs
    ):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # 現在表示している画像
        # NOTE
        #   現在表示している画像のインスタンスをウィジェットから取ることはできない。
        #   そのため、この階層でキャッシュ情報を保持しておく
        self._current_frame = None

        # モデル関係
        self._image_model = image_model
        self._image_model.register_notify_handler(
            ImageLayer.PREVIEW, self._on_preview_changed
        )

        # フォントを設定
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)
        silent_configure(self, font=default_font)

        # ブランク表示
        self._blank_text = blank_text
        configure_presence(self, blank_text)

        # リサイズハンドラ
        self.bind("<Configure>", self._on_resize)

    def _on_preview_changed(self):
        """
        画像に変更があった際に呼び出されるハンドラ
        """
        # UI 的に反映
        new_frame = self._image_model.get_image(ImageLayer.PREVIEW)
        if new_frame != self._current_frame:
            if isinstance(new_frame, AISImage):
                configure_presence(self, new_frame.photo_image)
                self._current_frame = new_frame
            else:
                configure_presence(self, self._blank_text)
                self._current_frame = None

    def _on_resize(self, _):
        """
        リサイズハンドラ
        """
        # モデルにサイズを反映
        actual_width = self.winfo_width()
        actual_height = self.winfo_height()
        with ImageModelEditSession(self._image_model) as edit:
            edit.set_size(
                ImageLayer.PREVIEW,
                ResizeDesc(AspectRatioPattern.E_RAW, actual_width, actual_height),
            )
