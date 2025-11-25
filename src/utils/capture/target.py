# std
from typing import Generator, Any
from dataclasses import dataclass
from copy import deepcopy
import re

# win32
import win32gui, win32con

# utils
from utils.std import replace_multi
from utils.windows import is_cloaked


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
        title = get_nime_window_text(WindowHandle(hwnd))
        if not title:
            continue
        elif title == "Program Manager":
            continue

        # ウィンドウ情報を生成して返す
        yield WindowHandle(hwnd)


def get_nime_window_text(window_handle: WindowHandle) -> str:
    """
    一閃流的に都合の良いように加工されたウィンドウ名を取得する。
    平たく言えば、ウィンドウ名からアニメ名を抽出する。
    """
    # None は空文字列化
    if window_handle is None:
        return ""

    # ウィンドウ名を取得
    text = win32gui.GetWindowText(window_handle.value)
    text = text.strip().rstrip()
    if len(text) == 0:
        return ""

    # 色々やる前のウィンドウ名を保存しておく
    raw_text = deepcopy(text)

    # Windows パス的な禁止文字を削除
    text = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", text)

    # 見た目空白な文字を ASCII 半角スペースに統一
    # NOTE
    #   NBSP, 全角, 2000-系, 202F, 205F, 1680
    text = re.sub(r"[\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000]", " ", text)

    # ゼロ幅系を削除
    # NOTE
    #   ZWSP/ZWNJ/ZWJ/WORD JOINER/BOM
    #   歴史的に空白扱いの MVS
    text = re.sub(r"[\u200B-\u200D\u2060\uFEFF\u180E]", "", text)

    # ソフトハイフンを削除
    # NOTE
    #   通常は印字されず「改行位置の候補」だけを意味する。
    #   可視の意図はないので 削除。
    text = re.sub(r"\u00AD", "", text)

    # 区切り文字を ASCII のハイフンで統一
    # NOTE
    #   \u2013 = en dash
    #   \u2014 = em dash
    #   \u2015 = horizontal bar
    #   \u007C = vertical bar (ASCII |)
    #   \uFF5C = fullwidth vertical bar
    #   \u2011 = non-breaking hyphen
    text = re.sub(r"[\u2013\u2014\u2015\u007C\uFF5C\u2011]", "-", text)

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
        if text.find("アニメ動画見放題") >= 0:
            # NOTE
            #   作品ページの場合「アニメ動画見放題」がついている
            #   作品ページはタイトルに話数情報が含まれないのでアニメ名抽出の対象としない
            return raw_text
        else:
            # NOTE
            #   dアニメストアは「<アニメ名> - <話数> - <話タイトル>」形式。
            #   <話タイトル> は冗長なので除外する。
            #   区切り文字「 - 」は贅沢なので空白１文字に短縮。
            text = text.replace(" dアニメストア", "")
            text = " ".join(text.split(" - ")[:2])
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
    return "<NIME>" + text
