# std
from typing import Callable, List, Tuple, Sequence

# Tk/CTk
import customtkinter as ctk

# utils
from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.pil import AspectRatioPattern, ResizeDesc


class SizePatternSlectionFrame(ctk.CTkFrame):
    """
    画像解像度選択フレーム
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        aux_on_radio_change: Callable[[AspectRatioPattern, ResizeDesc.Pattern], None],
        initial_aspect_ratio: AspectRatioPattern = AspectRatioPattern.E_RAW,
        initial_resolution: ResizeDesc.Pattern = ResizeDesc.Pattern.E_RAW,
        shown_aspect_raios: Sequence[AspectRatioPattern] = [
            ar for ar in AspectRatioPattern
        ],
        shown_resolutions: Sequence[ResizeDesc.Pattern] = [
            res for res in ResizeDesc.Pattern
        ],
        **kwargs,
    ):
        """
        コンストラクタ

        Args:
            master (ctk.CTkBaseClass): 親ウィジェット
            aux_on_radio_change (Callable): 変更があった時に呼び出されるハンドラ
        """
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

        # ハンドラを保存
        self._aux_on_radio_change = aux_on_radio_change

        # フレームのレイアウト
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        # アス比選択フレーム
        self.aspect_ratio_frame = ctk.CTkFrame(self)
        self.aspect_ratio_frame.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
        )

        # アス比選択ラジオボタン変数
        self.aspect_ratio_var = ctk.StringVar(value=initial_aspect_ratio.value)

        # アス比選択ラジオボタン
        self.aspect_ratio_frame.rowconfigure(0, weight=1)
        self.aspect_ratio_radios: List[ctk.CTkRadioButton] = []
        for i, aspect_ratio in enumerate(shown_aspect_raios):
            aspect_ratio_radio = ctk.CTkRadioButton(
                self.aspect_ratio_frame,
                text=aspect_ratio.value,
                variable=self.aspect_ratio_var,
                value=aspect_ratio.value,
                command=self._on_radio_change,
                width=0,
                font=default_font,
            )
            aspect_ratio_radio.grid(
                row=0, column=i, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
            )
            self.aspect_ratio_frame.columnconfigure(i, weight=1)
            self.aspect_ratio_radios.append(aspect_ratio_radio)

        # 解像度選択フレーム
        self.resolution_frame = ctk.CTkFrame(self)
        self.resolution_frame.grid(
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
        )

        # 解像度選択ラジオボタン変数
        self.resolution_var = ctk.StringVar(value=initial_resolution.value)

        # 解像度選択ラジオボタン
        self.resolution_frame.rowconfigure(0, weight=1)
        self.resolution_radios: List[ctk.CTkRadioButton] = []
        for i, resolution in enumerate(shown_resolutions):
            resolution_radio = ctk.CTkRadioButton(
                self.resolution_frame,
                text=resolution.value,
                variable=self.resolution_var,
                value=resolution.value,
                command=self._on_radio_change,
                width=0,
                font=default_font,
            )
            resolution_radio.grid(
                row=0, column=i, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
            )
            self.resolution_frame.columnconfigure(i, weight=1)
            self.resolution_radios.append(resolution_radio)

        # 初期状態を通知
        self.after("idle", self._on_radio_change)

    def _on_radio_change(self):
        """
        ラジオボタンに変化が合った時に呼び出されるハンドラ
        """
        aspect_raio = AspectRatioPattern(self.aspect_ratio_var.get())
        resize_desc = ResizeDesc.Pattern(self.resolution_var.get())
        self._aux_on_radio_change(aspect_raio, resize_desc)

    @property
    def aspect_ratio(self) -> AspectRatioPattern:
        """
        現在 UI 上で選択されているアスペクト比を返す

        Returns:
            AspectRatio: アスペクト比
        """
        return AspectRatioPattern(self.aspect_ratio_var.get())

    @property
    def resolution(self) -> ResizeDesc.Pattern:
        """
        現在 UI 上で選択されている解像度を返す

        Returns:
            Resolution: 解像度
        """
        return ResizeDesc.Pattern(self.resolution_var.get())
