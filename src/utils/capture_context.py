from typing import Optional, Generator, List, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass
import time

import win32gui, win32ui, win32con
from PIL import Image
import dxcam_cpp as dxcam

from utils.windows import enumerate_dxgi_outputs


@dataclass
class WindowIdentifier:
    """
    ウィンドウ識別子を保持するクラス
    """

    hwnd: int


@dataclass
class MonitorIdentifier:
    """
    モニター識別子を保持するクラス
    """

    adapter_index: int  # グラボのインデックス
    output_index: int  # モニターのインデックス


@dataclass
class CaptureTargetInfo:
    """
    キャプチャ対象の情報を保持するクラス
    """

    id: Union[WindowIdentifier, MonitorIdentifier]
    name: str

    def __str__(self) -> str:
        """
        キャプチャ対象の情報を文字列として返す

        Returns:
            str: キャプチャ対象の情報の文字列
        """
        return self.name


class CaptureContext(ABC):
    """
    キャプチャコンテキスト純粋仮想基底クラス
    """

    @abstractmethod
    def enumerate_capture_targets(self) -> Generator[CaptureTargetInfo, None, None]:
        """
        キャプチャ対象を列挙する

        Yields:
            Generator[CaptureTargetInfo, None, None]: キャプチャ対象のジェネレータ
                合法なキャプチャ対象を順番に返す
        """
        ...

    @abstractmethod
    def capture(self, capture_target_info: CaptureTargetInfo) -> Image.Image:
        """
        キャプチャを実行する

        Args:
            capture_target_info (CaptureTargetInfo): キャプチャ対象の情報

        Returns:
            Image.Image: キャプチャした画像
        """
        ...

    @abstractmethod
    def release(self) -> None:
        """
        内部リソースを開放する。
        dxcam-cpp のダメ挙動に対処するために必要なダメ関数。
        インスタンスを del する直前に呼び出すことで、確実に内部リソースを開放できる。
        """
        ...


class CaptureContextDXCam(CaptureContext):
    """
    DXCamキャプチャコンテキスト
    """

    def __init__(self) -> None:
        """
        コンストラクタ
        """
        super().__init__()
        self._dxcamera = None
        self._dxcamera_adaper_idx = None
        self._dxcamera_output_idx = None
        self._latest_np_image = None

    def enumerate_capture_targets(self) -> Generator[CaptureTargetInfo, None, None]:
        # 合法なモニターを順番に返す
        for dxgi_output_info in enumerate_dxgi_outputs():
            yield CaptureTargetInfo(
                MonitorIdentifier(
                    dxgi_output_info.adapter_index, dxgi_output_info.output_index
                ),
                str(dxgi_output_info),
            )

    def capture(self, capture_target_info: CaptureTargetInfo) -> Image.Image:
        # 引数の型チェック
        if not isinstance(capture_target_info.id, MonitorIdentifier):
            raise TypeError("Invalid capture target info type.")

        # キャプチャ対象が以前と違う場合はカメラを再生成
        if (
            self._dxcamera is None
            or self._dxcamera_adaper_idx != capture_target_info.id.adapter_index
            or self._dxcamera_output_idx != capture_target_info.id.output_index
        ):
            # カメラを生成
            # NOTE
            #   先に作っていたインスタンスを確実に削除しておかないと dxcam-cpp が警告を出してくる。
            #   このケースにおいては、既存インスタンスを返すらしい。
            #   なので、一応 release を呼んでから create する。
            self.release()
            self._dxcamera = dxcam.create(
                device_idx=capture_target_info.id.adapter_index,
                output_idx=capture_target_info.id.output_index,
            )
            if not isinstance(self._dxcamera, dxcam.DXCamera):
                raise ValueError("Invalid return value of dxcam.create.")

            # メンバ更新
            self._dxcamera_adaper_idx = capture_target_info.id.adapter_index
            self._dxcamera_output_idx = capture_target_info.id.output_index
            self._latest_np_image = None

            # 初回 Grab
            # NOTE
            #   dxcam-cpp の挙動として、初回 grab は黒画面が返ってくる。
            #   それを読み捨てるために、一度 grab を呼び出す。
            #   また、呼び出し間隔が短すぎると更新なし
            np_image = self._dxcamera.grab()
            if np_image is None:
                raise ValueError("Invalid return value of DXCamera.grab.")
            else:
                self._latest_np_image = np_image
                time.sleep(0.1)

        # キャプチャ
        # NOTE
        #   grab が None が返す＝画面に変化なしなので、最後のキャプチャを使う。
        np_image = self._dxcamera.grab()
        if np_image is None:
            np_image = self._latest_np_image
        else:
            self._latest_np_image = np_image

        # 正常終了
        return Image.fromarray(np_image)

    def release(self) -> None:
        if self._dxcamera is not None:
            self._dxcamera.release()
            del self._dxcamera
            self._dxcamera = None


class CaptureContextPyWin32(CaptureContext):
    """
    PyWin32キャプチャコンテキスト
    """

    def __init__(self) -> None:
        """
        コンストラクタ
        """
        super().__init__()

    def enumerate_capture_targets(self) -> Generator[CaptureTargetInfo, None, None]:
        # 全てのウィンドウハンドルを列挙
        hwnds: List[int] = []

        def enum_handler(hwnd: int, _):
            hwnds.append(hwnd)

        win32gui.EnumWindows(enum_handler, None)

        # 合法なウィンドウを順番に返す
        for hwnd in hwnds:
            # 不可視ウィンドウはスキップ
            if not win32gui.IsWindowVisible(hwnd):
                continue

            # タイトルが空のウィンドウはスキップ
            title = win32gui.GetWindowText(hwnd).strip()
            if not title:
                continue

            # ウィンドウ情報を生成して返す
            yield CaptureTargetInfo(WindowIdentifier(hwnd), title)

    def capture(self, capture_target_info: CaptureTargetInfo) -> Image.Image:
        # ウィンドウハンドルを解決
        if isinstance(capture_target_info.id, WindowIdentifier):
            hwnd = capture_target_info.id.hwnd
        else:
            raise TypeError("Invalid capture target info type.")

        # ウィンドウの画像をキャプチャ
        try:
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
            pil_image = Image.frombuffer(
                "RGB",
                (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
                bmpstr,
                "raw",
                "BGRX",
                0,
                1,
            )
        finally:
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)

        # 正常終了
        return pil_image

    def release(self) -> None:
        # NOTE pywin32 の場合は何もしなくて良い
        pass
