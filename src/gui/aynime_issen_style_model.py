from typing import Optional, Generator, List
from enum import Enum

from PIL import Image

from utils.capture_context import (
    CaptureTargetInfo,
    CaptureContext,
    CaptureContextDXCam,
    CaptureContextPyWin32,
)
from utils.pil import crop_to_aspect_ratio


class CaptureMode(Enum):
    """
    キャプチャモードを定義する列挙型
    """

    DXCAM = "dxcam"
    PYWIN32 = "pywin32"


class AspectRatioMode(Enum):
    """
    キャプチャのアスペクト比モードを定義する列挙型
    """

    MODE_RAW = "raw"
    MODE_16_9 = "16:9"
    MODE_4_3 = "4:3"


class AynimeIssenStyleModel:
    """
    えぃにめ一閃流奥義「一閃」のモデル
    """

    def __init__(self) -> None:
        """
        コンストラクタ
        """
        self._capture_context: Optional[CaptureContext] = None
        self._aspect_ratio_mode: Optional[AspectRatioMode] = None
        self._capture_target_info: Optional[CaptureTargetInfo] = None

    def change_capture_mode(self, mode: CaptureMode) -> None:
        """
        キャプチャモードを変更する

        Args:
            mode (CaptureMode): 変更後のキャプチャモード

        Raises:
            ValueError: mode が不正な場合
        """
        # キャプチャコンテキストを再生成する
        # NOTE
        #   先に作っていたインスタンスを確実に削除しておかないと dxcam-cpp が警告を出してくる。
        #   このケースにおいては、既存インスタンスを返すらしい。
        #   なので、一応、事前にキャプチャコンテキストを破棄する。
        if mode == CaptureMode.DXCAM and not isinstance(
            self._capture_context, CaptureContextDXCam
        ):
            if self._capture_context is not None:
                self._capture_context.release()
                del self._capture_context
                self._capture_context = None
            self._capture_context = CaptureContextDXCam()
        elif mode == CaptureMode.PYWIN32 and not isinstance(
            self._capture_context, CaptureContextPyWin32
        ):
            if self._capture_context is not None:
                self._capture_context.release()
                del self._capture_context
                self._capture_context = None
            self._capture_context = CaptureContextPyWin32()
        elif mode not in CaptureMode:
            raise ValueError(f"Unsupported capture mode: {mode}")

    def change_aspect_ratio_mode(self, mode: AspectRatioMode) -> None:
        """
        アスペクト比モードを変更する

        Args:
            mode (AspectRatioMode): アスペクト比モード
        """
        self._aspect_ratio_mode = mode

    def enumerate_capture_targets(self) -> Generator[CaptureTargetInfo, None, None]:
        """
        キャプチャ対象を列挙する

        Raises:
            RuntimeError: コンテキストが未初期化の場合

        Returns:
            _type_: キャプチャ対象のジェネレータ

        Yields:
            Generator[CaptureTargetInfo, None, None]: 合法なキャプチャ対象を順番に返す
        """
        if self._capture_context is None:
            raise RuntimeError("Capture context is not initialized.")
        else:
            return self._capture_context.enumerate_capture_targets()

    def change_capture_target(self, capture_target_info: CaptureTargetInfo) -> None:
        """
        キャプチャ対象を変更する

        Args:
            capture_target_info (CaptureTargetInfo): 変更後のキャプチャ対象
        """
        self._capture_target_info = capture_target_info

    def capture(self) -> Image.Image:
        """
        キャプチャを実行する

        Raises:
            RuntimeError: キャプチャコンテキストが未初期化の場合
            RuntimeError: キャプチャ対象が未設定の場合

        Returns:
            Image.Image: キャプチャ結果の PIL 画像
        """
        reasons = self.capture_not_ready_reasons
        if len(reasons) != 0:
            raise RuntimeError(reasons)
        else:
            capture_image = self._capture_context.capture(self._capture_target_info)
            if self._aspect_ratio_mode == AspectRatioMode.MODE_RAW:
                return capture_image
            elif self._aspect_ratio_mode == AspectRatioMode.MODE_16_9:
                return crop_to_aspect_ratio(capture_image, 16, 9)
            elif self._aspect_ratio_mode == AspectRatioMode.MODE_4_3:
                return crop_to_aspect_ratio(capture_image, 4, 3)
            else:
                raise ValueError(
                    f"Invalid aspect ratio mode({self._aspect_ratio_mode})"
                )

    @property
    def capture_not_ready_reasons(self) -> List[str]:
        """
        キャプチャの準備が整っていない理由を表す文字列（複数）を返す。
        キャプチャの準備が整っていれば、空のリストを返す。

        Returns:
            bool: キャプチャ可能なら True を返す
        """
        reasons = []
        if self._capture_context is None:
            reasons.append(
                "Capture context is not initialized(Tipically, capture mode is not selected)."
            )
        if self._aspect_ratio_mode is None:
            reasons.append("Aspect ratio mode is not selected.")
        if self._capture_target_info is None:
            reasons.append("Capture target info is not selected.")
        return reasons
