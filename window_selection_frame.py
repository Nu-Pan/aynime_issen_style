
from typing import (
    cast
)

import customtkinter as ctk
from CTkListbox import CTkListbox

from PIL import Image, ImageTk

from constants import (
    WIDGET_PADDING
)
from windows_wrapper import (
    get_visible_window_titles,
    capture_window_image,
    isotropic_scale_image_in_rectangle
)
from app_wide_properties import AppWideProperties
from constants import (
    WINDOW_MIN_WIDTH,
    WINDOW_MIN_HEIGHT
)


class WindowSelectionFrame(ctk.CTkFrame):
    '''
    ウィンドウ選択フレームクラス
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

        # レイアウト設定
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1, minsize=WINDOW_MIN_WIDTH//2)
        self.columnconfigure(1, weight=1, minsize=WINDOW_MIN_WIDTH//2)

        # Windows デスクトップ上に存在するウィンドウ一覧
        self.window_list_box = CTkListbox(self, multiple_selection=False)
        self.window_list_box.grid(row=0, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe")
        self.window_list_box.bind("<<ListboxSelect>>", self.on_select)        

        # ウィンドウ一覧再読み込みボタン
        self.reload_window_list_button = ctk.CTkButton(self, text="リロード", command=self.update_list)
        self.reload_window_list_button.grid(row=1, column=0, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe")

        # プレビュー画像表示用ラベル
        self.preview_label = ctk.CTkLabel(self, text="Preview")
        self.preview_label.grid(row=0, column=1, padx=WIDGET_PADDING, pady=WIDGET_PADDING, sticky="nswe")

        # ウィンドウサイズ変更イベントのバインド
        self.bind('<Configure>', self.on_frame_resize)

        # リサイズ前のキャプチャ画像
        self.original_capture_image = None

        # 初期リスト更新
        self.update_list()
        self.update_window_preview()


    def on_select(self, event) -> None:
        '''
        リストボックスの選択イベントハンドラ
        :param event: イベントオブジェクト
        :return: None
        '''
        # 選択されたウィンドウタイトルをアプリケーション全体のプロパティに保存
        selection = self.window_list_box.get(self.window_list_box.curselection())
        self.app_wide_properties.window_title_substring = selection

        # 描画更新
        self.update_original_capture_image()
        self.update_window_preview()


    def on_frame_resize(self, event) -> None:
        '''
        フレームのリサイズイベントハンドラ
        :param event: イベントオブジェクト
        :return: None
        '''
        self.update_window_preview()


    def update_list(self) -> None:
        '''
        ウィンドウリストを更新する
        :return: None
        '''
        # リストボックスをクリアしてから、ウィンドウタイトルを取得して追加
        self.window_list_box.delete(0, ctk.END)
        for title in get_visible_window_titles():
            self.window_list_box.insert(ctk.END, title)


    def update_original_capture_image(self) -> None:
        '''
        選択されたウィンドウのキャプチャを撮影し、その画像で内部状態を更新する。
        :return: None 
        '''
        self.original_capture_image = capture_window_image(
            self.app_wide_properties.window_title_substring
        )


    def update_window_preview(self) -> None:
        '''
        プレビューの表示状態を更新する。
        キャプチャは行わない。
        :return: None
        '''
        # フレーム内の版組みサイズを解決
        frame_width = self.winfo_width()
        frame_height = self.winfo_height()
        right_side_width = frame_width * 3 // 4

        # 描画対象画像を解決
        image = self.original_capture_image
        if image is None:
            self.preview_label.configure(
                text="Window Preview",
                width=right_side_width,
                height=frame_height
            )
            return

        # 画像をリサイズ
        image = isotropic_scale_image_in_rectangle(
            image,
            right_side_width,
            frame_height
        )

        # 画像をラベルに表示
        tk_image = ImageTk.PhotoImage(image)
        self.preview_label.configure(
            image=tk_image,
            text="",
            width=right_side_width,
            height=frame_height
        )
