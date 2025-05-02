
import customtkinter as ctk

from PIL import Image, ImageTk

from app_wide_properties import AppWideProperties
from constants import (
    WIDGET_PADDING,
    WINDOW_MIN_WIDTH
)
from windows_wrapper import (
    capture_window_image,
    isotropic_scale_image_in_rectangle,
    image_to_clipboard
)

class CaptureFrame(ctk.CTkFrame):
    '''
    キャプチャ操作を行うフレームクラス
    '''


    def __init__(
        self,
        master,
        app_wide_properties: AppWideProperties,
        **kwargs
    ):
        '''
        コンストラクタ
        :param master: 親ウィジェット
        :param kwargs: その他のキーワード引数
        '''
        super().__init__(master, **kwargs)

        # 参照を保存
        self.app_wide_properties = app_wide_properties

        # プレビューラベル兼キャプチャボタン
        self.preview_label = ctk.CTkLabel(self, text='クリックしてキャプチャ')
        self.preview_label.pack(fill="both", expand=True, padx=WIDGET_PADDING, pady=WIDGET_PADDING)
        self.preview_label.bind("<Button-1>", self.on_capture_click)

        # ウィンドウサイズ変更イベントのバインド
        self.bind('<Configure>', self.on_frame_resize)

        # リサイズ前のキャプチャ画像
        self.original_capture_image = None


    def on_capture_click(self, event) -> None:
        '''
        キャプチャボタンがクリックされたときの処理
        :param event: イベントオブジェクト
        '''
        # まずはキャプチャ＆プレビュー
        self.update_original_capture_image()
        self.update_preview_label()

        # 結果をクリップボードに転送
        image_to_clipboard(self.original_capture_image)


    def on_frame_resize(self, event) -> None:
        '''
        フレームのリサイズイベントハンドラ
        :param event: イベントオブジェクト
        :return: None
        '''
        self.update_preview_label()


    def update_original_capture_image(self) -> None:
        '''
        選択されたウィンドウのキャプチャを撮影し、その画像で内部状態を更新する。
        :return: None 
        '''
        self.original_capture_image = capture_window_image(
            self.app_wide_properties.window_title_substring
        )
        if self.original_capture_image is None:
            self.tk_image = None
            self.preview_label.configure(text="キャプチャ失敗")
            return


    def update_preview_label(self) -> None:
        '''
        プレビューの表示状態を更新する。
        キャプチャは行わない。
        :return: None
        '''
        # キャプチャ画像がない場合は何もしない
        if self.original_capture_image is None:
            return

        # 画像をリサイズ
        pil_image = isotropic_scale_image_in_rectangle(
            self.original_capture_image,
            self.preview_label.winfo_width(),
            self.preview_label.winfo_height()
        )

        # 画像をラベルに表示
        tk_image = ImageTk.PhotoImage(pil_image)
        self.preview_label.configure(
            image=tk_image,
            text=""
        )