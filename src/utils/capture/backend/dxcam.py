# std
from time import time, sleep

# win32
import win32con, win32api
from PIL import Image

# dxcam
import dxcam_cpp as dxcam

# dxgi_probe
import dxgi_probe

# utils
from utils.image import AISImage
from utils.capture.backend import *
from utils.capture.target import MonitorIdentifier


def hoge_func():
    pass


class CaptureBackendDxcam(CaptureBackend):
    """
    dxcam バックエンド
    """

    def __init__(self):
        super().__init__()
        self._monitor_id = None
        self._dxcamera = None
        self._last_capture_time = time()
        self._latest_ais_image = None

    def capture(self) -> AISImage:
        # 対象ウィンドウが未指定ならエラー
        if self.capture_window is None:
            raise ValueError("Invalid Window not set")

        # キャプチャ対象モニターを解決
        # NOTE
        #   動画キャプチャ向けの連続呼び出し時に毎回再チェックが走ると重そうなので、
        #   前回キャプチャから時間が経ってる場合だけ再チェックを行う。
        MONITOR_RESOLVE_PERIOD = 0.1
        current_time = time()
        if (
            self._monitor_id is None
            or current_time - self._last_capture_time > MONITOR_RESOLVE_PERIOD
        ):
            monitor_handle = win32api.MonitorFromWindow(
                self.capture_window.value, win32con.MONITOR_DEFAULTTONEAREST
            )
            display_name = win32api.GetMonitorInfo(monitor_handle)["Device"]
            candidates = [
                output_info
                for output_info in dxgi_probe.enumerate_outputs()
                if output_info.device_name == display_name
            ]
            if len(candidates) < 1:
                raise ValueError(f"No DXGI output (display name = {display_name})")
            elif len(candidates) > 1:
                raise ValueError(
                    f"Multiple DXGI output (display name = {display_name})"
                )
            else:
                new_monitor_id = MonitorIdentifier(
                    candidates[0].adapter_index, candidates[0].output_index
                )
        else:
            new_monitor_id = self._monitor_id

        # 必要ならカメラを（再）生成
        if new_monitor_id != self._monitor_id or self._dxcamera is None:
            # カメラを生成
            # NOTE
            #   先に作っていたインスタンスを確実に削除しておかないと dxcam-cpp が警告を出してくる。
            #   このケースにおいては、既存インスタンスを返すらしい。
            #   なので、一応 release を呼んでから create する。
            self.release()
            self._dxcamera = dxcam.create(
                device_idx=new_monitor_id.adapter_index,
                output_idx=new_monitor_id.output_index,
            )
            if not isinstance(self._dxcamera, dxcam.DXCamera):
                raise ValueError("Invalid return value of dxcam.create.")

            # メンバ更新
            self._monitor_id = new_monitor_id
            self._latest_ais_image = None

            # 初回 Grab
            # NOTE
            #   dxcam-cpp の挙動として、初回 grab は黒画面が返ってくる。
            #   それを読み捨てるために、一度 grab を呼び出す。
            #   また、呼び出し間隔が短すぎると更新なし
            np_image = self._dxcamera.grab()
            if np_image is None:
                raise ValueError("Invalid return value of DXCamera.grab.")
            else:
                self._latest_ais_image = AISImage(Image.fromarray(np_image))
                sleep(0.1)

        # キャプチャ
        # NOTE
        #   grab が None が返す＝画面に変化なしなので、最後のキャプチャを使う。
        np_image = self._dxcamera.grab()
        if np_image is None:
            ais_image = self._latest_ais_image
        else:
            ais_image = AISImage(Image.fromarray(np_image))
            self._latest_ais_image = ais_image

        # 最終キャプチャタイムを更新
        self._last_capture_time = time()

        # 必ず非 None が出るはず
        # NOTE
        #   静的解析を黙らせるためのチェック
        #   関数外のコンテキストも含めて考えれば、ここで None はありえない
        if ais_image is None:
            raise ValueError("Logic Error")

        # 正常終了
        return ais_image

    def release(self) -> None:
        """
        明示的にリソースを解放する
        これを呼び出さないとリソースが解放されないので次の初期化が失敗するかも。
        """
        if self._dxcamera is not None:
            self._dxcamera.release()
            del self._dxcamera
            self._dxcamera = None
