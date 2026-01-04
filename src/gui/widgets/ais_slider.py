# std
from typing import Callable, Any, TypeVar, Generic

# ctk
import customtkinter as ctk

# utils
from utils.constants import (
    DEFAULT_FONT_FAMILY,
    NUMERIC_FONT_FAMILY,
    WIDGET_MIN_WIDTH,
    WIDGET_MIN_HEIGHT,
)

# gui
from gui.widgets.ais_frame import AISFrame


T = TypeVar("T")


class AISSlider(AISFrame, Generic[T]):
    """
    使いやすくした CTkSlider
    """

    def __init__(
        self,
        master,
        description: str | None,
        value_list: list[T],
        value_distance: Callable[[T, T], float],
        value_formatter: Callable[[T], str],
        value_unit: str | None,
        **kwargs,
    ):
        """
        コンストラクタ
        """
        # 基底コンストラクタ
        super().__init__(
            master, width=WIDGET_MIN_WIDTH, height=WIDGET_MIN_HEIGHT, **kwargs
        )

        # 値リストは最低でも１つ必要
        if len(value_list) < 1:
            raise ValueError("# of value_list must not be 0")

        # 値関係
        # NOTE
        #   CTkSlider は float 空間上に変化が起きると _on_slider_changed をコールバックしてくる。
        #   つまり、１ドットでもスライダーが動くと、それがたとえステップの隙間でもコールバックしてくる。
        #   AISSlider 的に意味があるのは int 空間上の離散的変動なので、この挙動は望ましくない。
        #   この int 空間上での離散的変動をトラックするために self._slider_index を内部状態のマスターとする。
        self._slider_index = None
        self._value_list = value_list
        self._value_distance = value_distance
        self._value_formatter = value_formatter
        self._value_unit = value_unit

        # フォントをロード
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)
        numeric_font = ctk.CTkFont(NUMERIC_FONT_FAMILY)

        # レイアウト設定
        self.ais.rowconfigure(0, weight=1)

        # 列方向の配置を解決
        if description is None:
            desc_label_column = -1
            slider_colunm = 0
            value_label_colunn = 1
        else:
            desc_label_column = 0
            slider_colunm = 1
            value_label_colunn = 2

        # 説明ラベル
        if description is None:
            self._desc_label = None
        else:
            self._desc_label = ctk.CTkLabel(
                self, text=description, font=default_font, width=WIDGET_MIN_WIDTH
            )
            self.ais.grid_child(self._desc_label, 0, desc_label_column)
            self.ais.columnconfigure(desc_label_column, weight=0)

        # スライダー
        self._slider = ctk.CTkSlider(
            self,
            from_=0,
            to=len(value_list) - 1,
            number_of_steps=len(value_list) - 1,
            command=self._on_slider_changed,
            height=1,
        )
        self.ais.grid_child(self._slider, 0, slider_colunm)
        self.ais.columnconfigure(slider_colunm, weight=1)

        # 値ラベル
        value_placeholder_text = "-" * max(
            len(self._value_formatter(v)) for v in value_list
        )
        if value_unit is None:
            invalid_value_label_text = f"{value_placeholder_text}"
        else:
            invalid_value_label_text = f"{value_placeholder_text} {value_unit}"
        self._value_label = ctk.CTkLabel(
            self,
            text=invalid_value_label_text,
            font=numeric_font,
            width=round(1.5 * WIDGET_MIN_WIDTH),
        )
        self.ais.grid_child(self._value_label, 0, value_label_colunn)
        self.ais.columnconfigure(value_label_colunn, weight=0)

        # ハンドラリスト
        self._handlers: list[Callable[[T], None]] = []

    @property
    def value(self) -> T:
        """
        値を取得
        """
        if self._slider_index is not None:
            return self._value_list[self._slider_index]
        else:
            raise ValueError("self._value_index is None")

    def set_value(self, value: T) -> None:
        """
        値を設定
        """
        # 適切な値を self._value_list から探す
        best_index = None
        best_diff = None
        for vi in range(len(self._value_list)):
            v = self._value_list[vi]
            diff = self._value_distance(v, value)
            if best_diff is None or diff < best_diff:
                best_index = vi
                best_diff = diff

        # 適切な値が見つからなかった場合はエラー
        if best_index is None:
            raise ValueError(f"value={value} is not found in self._value_list")

        # ウィジェットに反映
        # NOTE
        #   変更がある場合だけ設定処理を走らせる
        #   これがないとイベント発火が無限ループして大変なことになる
        if self._slider_index is None or self._slider_index != best_index:
            # self._slider_index = best_index
            self._slider.set(best_index)
            self._on_slider_changed(best_index)

    def register_handler(self, handler: Callable[[T], None]):
        """
        スライダーに変更があった際に呼び出されるハンドラを登録
        こちらは AISSlider からコールバックされる
        """
        self._handlers.append(handler)

    def _on_slider_changed(self, slider_index: Any) -> None:
        """
        スライダー変更ハンドラ
        こちらは CTk ウィジェットからコールバックされる
        """
        # 同じ値が連続した場合はスキップ
        slider_index = int(slider_index)
        if slider_index == self._slider_index:
            return

        # 値を解決
        value = self._value_list[slider_index]
        value_str = self._value_formatter(value)

        # 状態更新
        self._slider_index = slider_index
        if self._value_unit is None:
            self._value_label.configure(text=f"{value_str}")
        else:
            self._value_label.configure(text=f"{value_str} {self._value_unit}")

        # コールバック呼び出し
        for handler in self._handlers:
            handler(value)
