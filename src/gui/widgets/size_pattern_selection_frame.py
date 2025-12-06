# std
from typing import Callable, Sequence

# Tk/CTk
import customtkinter as ctk

# utils
from utils.constants import WIDGET_MIN_WIDTH, DEFAULT_FONT_FAMILY
from utils.image import AspectRatioPattern, AspectRatio, ResolutionPattern, Resolution

# gui
from gui.widgets.ais_frame import AISFrame
from gui.model.aynime_issen_style import AynimeIssenStyleModel


class AspectRatioSelectionFrame(AISFrame):
    """
    アスペクト比パターン選択フレーム
    SizePatternSlectionFrame の構成パーツ
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_radio_change: Callable[[], None],
        initial_aspect_ratio: AspectRatioPattern = AspectRatioPattern.E_RAW,
        shown_aspect_raios: Sequence[AspectRatioPattern] = [
            ar for ar in AspectRatioPattern
        ],
        **kwargs,
    ):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)

        # レイアウト
        self.ais.rowconfigure(0, weight=1)

        # アス比選択ラジオボタン変数
        self._aspect_ratio_var = ctk.StringVar(value=initial_aspect_ratio.value)

        # アス比選択ラジオボタン
        self._aspect_ratio_radios: list[ctk.CTkRadioButton] = []
        for i, aspect_ratio in enumerate(shown_aspect_raios):
            aspect_ratio_radio = ctk.CTkRadioButton(
                self,
                text=aspect_ratio.value,
                variable=self._aspect_ratio_var,
                value=aspect_ratio.value,
                command=on_radio_change,
                width=WIDGET_MIN_WIDTH,
                font=default_font,
            )
            self.ais.grid_child(aspect_ratio_radio, 0, i, sticky="ns")
            self.ais.columnconfigure(i, weight=1)
            self._aspect_ratio_radios.append(aspect_ratio_radio)

    @property
    def value(self) -> AspectRatioPattern:
        """
        選択中の値を取得
        """
        return AspectRatioPattern(self._aspect_ratio_var.get())


class ResolutionSelectionFrame(AISFrame):
    """
    解像度パターン選択フレーム
    SizePatternSlectionFrame の構成パーツ
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_radio_change: Callable[[], None],
        initial_resolution: ResolutionPattern = ResolutionPattern.E_RAW,
        shown_resolutions: Sequence[ResolutionPattern] = [
            res for res in ResolutionPattern
        ],
        **kwargs,
    ):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)

        # レイアウト
        self.ais.rowconfigure(0, weight=1)

        # 解像度選択ラジオボタン変数
        self._resolution_var = ctk.StringVar(value=initial_resolution.value)

        # 解像度選択ラジオボタン
        self._resolution_radios: list[ctk.CTkRadioButton] = []
        for i, resolution in enumerate(shown_resolutions):
            resolution_radio = ctk.CTkRadioButton(
                self,
                text=Resolution.from_pattern(resolution).name,
                variable=self._resolution_var,
                value=resolution.value,
                command=on_radio_change,
                width=WIDGET_MIN_WIDTH,
                font=default_font,
            )
            self.ais.grid_child(resolution_radio, 0, i, sticky="ns")
            self.ais.columnconfigure(i, weight=1)
            self._resolution_radios.append(resolution_radio)

    @property
    def value(self) -> ResolutionPattern:
        """
        選択中の値を取得
        """
        return ResolutionPattern(self._resolution_var.get())


class SizePatternSlectionFrame(AISFrame):
    """
    画像解像度選択フレーム
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        model: AynimeIssenStyleModel,
        aux_on_radio_change: Callable[[AspectRatioPattern, ResolutionPattern], None],
        initial_aspect_ratio: AspectRatioPattern = AspectRatioPattern.E_RAW,
        initial_resolution: ResolutionPattern = ResolutionPattern.E_RAW,
        shown_aspect_ratios: Sequence[AspectRatioPattern] = [
            ar for ar in AspectRatioPattern
        ],
        shown_resolutions: Sequence[ResolutionPattern] = [
            res for res in ResolutionPattern
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

        # モデル
        self._model = model

        # ハンドラを保存
        self._aux_on_radio_change = aux_on_radio_change

        # フレームのレイアウト
        self.ais.rowconfigure(0, weight=1)

        # アスペクト比選択フレーム
        self._aspect_ratio_frame = AspectRatioSelectionFrame(
            self, self._on_radio_change, initial_aspect_ratio, shown_aspect_ratios
        )
        self.ais.grid_child(self._aspect_ratio_frame, 0, 0, sticky="ns")
        self.ais.columnconfigure(0, weight=1)

        # 解像度選択フレーム
        self._resolution_frame = ResolutionSelectionFrame(
            self, self._on_radio_change, initial_resolution, shown_resolutions
        )
        self.ais.grid_child(self._resolution_frame, 0, 1, sticky="ns")
        self.ais.columnconfigure(1, weight=1)

        # 初期状態を通知
        self.after("idle", self._on_radio_change)

    def _on_radio_change(self):
        """
        ラジオボタンに変化が合った時に呼び出されるハンドラ
        """
        # 状態を取得
        aspect_raio_pat = self._aspect_ratio_frame.value
        resize_desc_pat = self._resolution_frame.value

        # モデルに反映
        self._model.stream.set_max_size_pattern(
            str(id(self)), aspect_raio_pat, resize_desc_pat
        )

        # コールバック
        self._aux_on_radio_change(aspect_raio_pat, resize_desc_pat)

    @property
    def aspect_ratio(self) -> AspectRatioPattern:
        """
        現在 UI 上で選択されているアスペクト比を返す

        Returns:
            AspectRatio: アスペクト比
        """
        return self._aspect_ratio_frame.value

    @property
    def resolution(self) -> ResolutionPattern:
        """
        現在 UI 上で選択されている解像度を返す

        Returns:
            Resolution: 解像度
        """
        return self._resolution_frame.value
