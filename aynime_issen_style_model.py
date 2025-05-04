
from typing import (
    Optional,
    Generator
)
from enum import Enum

from PIL import Image

from capture_context import (
    CaptureTargetInfo,
    CaptureContext,
    CaptureContextDXCam,
    CaptureContextPyWin32
)


class CaptureMode(Enum):
    '''
    キャプチャモードを定義する列挙型
    '''
    DXCAM = 'dxcam'
    PYWIN32 = 'pywin32'


class AynimeIssenStyleModel:
    '''
    えぃにめ一閃流奥義のモデル
    '''


    def __init__(self) -> None:
        '''
        コンストラクタ
        '''
        self._capture_context: Optional[CaptureContext] = None
        self._capture_target_info: Optional[CaptureTargetInfo] = None


    def change_capture_mode(self, mode: CaptureMode) -> None:
        '''
        キャプチャモードを変更する
        :param mode: キャプチャモード
        '''
        # キャプチャコンテキストを再生成する
        # NOTE
        #   先に作っていたインスタンスを確実に削除しておかないと dxcam-cpp が警告を出してくる。
        #   このケースにおいては、既存インスタンスを返すらしい。
        #   なので、一応、事前にキャプチャコンテキストを破棄する。
        if mode == CaptureMode.DXCAM and not isinstance(self._capture_context, CaptureContextDXCam):
            if self._capture_context is not None:
                self._capture_context.release()
                del self._capture_context
                self._capture_context = None
            self._capture_context = CaptureContextDXCam()
        elif mode == CaptureMode.PYWIN32 and not isinstance(self._capture_context, CaptureContextPyWin32):
            if self._capture_context is not None:
                self._capture_context.release()
                del self._capture_context
                self._capture_context = None
            self._capture_context = CaptureContextPyWin32()
        else:
            raise ValueError(f"Unsupported capture mode: {mode}")


    def enumerate_capture_targets(self) -> Generator[Generator, None, None]:
        '''
        キャプチャ対象を列挙する
        :return: キャプチャ対象のジェネレータ
        '''
        if self._capture_context is None:
            raise RuntimeError("Capture context is not initialized.")
        else:
            return self._capture_context.enumerate_capture_targets()


    def change_capture_target(self, capture_target_info: CaptureTargetInfo) -> None:
        '''
        キャプチャ対象を変更する
        :param capture_target_info: キャプチャ対象の情報
        '''
        self._capture_target_info = capture_target_info


    def capture(self) -> Image.Image:
        '''
        キャプチャを実行する
        :return: キャプチャした画像
        '''
        if self._capture_context is None:
            raise RuntimeError("Capture context is not initialized.")
        elif self._capture_target_info is None:
            raise RuntimeError("Capture target info is not set.")
        else:
            return self._capture_context.capture(self._capture_target_info)
