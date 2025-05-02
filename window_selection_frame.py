from typing import (
    List,
    Optional
)

import win32gui, win32ui, win32con

import tkinter as tk
import customtkinter as ctk
from CTkListbox import CTkListbox

from PIL import Image, ImageTk
from constants import (
    GUI_PADDING
)

def get_visible_window_titles() -> List[str]:
    '''
    現在表示されているウィンドウのタイトルを取得する
    :return: 表示されているウィンドウのタイトルのリスト
    '''
    titles = []
    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                titles.append(title)
    win32gui.EnumWindows(enum_handler, None)
    return titles


def capture_window_image(title_substring) -> Optional[Image.Image]:
    '''
    指定されたタイトルを含むウィンドウの画像をキャプチャする
    :param title_substring: ウィンドウタイトルの部分文字列
    '''
    # ウィンドウのハンドルを取得
    hwnds = []
    def enum_handler(hwnd, result: list):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_substring in title:
                result.append(hwnd)
    win32gui.EnumWindows(enum_handler, hwnds)
    if not hwnds:
        return None

    # 最初のウィンドウを選択
    hwnd = hwnds[0]

    # ウィンドウの画像をキャプチャ
    try:
        # ウィンドウのサイズを取得
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)
        saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        img = Image.frombuffer("RGB", (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, "raw", "BGRX", 0, 1)
    finally:
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)

    return img


# ウィンドウ選択フレーム
class WindowSelectionFrame(ctk.CTkFrame):


    def __init__(self, master, **kwargs):
        '''
        ウィンドウ選択フレームの初期化
        :param master: 親ウィジェット
        :param kwargs: その他のキーワード引数
        '''
        super().__init__(master, **kwargs)

        # レイアウト設定
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1, minsize=320)
        self.columnconfigure(1, weight=1, minsize=320)

        # Windows デスクトップ上に存在するウィンドウ一覧
        self.window_list_box = CTkListbox(self, multiple_selection=False)
        self.window_list_box.grid(row=0, column=0, padx=GUI_PADDING, pady=GUI_PADDING, sticky="nswe")
        self.window_list_box.bind("<<ListboxSelect>>", self.on_select)        

        # ウィンドウ一覧再読み込みボタン
        self.reload_window_list_button = ctk.CTkButton(self, text="リロード", command=self.update_list)
        self.reload_window_list_button.grid(row=1, column=0, padx=GUI_PADDING, pady=GUI_PADDING, sticky="nswe")

        # プレビュー画像表示用ラベル
        self.preview_label = ctk.CTkLabel(self, text="Preview")
        self.preview_label.grid(row=0, column=1, padx=GUI_PADDING, pady=GUI_PADDING, sticky="nswe")

        # プレビュー更新関係
        self.bind('<Configure>', self.on_frame_resize)
        self.original_screen_shot = None

        # 初期リスト更新
        self.update_list()
        self.update_window_preview()


    def on_select(self, event) -> None:
        '''
        リストボックスの選択イベントハンドラ
        :param event: イベントオブジェクト
        :return: None
        '''
        self.update_original_screen_shot()
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


    def update_original_screen_shot(self) -> None:
        '''
        選択されたウィンドウのスクリーンショットを撮影し、その画像で内部状態を更新する。
        :return: None 
        '''
        selection = self.window_list_box.get(self.window_list_box.curselection())
        self.original_screen_shot = capture_window_image(selection)


    def update_window_preview(self) -> None:
        '''
        '''
        # フレーム内の版組みサイズを解決
        frame_width = self.winfo_width()
        frame_height = self.winfo_height()
        right_side_width = frame_width * 3 // 4

        # 描画対象画像を解決
        image = self.original_screen_shot
        if image is None:
            self.preview_label.configure(
                text="Window Preview",
                width=right_side_width,
                height=frame_height
            )
            return

        # プレビュー画像の適切なサイズを解決
        width_base_scale = right_side_width / image.width
        height_base_scale = frame_height / image.height
        actual_scale = min(width_base_scale, height_base_scale)
        if actual_scale < 1.0:
            actual_width = int(image.width * actual_scale)
            actual_height = int(image.height * actual_scale)
        else:
            actual_width = image.width
            actual_height = image.height

        # 画像をリサイズ
        if actual_scale < 1.0:
            image = image.resize(
                (actual_width, actual_height),
                Image.Resampling.LANCZOS
            )

        # 画像をラベルに表示
        tk_image = ImageTk.PhotoImage(image)
        self.preview_label.configure(
            image=tk_image,
            text="",
            width=right_side_width,
            height=frame_height
        )
