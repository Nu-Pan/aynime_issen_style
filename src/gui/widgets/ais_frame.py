# std
from typing import Protocol

# Tk/CTk
import customtkinter as ctk

# utils
from utils.constants import WIDGET_PADDING


class HasGrid(Protocol):
    def grid(self, *args, **kwargs) -> None: ...


class AISFrameInterface:
    """
    AISFrame の拡張操作インターフェースクラス
    """

    def __init__(self, parent: "AISFrame"):
        """
        コンストラクタ
        """
        self._parent = parent

    def grid_child(
        self,
        widget: HasGrid,
        row: int,
        column: int,
        row_span: int = 1,
        column_span: int = 1,
        sticky: str = "nswe",
    ) -> None:
        """
        widget を自分自身の直下に grid で配置する
        通常の grid とは逆の関係なので注意
        """
        # グリッドを予約
        row_stop = row + row_span
        column_stop = column + column_span
        self._reserve_grid(row_stop, column_stop)

        # grid で配置
        widget.grid(
            row=2 * row + 1,
            rowspan=2 * (row_span - 1) + 1,
            column=2 * column + 1,
            columnspan=2 * (column_span - 1) + 1,
            sticky=sticky,
        )

    def rowconfigure(
        self,
        row: int,
        row_span: int = 1,
        *,
        weight: int | None = None,
        minsize: int | None = None,
    ):
        """
        行方向のウェイトを設定する
        """
        # パラメータを構築
        kwargs = dict()
        if weight is not None:
            kwargs["weight"] = weight
        if minsize is not None:
            kwargs["minsize"] = minsize

        # 各行に設定
        row_stop = row + row_span
        self._reserve_grid(row_stop, 0)
        for r in range(row, row_stop):
            self._parent.rowconfigure(2 * r + 1, **kwargs)

    def columnconfigure(
        self,
        column: int,
        colunm_span: int = 1,
        *,
        weight: int | None = None,
        minsize: int | None = None,
    ):
        """
        列方向のウェイトを設定する
        """
        # パラメータを構築
        kwargs = dict()
        if weight is not None:
            kwargs["weight"] = weight
        if minsize is not None:
            kwargs["minsize"] = minsize

        # 各列に設定
        column_stop = column + colunm_span
        self._reserve_grid(0, column_stop)
        for c in range(column, column_stop):
            self._parent.columnconfigure(2 * c + 1, **kwargs)

    def _reserve_grid(self, row_stop: int, column_stop: int):
        """
        グリッドを予約する
        NOTE
            grid に対して必要なパディング設定を行うことを「予約」と呼んでいる。
        """
        # 行方向に予約
        if row_stop > self._parent._reserved_row_stop:
            self._parent._reserved_row_stop = row_stop
            self._parent.rowconfigure(0, minsize=WIDGET_PADDING)
            for i in range(row_stop):
                self._parent.rowconfigure(2 * (i + 1), minsize=WIDGET_PADDING)

        # 列方向に予約
        if column_stop > self._parent._reserved_column_stop:
            self._parent._reserved_column_stop = column_stop
            self._parent.columnconfigure(0, minsize=WIDGET_PADDING)
            for i in range(column_stop):
                self._parent.columnconfigure(2 * (i + 1), minsize=WIDGET_PADDING)


class AISFrame(ctk.CTkFrame):
    """
    一閃流フレーム
    grid 上に不可視の要素を差し込んでパディングを実現している。
    """

    def __init__(self, master, **kwargs):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # grid の「予約」済みのサイズ
        self._reserved_row_stop = 0
        self._reserved_column_stop = 0

    @property
    def ais(self) -> AISFrameInterface:
        """
        AIS 拡張操作インターフェースを取得
        """
        return AISFrameInterface(self)
