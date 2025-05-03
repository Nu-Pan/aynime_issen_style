
import threading

import customtkinter as ctk
from PIL import ImageTk
import keyboard


from aynime_issen_style_model import AynimeIssenStyleModel
from constants import (
    WIDGET_PADDING,
    DEFAULT_FONT_NAME
)
from pil_wrapper import isotropic_scale_image_in_rectangle
from windows_wrapper import image_to_clipboard


class CaptureFrame(ctk.CTkFrame):
    '''
    キャプチャ操作を行うフレーム
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

        # プレビューラベル兼キャプチャボタン
        self.preview_label = ctk.CTkLabel(
            self,
            text='クリック or Ctrl+Alt+P でキャプチャ',
            font=default_font
        )
        self.preview_label.pack(fill="both", expand=True, padx=WIDGET_PADDING, pady=WIDGET_PADDING)
        self.preview_label.bind("<Button-1>", self.on_capture_click)

        # ウィンドウサイズ変更イベントのバインド
        self.bind('<Configure>', self.on_frame_resize)

        # リサイズ前のキャプチャ画像
        self.original_capture_image = None

        # ホットキー用のバックグラウンドスレッドを開始
        # NOTE
        #   ホットキーのリスニングはメインスレッドで行うと、GUIがフリーズしてしまうので、バックグラウンドスレッドを使用する。
        #   デーモンスレッドにすることで、メインスレッドが終了したときに自動的に終了する。
        threading.Thread(target=self.listen_hotkey, daemon=True).start()


    def on_capture_click(self, event) -> None:
        '''
        キャプチャボタンがクリックされたときの処理
        :param event: イベントオブジェクト
        '''
        # まずはキャプチャ＆プレビュー
        self.update_original_capture_image()
        self.update_preview_label()

        # キャプチャ画像がない場合は何もしない
        if self.original_capture_image is None:
            self.preview_label.configure(text="キャプチャ失敗")
            return

        # 結果をクリップボードに転送
        image_to_clipboard(self.original_capture_image)

        # クリップボード転送完了通知
        self.notify_status('一閃\nクリップボード転送完了')


    def on_frame_resize(self, event) -> None:
        '''
        フレームのリサイズイベントハンドラ
        :param event: イベントオブジェクト
        :return: None
        '''
        self.update_preview_label()


    def listen_hotkey(self) -> None:
        '''
        ホットキーをリスニングする。
        :return: None
        '''
        keyboard.add_hotkey('ctrl+alt+p', lambda: self.on_capture_click(None))
        keyboard.wait()


    def update_original_capture_image(self) -> None:
        '''
        選択されたウィンドウのキャプチャを撮影し、その画像で内部状態を更新する。
        :return: None 
        '''
        try:
            self.original_capture_image = self.model.capture()
        except Exception as e:
            self.original_capture_image = None
            self.preview_label.configure(text=f"キャプチャ失敗\n{e}")


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


    def notify_status(
        self,
        message: str,
        duration_ms: int = 2000
    ) -> None:
        '''
        duration_ms の間、隅っこにメッセージを通知する。
        :param message: メッセージ文字列
        :param duration_ms: 表示時間（ミリ秒）
        :return: None
        '''
        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

        # 通知ラベルを生成
        # NOTE
        #   ラベルの四隅の外側はテーマ色でフィルされてしまうので、角丸のないラベルを使用する(corner_radius=0)。
        status_label = ctk.CTkLabel(
            self,
            text=message,
            fg_color='#3a8d3f',
            text_color="white",
            corner_radius=0,
            font=default_font
        )
        status_label.place(
            relx=0.5,
            rely=0.5,
            anchor='center'
        )
        status_label.configure(
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING
        )

        # 通知ラベルは一定時間後に自動破棄
        self.after(duration_ms, status_label.destroy)
