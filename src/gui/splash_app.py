# std
from typing import cast

# PIL
from PIL import Image

# Tk/CTk
import customtkinter as ctk
from time import perf_counter
from typing import Callable

# utils
from utils.constants import (
    APP_NAME_JP,
    DEFAULT_FONT_FAMILY,
    NUMERIC_FONT_FAMILY,
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT,
)
from utils.pyinstaller import resource_path
from utils.ctk import place_window_to_display_center

# gui
from gui.widgets.ais_frame import AISFrame


# プログレスラベルで表示する文字アニメーションの定義
_PROGRESS_SEQUENCE = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class SplashWindow(ctk.CTkToplevel):
    """
    アプリ起動時スプラッシュウィンドウ
    """

    def __init__(self, master: ctk.CTk, completion_query_handler: Callable[[], bool]):
        super().__init__(master)

        # フォントロード
        title_font = ctk.CTkFont(DEFAULT_FONT_FAMILY, 24)
        progress_font = ctk.CTkFont(DEFAULT_FONT_FAMILY, 48)

        # ウィンドウ見た目の基本設定
        self.transient(master)  # 親ウィンドウの子として扱う
        self.attributes("-topmost", True)  # 最前面
        self.overrideredirect(True)  # 枠無し

        # ウィンドウをディスプレイ中央に配置
        place_window_to_display_center(self, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # ルートフレーム
        self._root_frame = AISFrame(
            self, corner_radius=0, border_width=0, fg_color=self._fg_color
        )
        self._root_frame.pack(fill="both", expand=True)
        self._root_frame.ais.columnconfigure(0, weight=1)

        # アイコン＆タイトル表示用フレーム
        self._identity_frame = AISFrame(
            self._root_frame, corner_radius=0, border_width=0, fg_color=self._fg_color
        )
        self._root_frame.ais.grid_child(self._identity_frame, 0, 0, sticky="")
        self._root_frame.ais.rowconfigure(0, weight=1)
        self._identity_frame.ais.columnconfigure(0, weight=1)

        # アイコンを表示
        self._logo_image = ctk.CTkImage(
            light_image=Image.open(resource_path("app.ico")),
            size=(132, 134),
        )
        self._logo_label = ctk.CTkLabel(
            self._identity_frame, image=self._logo_image, text=""
        )
        self._identity_frame.ais.grid_child(self._logo_label, 0, 0)
        self._identity_frame.ais.rowconfigure(0, weight=1)

        # アプリ名を表示
        self._title_label = ctk.CTkLabel(
            self._identity_frame, text=APP_NAME_JP, font=title_font
        )
        self._identity_frame.ais.grid_child(self._title_label, 1, 0)
        self._identity_frame.ais.rowconfigure(1, weight=1)

        # プログレスっぽいのを表示
        # NOTE
        #   アニメーションすることで、何かが動いていることをユーザーに伝えるのが目的。
        #   全体に対する進捗状況の通知は諦める。
        self._progress_label = ctk.CTkLabel(
            self._root_frame, text="*", font=progress_font
        )
        self._root_frame.ais.grid_child(self._progress_label, 1, 0)
        self._root_frame.ais.rowconfigure(1, weight=1)

        # 完了待機ポーリングをスタート
        self._progress_index = 0
        self._completion_query_handler = completion_query_handler
        self._start_in_sec = perf_counter()
        self._after_id = None
        self._schedule_next_completion_poll()

    def _schedule_next_completion_poll(self) -> None:
        """
        完了待機ポーリングをスケジュールする
        """
        self._after_id = self.after(50, self._polling_completion)

    def _polling_completion(self) -> None:
        """
        完了待機ポーリング
        このスプラッシュウィンドウを作った親のバックグラウンドジョブ完了を待機する
        """
        # プログレスの表示文字を１つ進める
        self._progress_index += 1
        if self._progress_index >= len(_PROGRESS_SEQUENCE):
            self._progress_index = 0

        # プログレスラベルに更新を反映
        self._progress_label.configure(text=_PROGRESS_SEQUENCE[self._progress_index])

        # 待機完了
        # NOTE
        #   親のバックグラウンドジョブが完了だけでなく、固定の２秒待機も行う。
        #   スプラッシュウィンドウ表示が短すぎると、間違いなくユーザーが不審がるので。
        elapsed = perf_counter() - self._start_in_sec
        if self._completion_query_handler() and elapsed > 2.0:
            # 本体を表示
            root = cast(ctk.CTk, self.master)
            try:
                root.deiconify()  # main 側で withdraw している前提
            except Exception:
                pass

            # 自分自身を破棄
            self.destroy()

            # 次は不要なのでこのまま終了
            return

        # 次のポーリング
        self._schedule_next_completion_poll()

    def destroy(self) -> None:
        """
        自分自身を安全に破棄する
        """
        # 保留中の after をキャンセル
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

        # 通常の destroy へ
        super().destroy()
