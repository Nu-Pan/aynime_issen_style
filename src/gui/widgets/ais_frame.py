# Tk/CTk
import customtkinter as ctk


class AISFrame:
    """
    フレーム
    grid 上に不可視の要素を差し込んでパディングを実現する。
    """

    def __init__(self, master, pad: int, **kwargs):
        """
        コンストラクタ
        """
        # 本体
        self._impl = ctk.CTkFrame(master, **kwargs)

        # パラメータ保存
        self._pad = pad

        # grid の「予約」済みのサイズ
        self._reserved_row_stop = 0
        self._reserved_column_stop = 0

    @property
    def ctk_impl(self) -> ctk.CTkFrame:
        """
        内部実装の CTk オブジェクトを取得する
        """
        return self._impl

    def grid_child(
        self,
        widget: ctk.CTkBaseClass,
        row: int,
        column: int,
        row_span: int = 1,
        column_span: int = 1,
        sticky: str = "nswe",
    ) -> None:
        """
        child_widget を自分自身の直下に grid で配置する
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

    def set_row_weights(self, weight: int, row: int, row_span: int = 1):
        """
        行方向のウェイトを設定する
        """
        row_stop = row + row_span
        self._reserve_grid(row_stop, 0)
        for r in range(row, row_stop):
            self._impl.rowconfigure(2 * r + 1, weight=weight)

    def set_column_weights(self, weight: int, column: int, colunm_span: int = 1):
        """
        列方向のウェイトを設定する
        """
        column_stop = column + colunm_span
        self._reserve_grid(0, column_stop)
        for c in range(column, column_stop):
            self._impl.columnconfigure(2 * c + 1, weight=weight)

    def _reserve_grid(self, row_stop: int, column_stop: int):
        """
        グリッドを予約する
        NOTE
            grid に対して必要なパディング設定を行うことを「予約」と呼んでいる。
        """
        # 行方向に予約
        if row_stop > self._reserved_row_stop:
            self._reserved_row_stop = row_stop
            self._impl.rowconfigure(0, minsize=self._pad)
            for i in range(row_stop):
                self._impl.rowconfigure(2 * (i + 1), minsize=self._pad)

        # 列方向に予約
        if column_stop > self._reserved_column_stop:
            self._reserved_column_stop = column_stop
            self._impl.columnconfigure(0, minsize=self._pad)
            for i in range(column_stop):
                self._impl.columnconfigure(2 * (i + 1), minsize=self._pad)
