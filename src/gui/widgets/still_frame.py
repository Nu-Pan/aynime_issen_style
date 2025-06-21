# std
from typing import Optional

# PIL
from PIL import Image, ImageTk

# TK/CTk
import customtkinter as ctk

# utils
from utils.pil import IntegratedImage
from utils.constants import DEFAULT_FONT_NAME
from utils.ctk import silent_configure


class StillLabel(ctk.CTkLabel):
    """
    画像表示用のフレーム
    設定された画像をアスペクト比を維持したまま全体が映るようにダウンスケールして表示する
    """

    def __init__(self, master: ctk.CTkBaseClass, **kwargs):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # フォントを設定
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)
        silent_configure(self, font=default_font)

        # 内部状態
        self._integrated_image = None

        # リサイズハンドラ
        self.bind("<Configure>", self._on_resize)

    def set_contents(
        self, image: Optional[IntegratedImage] = None, text: Optional[str] = None
    ):
        """
        表示するコンテンツを設定する

        Args:
            image (Optional[Image.Image], optional): 表示する画像
            text (Optional[str], optional): 表示する文字列
        """
        # 画像の更新
        if isinstance(image, IntegratedImage):
            self._integrated_image = image
        elif image is None:
            self._integrated_image = None
        else:
            raise TypeError(type(image))

        # テキストの更新
        if text is None:
            silent_configure(self, text="")
        else:
            silent_configure(self, text=text)

        # リサイズを実行
        self._on_resize(None)

    def _on_resize(self, _):
        """
        リサイズハンドラ
        """
        # 画像なしの場合は何もしない
        if self._integrated_image is None:
            silent_configure(self, image="")
            return

        # エイリアス
        actual_width = self.winfo_width()
        actual_height = self.winfo_height()

        # リサイズ
        # NOTE
        #   枠いっぱいに全体が映るようにアス比を維持してスケール
        pil_image = self._integrated_image.preview(actual_width, actual_height)
        silent_configure(self, image=ImageTk.PhotoImage(pil_image))
