
from typing import (
    cast
)
import warnings

import customtkinter as ctk
from CTkListbox import CTkListbox

from PIL import ImageTk

from utils.pil_wrapper import isotropic_scale_image_in_rectangle
from utils.capture_context import (
    CaptureTargetInfo
)
from aynime_issen_style_model import (
    CaptureMode,
    AynimeIssenStyleModel
)
from utils.constants import (
    WIDGET_PADDING,
    WINDOW_MIN_WIDTH,
    DEFAULT_FONT_NAME
)


class WindowSelectionFrame(ctk.CTkFrame):
    '''
    ウィンドウ選択フレームクラス
    '''


    def __init__(
        self,
        master,
        model: AynimeIssenStyleModel,
        **kwargs
    ):
        '''
        コンストラクタ
        :param master: 親ウィジェット
        :param kwargs: その他のキーワード引数
        '''
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

        # 参照を保存
        self.model = model

        # レイアウト設定
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=0, minsize=self.winfo_width()//2)
        self.columnconfigure(1, weight=1, minsize=self.winfo_width()//2)

        # 画面左側のフレーム
        self.west_frame = ctk.CTkFrame(self)
        self.west_frame.grid(
            row=0,
            column=0,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe"
        )
        self.west_frame.configure(
            width=WINDOW_MIN_WIDTH//2
        )
        self.west_frame.rowconfigure(0, weight=0)
        self.west_frame.rowconfigure(1, weight=1)
        self.west_frame.rowconfigure(2, weight=0)
        self.west_frame.columnconfigure(0, weight=1)

        # モード選択フレーム
        self.capture_mode_frame = ctk.CTkFrame(self.west_frame)
        self.capture_mode_frame.grid(
            row=0,
            column=0,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nwe"
        )
        self.capture_mode_frame.columnconfigure(0, weight=1)
        self.capture_mode_frame.columnconfigure(1, weight=1)

        # モード選択ラジオボタンの排他選択用変数
        self.capture_mode_var = ctk.StringVar(value=CaptureMode.DXCAM.value)

        # モード選択ラジオボタン（DXCAM）
        self.capture_mode_dxcam_radio = ctk.CTkRadioButton(
            self.capture_mode_frame,
            text=CaptureMode.DXCAM.name,
            variable=self.capture_mode_var,
            value=CaptureMode.DXCAM.value,
            command=self.on_capture_mode_radio_change
        )
        self.capture_mode_dxcam_radio.grid(
            row=0,
            column=0,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING
        )

        # モード選択ラジオボタン（PYWIN32）
        self.capture_mode_pywin32_radio = ctk.CTkRadioButton(
            self.capture_mode_frame,
            text=CaptureMode.PYWIN32.name,
            variable=self.capture_mode_var,
            value=CaptureMode.PYWIN32.value,
            command=self.on_capture_mode_radio_change
        )
        self.capture_mode_pywin32_radio.grid(
            row=0,
            column=1,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING
        )

        # キャプチャ対象リストボックス
        self.capture_target_list_box = CTkListbox(
            self.west_frame,
            multiple_selection=False
        )
        self.capture_target_list_box.grid(
            row=1,
            column=0,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe"
        )
        self.capture_target_list_box.bind("<<ListboxSelect>>", self.on_capture_target_select)        

        # ウィンドウ一覧再読み込みボタン
        self.reload_capture_target_list_button = ctk.CTkButton(
            self.west_frame,
            text="リロード",
            command=self.update_list,
            font=default_font
        )
        self.reload_capture_target_list_button.grid(
            row=2,
            column=0,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe"
        )

        # 画面右側のフレーム
        self.east_frame = ctk.CTkFrame(self)
        self.east_frame.grid(
            row=0,
            column=1,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING,
            sticky="nswe"
        )

        # プレビュー画像表示用ラベル
        self.capture_target_preview_label = ctk.CTkLabel(
            self.east_frame,
            text="Preview",
            font=default_font
        )
        self.capture_target_preview_label.pack(
            fill='both',
            expand=True,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING
        )

        # ウィンドウサイズ変更イベントのバインド
        self.capture_target_preview_label.bind('<Configure>', self.on_capture_target_preview_resize)

        # リサイズ前のキャプチャ画像
        self.original_capture_image = None

        # 初期リスト更新
        self.update_list()
        self.clear_capture_target_preview()


    def on_capture_mode_radio_change(self) -> None:
        '''
        キャプチャモードの選択イベントハンドラ
        :return: None
        '''
        self.model.change_capture_mode(CaptureMode(self.capture_mode_var.get()))
        self.update_list()
        self.clear_capture_target_preview()


    def on_capture_target_select(self, event) -> None:
        '''
        リストボックスの選択イベントハンドラ
        :param event: イベントオブジェクト
        :return: None
        '''
        # キャプチャ対象の変更をモデルに反映
        selection = cast(
            CaptureTargetInfo,
            self.capture_target_list_box.get(self.capture_target_list_box.curselection())
        )
        self.model.change_capture_target(selection)

        # 描画更新
        self.update_original_capture_image()
        self.update_capture_target_preview()


    def on_capture_target_preview_resize(self, event) -> None:
        '''
        右側フレームのリサイズイベントハンドラ
        :param event: イベントオブジェクト
        :return: None
        '''
        self.update_capture_target_preview()


    def update_list(self) -> None:
        '''
        ウィンドウリストを更新する
        :return: None
        '''
        # リストボックスをクリアしてから、ウィンドウタイトルを取得して追加
        try:
            self.reload_capture_target_list_button.configure(state=ctk.DISABLED)
            self.capture_target_list_box.delete('all')
            for capture_target_info in self.model.enumerate_capture_targets():
                self.capture_target_list_box.insert(
                    ctk.END,
                    capture_target_info,
                    False
                )
            self.capture_target_list_box.update()
        finally:
            self.reload_capture_target_list_button.configure(state=ctk.NORMAL)


    def update_original_capture_image(self) -> None:
        '''
        選択されたウィンドウのキャプチャを撮影し、その画像で内部状態を更新する。
        :return: None 
        '''
        self.original_capture_image = self.model.capture()
        if self.original_capture_image is None:
            self.capture_target_preview_label.configure(text="キャプチャ失敗")


    def clear_capture_target_preview(self) -> None:
        '''
        プレビューの表示状態をクリアする。
        :return: None
        '''
        self.original_capture_image = None
        with warnings.catch_warnings():
            warnings.filterwarnings(
                'ignore',
                message='CTkLabel Warning: Given image is not CTkImage',
                category=UserWarning
            )
            self.capture_target_preview_label.configure(
                image='',
                text='Capture Target Preview'
            )


    def update_capture_target_preview(self) -> None:
        '''
        プレビューの表示状態を更新する。
        キャプチャは行わない。
        :return: None
        '''
        # 描画対象画像を解決
        image = self.original_capture_image
        if image is None:
            self.clear_capture_target_preview()
            return

        # 画像をリサイズ
        image = isotropic_scale_image_in_rectangle(
            image,
            self.capture_target_preview_label.winfo_width() - 2 * WIDGET_PADDING,
            self.capture_target_preview_label.winfo_height() - 2 * WIDGET_PADDING
        )

        # 画像をラベルに表示
        tk_image = ImageTk.PhotoImage(image)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                'ignore',
                message='CTkLabel Warning: Given image is not CTkImage',
                category=UserWarning
            )
            self.capture_target_preview_label.configure(
                image=tk_image,
                text=''
            )
