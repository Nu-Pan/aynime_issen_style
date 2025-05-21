from typing import Callable, List, Tuple
import time
import sys
from math import sqrt
from enum import Enum, auto

from PIL import Image, ImageTk

from tkinter import Event

import customtkinter as ctk

from utils.constants import WIDGET_PADDING, DEFAULT_FONT_NAME
from utils.pil import make_disabled_image
from utils.pil import AspectRatio, Resolution


def pattern_size_to_free(
    aspect_raio: AspectRatio, resolution: Resolution
) -> Tuple[int, int]:
    """
    列挙値を元に数値の解像度を解決する

    Args:
        aspect_raio (AspectRatio): アスペクト比列挙値
        resolution (Resolution): 解像度列挙値

    Returns:
        Tuple[int, int]: Width x Height
    """
    # 解像度
    width = resolution.int_value
    if width is None:
        raise ValueError(f"{resolution} is not supported")

    # アスペクト比
    asp_int = aspect_raio.int_value
    if asp_int is None:
        raise ValueError(f"{aspect_raio} is not supported")

    # 正常終了
    return (width, width * asp_int[1] // asp_int[0])


class SizePatternSlectionFrame(ctk.CTkFrame):
    """
    画像解像度選択フレーム
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        aux_on_radio_change: Callable[[AspectRatio, Resolution], None],
        initial_aspect_ratio: AspectRatio = AspectRatio.E_RAW,
        initial_resolution: Resolution = Resolution.E_RAW,
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
        self.rowconfigure(0, weight=0)
        self.rowconfigure(0, weight=0)
        self.columnconfigure(0, weight=1)

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
        for i, aspect_ratio in enumerate(AspectRatio):
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
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="ns"
        )

        # 解像度選択ラジオボタン変数
        self.resolution_var = ctk.StringVar(value=initial_resolution.value)

        # 解像度選択ラジオボタン
        self.resolution_frame.rowconfigure(0, weight=1)
        self.resolution_radios: List[ctk.CTkRadioButton] = []
        for i, resolution in enumerate(Resolution):
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
        aspect_raio = AspectRatio(self.aspect_ratio_var.get())
        resolution = Resolution(self.resolution_var.get())
        self._aux_on_radio_change(aspect_raio, resolution)
