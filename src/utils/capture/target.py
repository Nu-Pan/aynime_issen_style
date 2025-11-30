# std
from typing import Generator
from dataclasses import dataclass
from copy import deepcopy
import re

# win32
import win32gui, win32con

# utils
from utils.std import replace_multi
from utils.windows import is_cloaked, sanitize_text


@dataclass
class MonitorIdentifier:
    """
    モニター識別子を保持するクラス
    """

    adapter_index: int  # グラボのインデックス
    output_index: int  # モニターのインデックス


@dataclass
class WindowHandle:
    """
    ウィンドウ識別子を保持するクラス
    """

    value: int


def enumerate_windows() -> Generator[WindowHandle, None, None]:
    # 全てのウィンドウハンドルを列挙
    hwnds: list[int] = []

    def enum_handler(hwnd: int, _):
        hwnds.append(hwnd)

    win32gui.EnumWindows(enum_handler, None)

    # 合法なウィンドウを順番に返す
    for hwnd in hwnds:
        # 不可視ウィンドウはスキップ
        if not win32gui.IsWindowVisible(hwnd):
            continue

        # 最小化されているウィンドウはスキップ
        if win32gui.IsIconic(hwnd):
            continue

        # クローク状態のウィンドウはスキップ
        if is_cloaked(hwnd):
            continue

        # サイズを持たないウィンドウはスキップ
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        if right - left <= 0 or bottom - top <= 0:
            continue

        # オーナーが居るウィンドウはスキップ
        if win32gui.GetWindow(hwnd, win32con.GW_OWNER):
            continue

        # タイトルでフィルタ
        # NOTE
        #   空タイトルはダメ
        #   Program Manager は何故か残っちゃうので名指しで除外
        title, _ = get_nime_window_text(WindowHandle(hwnd))
        if not title:
            continue
        elif title == "Program Manager":
            continue

        # ウィンドウ情報を生成して返す
        yield WindowHandle(hwnd)


def get_nime_window_text(window_handle: WindowHandle) -> tuple[str, bool]:
    """
    一閃流的に都合の良いように加工されたウィンドウ名を取得する。
    平たく言えば、ウィンドウ名からアニメ名を抽出する。
    (加工された名前, えぃにめか？) を返す。
    """
    # None は空文字列化
    if window_handle is None:
        return "", False

    # ウィンドウ名を取得
    text = win32gui.GetWindowText(window_handle.value)
    text = sanitize_text(text)
    if len(text) == 0:
        return "", False

    # アプリの種類で分岐
    # NOTE
    #   ブラウザの場合はアニメ名が取れるので、末尾のアプリ名だけ取って続行。
    #   それ以外は断念
    if text.endswith("Mozilla Firefox"):
        text = text.replace(" - Mozilla Firefox", "")
    elif text.endswith("Google Chrome"):
        text = text.replace(" - Google Chrome", "")
    elif text.endswith(" - Discord"):
        # NOTE
        #   Discord の配信画面は、チャンネル名が返ってくる
        #   そこにえぃにめは無い
        text = text.replace(" - Discord", "")
        return text, False
    else:
        # それ以外の非対応アプリ
        return text, False

    # 配信サービス別の処理
    # NOTE
    #   アニメタイトルと話数は区別せずに１つの「アニメ名」とみなす。
    #   最終的にそれを見た人間が認識できれば何でも良いので、一閃流として区別する必要がない。
    bc_pos = text.find("バンダイチャンネル")
    if text.endswith("dアニメストア"):
        if text.find("アニメ動画見放題") >= 0:
            # NOTE
            #   作品ページの場合「アニメ動画見放題」がついている
            #   作品ページはタイトルに話数情報が含まれないのでアニメ名抽出の対象としない
            return text, False
        else:
            # NOTE
            #   dアニメストアは「<アニメ名> - <話数> - <話タイトル>」形式。
            #   <話タイトル> は冗長なので除外する。
            #   区切り文字「 - 」は贅沢なので空白１文字に短縮。
            text = text.replace(" dアニメストア", "")
            text = " ".join(text.split(" - ")[:2])
    elif text.endswith("AnimeFesta"):
        # NOTE
        #   AnimeFesta はアニメ名しか出てこないので、特別にすることも無い
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
        return text, False

    # 余計な空白を除去
    text = text.strip().rstrip()
    text = re.sub(r" {2,}", " ", text)

    # 正常終了
    return text, True
