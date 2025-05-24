# std
from typing import cast

# Tk/CTk
from tkinter import Event
import customtkinter as ctk
from CTkListbox import CTkListbox

# utils
from utils.capture_context import CaptureTargetInfo
from utils.constants import WIDGET_PADDING, WINDOW_MIN_WIDTH, DEFAULT_FONT_NAME

# gui
from gui.widgets.still_frame import StillLabel

# local
from aynime_issen_style_model import CaptureMode, AynimeIssenStyleModel


class WindowSelectionFrame(ctk.CTkFrame):
    """
    ウィンドウ選択フレームクラス
    """

    def __init__(
        self, master: ctk.CTkBaseClass, model: AynimeIssenStyleModel, **kwargs
    ):
        """
        コンストラクタ

        Args:
            master (_type_): 親ウィジェット
            model (AynimeIssenStyleModel): モデル
        """
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

        # 参照を保存
        self.model = model

        # レイアウト設定
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=0, minsize=self.winfo_width() // 2)
        self.columnconfigure(1, weight=1, minsize=self.winfo_width() // 2)

        # 画面左側のフレーム
        self.west_frame = ctk.CTkFrame(self)
        self.west_frame.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.west_frame.configure(width=WINDOW_MIN_WIDTH // 2)
        self.west_frame.rowconfigure(0, weight=0)
        self.west_frame.rowconfigure(1, weight=1)
        self.west_frame.rowconfigure(2, weight=0)
        self.west_frame.columnconfigure(0, weight=1)

        # キャプチャモード選択フレーム
        self.capture_mode_frame = ctk.CTkFrame(self.west_frame)
        self.capture_mode_frame.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nwe"
        )
        self.capture_mode_frame.columnconfigure(0, weight=1)
        self.capture_mode_frame.columnconfigure(1, weight=1)

        # キャプチャモード選択ラジオボタン変数
        self.capture_mode_var = ctk.StringVar(value=CaptureMode.DXCAM.value)

        # キャプチャモード選択ラジオボタン（DXCAM）
        self.capture_mode_dxcam_radio = ctk.CTkRadioButton(
            self.capture_mode_frame,
            text=CaptureMode.DXCAM.name,
            variable=self.capture_mode_var,
            value=CaptureMode.DXCAM.value,
            command=self.on_capture_mode_radio_change,
            width=0,
        )
        self.capture_mode_dxcam_radio.grid(
            row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # キャプチャモード選択ラジオボタン（PYWIN32）
        self.capture_mode_pywin32_radio = ctk.CTkRadioButton(
            self.capture_mode_frame,
            text=CaptureMode.PYWIN32.name,
            variable=self.capture_mode_var,
            value=CaptureMode.PYWIN32.value,
            command=self.on_capture_mode_radio_change,
            width=0,
        )
        self.capture_mode_pywin32_radio.grid(
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # キャプチャ対象リストボックス
        self.capture_target_list_box = CTkListbox(
            self.west_frame, multiple_selection=False
        )
        self.capture_target_list_box.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.capture_target_list_box.bind(
            "<<ListboxSelect>>", self.on_capture_target_select
        )

        # ウィンドウ一覧再読み込みボタン
        self.reload_capture_target_list_button = ctk.CTkButton(
            self.west_frame,
            text="リロード",
            command=self.update_list,
            font=default_font,
        )
        self.reload_capture_target_list_button.grid(
            row=2, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )

        # 画面右側のフレーム
        self.east_frame = ctk.CTkFrame(self)
        self.east_frame.grid(
            row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.east_frame.rowconfigure(0, weight=0)
        self.east_frame.rowconfigure(1, weight=1)
        self.east_frame.columnconfigure(0, weight=1)

        # プレビュー画像表示用ラベル
        self.capture_target_preview_label = StillLabel(self.east_frame)
        self.capture_target_preview_label.grid(
            row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe"
        )
        self.capture_target_preview_label.set_contents(text="Preview")

        # リサイズ前のキャプチャ画像
        self.original_capture_image = None

        # 初回キャプチャターゲットリスト更新
        self.update_list()
        self.clear_capture_target_preview()

        # UI 上の設定をモデルに反映
        self.on_capture_mode_radio_change()

    def on_capture_mode_radio_change(self) -> None:
        """
        キャプチャモードの選択イベントハンドラ
        """
        # モデルに変更を反映
        self.model.change_capture_mode(CaptureMode(self.capture_mode_var.get()))
        self.update_list()

        # プレビューをクリア
        self.clear_capture_target_preview()

    def on_capture_target_select(self, event: Event) -> None:
        """
        リストボックスの選択イベントハンドラ

        Args:
            event (_type_): イベントオブジェクト
        """
        # キャプチャ対象の変更をモデルに反映
        selection = cast(
            CaptureTargetInfo,
            self.capture_target_list_box.get(
                self.capture_target_list_box.curselection()
            ),
        )
        self.model.change_capture_target(selection)

        # 描画更新
        self.update_original_capture_image()
        self.update_capture_target_preview()

    def update_list(self) -> None:
        """
        ウィンドウリストを更新する
        """
        # リストボックスをクリアしてから、ウィンドウタイトルを取得して追加
        try:
            self.reload_capture_target_list_button.configure(state=ctk.DISABLED)
            self.capture_target_list_box.delete("all")
            for capture_target_info in self.model.enumerate_capture_targets():
                self.capture_target_list_box.insert(ctk.END, capture_target_info, False)
            self.capture_target_list_box.update()
        finally:
            self.reload_capture_target_list_button.configure(state=ctk.NORMAL)

    def update_original_capture_image(self) -> None:
        """
        選択されたウィンドウのキャプチャを撮影し、その画像で内部状態を更新する。
        """
        try:
            self.original_capture_image = self.model.capture()
        except Exception as e:
            self.original_capture_image = None

    def clear_capture_target_preview(self) -> None:
        """
        プレビューの表示状態をクリアする。
        """
        self.original_capture_image = None
        self.capture_target_preview_label.set_contents(text="Capture Target Preview")

    def update_capture_target_preview(self) -> None:
        """
        プレビューの表示状態を更新する。
        キャプチャは行わない。
        """
        # 描画対象画像を解決
        image = self.original_capture_image
        if image is None:
            self.clear_capture_target_preview()
            return

        # 画像を表示
        self.capture_target_preview_label.set_contents(image=image)
