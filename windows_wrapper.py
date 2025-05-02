
from typing import (
    List,
    Optional
)
import io

import win32gui, win32ui, win32con, win32clipboard

from PIL import Image


def get_visible_window_titles() -> List[str]:
    '''
    現在表示されているウィンドウ全てのタイトルをリストで取得する
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


def capture_window_image(title_substring: str) -> Optional[Image.Image]:
    '''
    指定されたタイトルを含むウィンドウの画像をキャプチャする
    :param title_substring: ウィンドウタイトルの部分文字列
    '''
    # ウィンドウのハンドルを取得
    hwnds: List[int] = []
    def enum_handler(hwnd: int, result: list):
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


def isotropic_scale_image_in_rectangle(
    image: Image.Image,
    rectangle_width: int,
    rectangle_height: int
) -> Image.Image:
    '''
    画像を指定された矩形に収まるように等比縮小する
    :param image: PILのImageオブジェクト
    :param rectangle_width: 矩形の幅
    :param rectangle_height: 矩形の高さ
    :return: 矩形に収まるように縮小された画像
    '''
    # 矩形のアスペクト比を計算
    rectangle_aspect_ratio = rectangle_width / rectangle_height

    # 画像のアスペクト比を計算
    image_aspect_ratio = image.width / image.height

    # 縮小率を計算
    if image_aspect_ratio > rectangle_aspect_ratio:
        scale = rectangle_width / image.width
    else:
        scale = rectangle_height / image.height

    # 画像を縮小
    new_size = (int(image.width * scale), int(image.height * scale))
    return image.resize(new_size, Image.Resampling.BILINEAR)


def image_to_clipboard(image: Image.Image) -> None:
    '''
    画像をクリップボードにコピーする
    :param image: PILのImageオブジェクト
    :return: None
    '''
    # 画像をRGBモードに変換
    image = image.convert("RGB")
    
    # 画像をクリップボードにコピー
    with io.BytesIO() as bmp_io:
        image.save(bmp_io, format="BMP")
        bmp_data = bmp_io.getvalue()

    # BMPヘッダを除去
    data = bmp_data[14:]

    # クリップボードに CF_DIB 形式でデータをセット
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_DIB, data)
    win32clipboard.CloseClipboard()
