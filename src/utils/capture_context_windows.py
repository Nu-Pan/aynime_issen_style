# std
from typing import Generator, List, Union, Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from copy import deepcopy
import re

# win32
import win32gui, win32ui, win32con, win32api
from PIL import Image

# dxcam
import dxcam_cpp as dxcam

# dxgi_probe
import dxgi_probe

# utils
from utils.image import AISImage
from utils.capture_context import WindowHandle, CaptureContext
from utils.std import replace_multi


def get_nime_window_text(window_handle: WindowHandle) -> str:
    """
    一閃流的に都合の良いように加工されたウィンドウ名を取得する
    """
    # ウィンドウ名を取得
    text = win32gui.GetWindowText(window_handle.value)
    text = text.strip().rstrip()
    if len(text) == 0:
        return ""

    # 色々やる前のウィンドウ名を保存しておく
    raw_text = deepcopy(text)

    # Windows パス的な禁止文字を削除
    text = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", text)

    # 区切り文字を ASCII のハイフンで統一
    # NOTE
    #   - = dash(ASCII)
    #   – = en dash(Unicode)
    #   — = em dash(Unicode)
    text = replace_multi(text, ["–", "—", "|", "｜"], "-")

    # 空白文字を半角で統一
    text = text.replace("　", " ")

    # アンダースコア --> 半角空白
    text = text.replace("_", " ")

    # ２つ以上連続する空白を 1 文字に短縮
    text = re.sub(r" {2,}", " ", text)

    # アプリの種類で分岐
    # NOTE
    #   ブラウザの場合はアニメ名が取れるので、末尾のアプリ名だけ取って続行。
    #   それ以外は断念して UNKNOWN を返す
    if text.endswith("Mozilla Firefox"):
        text = text.replace(" - Mozilla Firefox", "")
    elif text.endswith("Google Chrome"):
        text = text.replace(" - Google Chrome", "")
    elif text.endswith("Discord"):
        # NOTE
        #   Discord の配信画面は、チャンネル名が返ってくる
        #   そこにアニメは無い
        return raw_text
    else:
        # それ以外の非対応アプリ
        return raw_text

    # 配信サービス別の処理
    # NOTE
    #   アニメタイトルと話数は区別せずに１つの「アニメ名」とみなす。
    #   最終的にそれを見た人間が認識できれば何でも良いので、一閃流として区別する必要がない。
    bc_pos = text.find("バンダイチャンネル")
    if text.endswith("dアニメストア"):
        # NOTE
        #   区切り文字３文字は贅沢なので１文字に短縮
        text = text.replace(" dアニメストア", "")
        text = text.replace(" - ", " ")
    elif text.endswith("AnimeFesta"):
        # NOTE
        #   AnimeFest はアニメ名しか出てこないので、特別にすることも無い
        text = text.replace("を見る AnimeFesta", "")
    elif bc_pos != -1:
        # NOTE
        #   バンダイチャンネルの場合、余計な文字がいっぱい付くので、それらをまとめてカット。
        #   また、微妙な区切り文字が残るのでそれもカット。
        text = text[:bc_pos]
        if text.endswith("- "):
            text = text[:-2]
    elif text.endswith("Prime Video"):
        # NOTE
        #   Amazon Prime Video の場合、前後に余計な文字が付くので、それらをカット。
        text = replace_multi(text, ["Amazon.co.jp ", "を観る Prime Video"], "")
    else:
        return raw_text

    # 前後の空白系文字を削除
    text = text.strip().rstrip()

    # ２つ以上連続する空白を 1 文字に短縮
    text = re.sub(r" {2,}", " ", text)

    # 正常終了
    return "NIME " + text


@dataclass
class MonitorIdentifier:
    """
    モニター識別子を保持するクラス
    """

    adapter_index: int  # グラボのインデックス
    output_index: int  # モニターのインデックス

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, MonitorIdentifier):
            return (
                self.adapter_index == other.adapter_index
                and self.output_index == other.output_index
            )
        else:
            return False


class CaptureContextWindows(CaptureContext):
    """
    Windows 用キャプチャコンテキスト
    PyWin32 でウィンドウを選択し DXCAM でキャプチャする。
    """

    def __init__(self) -> None:
        """
        コンストラクタ
        """
        super().__init__()
        self._window_handle = None
        self._monitor_id = None
        self._dxcamera = None
        self._last_capture_time = time.time()
        self._latest_ais_image = None

    def enumerate_windows(self) -> Generator[WindowHandle, None, None]:
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
            title = get_nime_window_text(WindowHandle(hwnd))
            if not title:
                continue

            # ウィンドウ情報を生成して返す
            yield WindowHandle(hwnd)

    def set_capture_window(self, window_handle: WindowHandle) -> None:
        self._window_handle = window_handle

    @property
    def current_window_name(self) -> Optional[str]:
        if self._window_handle is None:
            return None
        else:
            return get_nime_window_text(self._window_handle)

    def get_window_name(self, window_handle: WindowHandle) -> str:
        return get_nime_window_text(window_handle)

    def capture(self) -> AISImage:
        # 対象ウィンドウが未指定ならエラー
        if self._window_handle is None:
            raise ValueError("Invalid Window not set")

        # キャプチャ対象モニターを解決
        # NOTE
        #   動画キャプチャ向けの連続呼び出し時に毎回再チェックが走ると重そうなので、
        #   前回キャプチャから時間が経ってる場合だけ再チェックを行う。
        MONITOR_RESOLVE_PERIOD = 0.1
        current_time = time.time()
        if (
            self._monitor_id is None
            or current_time - self._last_capture_time > MONITOR_RESOLVE_PERIOD
        ):
            monitor_handle = win32api.MonitorFromWindow(
                self._window_handle.value, win32con.MONITOR_DEFAULTTONEAREST
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
                time.sleep(0.1)

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
        self._last_capture_time = time.time()

        # 必ず非 None が出るはず
        # NOTE
        #   静的解析を黙らせるためのチェック
        #   関数外のコンテキストも含めて考えれば、ここで None はありえない
        if ais_image is None:
            raise ValueError("Logic Error")

        # 正常終了
        return ais_image

    def release(self) -> None:
        if self._dxcamera is not None:
            self._dxcamera.release()
            del self._dxcamera
            self._dxcamera = None
