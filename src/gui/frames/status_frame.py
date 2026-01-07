# std
from inspect import cleandoc
import re
import webbrowser
import sys
import os
from dataclasses import dataclass
from pathlib import Path

# Tk/CTk
import customtkinter as ctk

# utils
from utils.constants import (
    APP_NAME_JP,
    AIS_LICENSE_FILE_PATH,
    LICENSES_DIR_PATH,
    DEFAULT_FONT_FAMILY,
    VERSION_FILE_PATH,
    WIDGET_MIN_WIDTH,
    WIDGET_MIN_HEIGHT,
    NIME_DIR_PATH,
    TENSEI_DIR_PATH,
)
from utils.ais_logging import write_log
from utils.user_properties import USER_PROPERTIES
from utils.ensure_web_tool import DEFAULT_FFMPEG_ZIP_URL, DEFAULT_GIFSCICLE_ZIP_URL


# gui
from gui.widgets.ais_frame import AISFrame


# バージョン情報のインポート
# NOTE
#   バージョン情報はビルド時の動的生成が絡むため、
#   git のトラック対象外としている。
#   つまり、ファイルが存在しない場合があるため、その場合は動的に生成する。
if not hasattr(sys, "_MEIPASS") and not VERSION_FILE_PATH.exists():
    __version_text = """
    COMMIT_HASH = '-'
    BUILD_DATE = '----/--/-- --:--'
    """
    open(VERSION_FILE_PATH, "w").write(cleandoc(__version_text))
from utils.version_constants import COMMIT_HASH, BUILD_DATE


class ShortcutFrame(AISFrame):
    """
    フォルダ開くボタンとか、そういう滅多に押さないウィジェットをまとめるフレーム
    """

    UI_TAB_NAME = "ショートカット"

    def __init__(self, master, **kwargs):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # NIME フォルダボタン
        self._nime_button = ctk.CTkButton(
            self,
            text="OPEN NIME FOLDER",
            width=3 * WIDGET_MIN_WIDTH,
            height=WIDGET_MIN_HEIGHT,
            command=lambda: os.startfile(NIME_DIR_PATH),
        )
        self.ais.grid_child(self._nime_button, 0, 0, sticky="")

        # 転生フォルダボタン
        self._tensei_button = ctk.CTkButton(
            self,
            text="OPEN TENSEI FOLDER",
            width=3 * WIDGET_MIN_WIDTH,
            height=WIDGET_MIN_HEIGHT,
            command=lambda: os.startfile(TENSEI_DIR_PATH),
        )
        self.ais.grid_child(self._tensei_button, 1, 0, sticky="")


class VersionFrame(AISFrame):
    """
    バージョン情報を表示するためだけのフレーム
    """

    UI_TAB_NAME = "バージョン"

    def __init__(self, master, **kwargs):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)

        # 表示用バージョン文字列
        version_text = f"""
        Author
        \tNU-Pan
        
        GitHub
        \thttps://github.com/Nu-Pan/aynime_issen_style

        User's Manual
        \thttps://github.com/Nu-Pan/aynime_issen_style/wiki/User's-Manual

        Commit Hash
        \t{COMMIT_HASH}

        Build Date
        \t{BUILD_DATE}

        俺は星間国家の悪徳領主!
        \thttps://seikankokka-anime.com/

        無職の英雄 〜別にスキルなんか要らなかったんだが〜
        \thttps://mushoku-eiyu-anime.com/
        \thttps://ncode.syosetu.com/n6683ej/4/
        """
        version_text = cleandoc(version_text)

        # バージョン情報テキストボックス
        self.version_text_box = ctk.CTkTextbox(
            self, font=default_font, border_width=0, fg_color="transparent", wrap="word"
        )
        self.ais.grid_child(self.version_text_box, 0, 0)
        self.ais.rowconfigure(0, weight=1)
        self.ais.columnconfigure(0, weight=1)

        # クリックで URL を開けるようにタグを仕込む
        url_regex = re.compile(r"https?://\S+")
        pos = 0
        for m in url_regex.finditer(version_text):
            # 前の区間（プレーンテキスト）
            plain = version_text[pos : m.start()]
            self.version_text_box.insert(ctk.END, plain)

            # URL 区間
            url = m.group()
            start_index = self.version_text_box.index("end-1c")
            self.version_text_box.insert(ctk.END, url)
            end_index = self.version_text_box.index("end-1c")

            # タグ設定
            tag = f"url{start_index}"
            self.version_text_box.tag_add(tag, start_index, end_index)
            self.version_text_box.tag_config(tag, foreground="#4da3ff", underline=True)
            self.version_text_box.tag_bind(
                tag,
                "<Enter>",
                lambda e, t=tag: self.version_text_box.configure(cursor="hand2"),
            )
            self.version_text_box.tag_bind(
                tag,
                "<Leave>",
                lambda e: self.version_text_box.configure(cursor="arrow"),
            )
            self.version_text_box.tag_bind(
                tag, "<Button-1>", lambda e, u=url: webbrowser.open_new_tab(u)
            )

            pos = m.end()

        # 残りのテキストを追加
        self.version_text_box.insert(ctk.END, version_text[pos:])

        # 表示用なので変更不可
        self.version_text_box.configure(state="disabled")


@dataclass
class SoftwareLicenseEntry:
    """
    ソフトウェアとそのライセンスにまつわる情報をまとめたクラス
    """

    message: str | None
    official_url: str
    download_url: str
    license_name: str
    license_file_path: Path


SOFTWARE_LICENSE_ENTRIES = {
    APP_NAME_JP: SoftwareLicenseEntry(
        f"{APP_NAME_JP}は MIT ライセンスで公開しています",
        "https://github.com/Nu-Pan/aynime_issen_style",
        "https://github.com/Nu-Pan/aynime_issen_style/releases",
        "MIT",
        AIS_LICENSE_FILE_PATH,
    ),
    "FFmpeg": SoftwareLicenseEntry(
        None,
        "https://www.ffmpeg.org/",
        USER_PROPERTIES.get("ffmpeg_zip_url", DEFAULT_FFMPEG_ZIP_URL),
        "GPL-2.0-or-later",
        LICENSES_DIR_PATH / "GPL-2.0.txt",
    ),
    "gifscile": SoftwareLicenseEntry(
        None,
        "https://www.lcdf.org/gifsicle/",
        USER_PROPERTIES.get("gifscicle_zip_url", DEFAULT_GIFSCICLE_ZIP_URL),
        "GPL-2.0-only",
        LICENSES_DIR_PATH / "GPL-2.0.txt",
    ),
}


def _set_readonly_text_box(widget: ctk.CTkTextbox, text: str):
    """
    編集不可テキストボックスに文字列を設定するヘルパ
    """
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    widget.configure(state="disabled")
    widget.yview_moveto(0.0)


class LicenseFrame(AISFrame):
    """
    ライセンス情報を表示するフレーム
    """

    UI_TAB_NAME = "ライセンス"

    def __init__(self, master, **kwargs):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)

        # レイアウト
        self.ais.columnconfigure(0, weight=1)

        # ソフトウェア選択コンボボックス
        self._software_combo_box = ctk.CTkComboBox(
            self,
            width=WIDGET_MIN_WIDTH,
            height=WIDGET_MIN_HEIGHT,
            values=[k for k in SOFTWARE_LICENSE_ENTRIES],
            command=self._on_software_combo_box_changed,
        )
        self.ais.grid_child(self._software_combo_box, 0, 0)

        # 説明ラベル
        self._message_text_box = ctk.CTkTextbox(
            self,
            width=WIDGET_MIN_WIDTH,
            height=3 * WIDGET_MIN_HEIGHT,
            font=default_font,
            wrap="word",
            state="disabled",
        )
        self.ais.grid_child(self._message_text_box, 1, 0)

        # ライセンス条文テキストボックス
        self._license_text_box = ctk.CTkTextbox(
            self,
            width=WIDGET_MIN_WIDTH,
            height=WIDGET_MIN_HEIGHT,
            font=default_font,
            wrap="word",
            state="disabled",
        )
        self.ais.grid_child(self._license_text_box, 2, 0)
        self.ais.rowconfigure(2, weight=1)

        # 一閃流のライセンスをプリロード
        self._on_software_combo_box_changed(APP_NAME_JP)

    def _on_software_combo_box_changed(self, selected_name: str):
        """
        ソフトウェア選択コンボボックス変更ハンドラ
        """
        entry = SOFTWARE_LICENSE_ENTRIES.get(selected_name)
        if entry is None:
            _set_readonly_text_box(self._message_text_box, "")
            _set_readonly_text_box(self._license_text_box, "")
        else:
            # メッセージを設定
            if entry.message:
                # fmt: off
                msg = cleandoc(f"""
                {entry.message}
                公式: {entry.official_url}
                ダウンロード: {entry.download_url}
                ライセンス: {entry.license_name}
                """)
                # fmt: on
            else:
                # fmt: off
                msg = cleandoc(f"""
                {APP_NAME_JP}は {selected_name} をサブプロセスとして利用します。
                公式: {entry.official_url}
                ダウンロード: {entry.download_url}
                ライセンス: {entry.license_name}
                """)
                # fmt: on
            _set_readonly_text_box(self._message_text_box, msg)
            # 条文を設定
            license_str = ""
            try:
                with open(entry.license_file_path, "r", encoding="utf-8") as f:
                    license_str = f.read()
            except:
                write_log("error", f"Failed to load {entry.license_file_path}")
                pass
            _set_readonly_text_box(self._license_text_box, license_str)


class StatusFrame(ctk.CTkFrame):
    """
    ステータスフレーム
    その他いろいろを詰めるためのフレーム
    """

    UI_TAB_NAME = "ステータス"

    def __init__(self, master, **kwargs):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # タブビューを追加
        self.tabview = ctk.CTkTabview(self, corner_radius=0, border_width=0)
        self.tabview.pack(fill="both", expand=True)

        # ショートカットタブを追加
        self.tabview.add(ShortcutFrame.UI_TAB_NAME)
        self.shortcut_frame = ShortcutFrame(self.tabview.tab(ShortcutFrame.UI_TAB_NAME))
        self.shortcut_frame.pack(fill="both", expand=True)

        # バージョンタブを追加
        self.tabview.add(VersionFrame.UI_TAB_NAME)
        self.version_frame = VersionFrame(self.tabview.tab(VersionFrame.UI_TAB_NAME))
        self.version_frame.pack(fill="both", expand=True)

        # ライセンスタブを追加
        self.tabview.add(LicenseFrame.UI_TAB_NAME)
        self.license_frame = LicenseFrame(self.tabview.tab(LicenseFrame.UI_TAB_NAME))
        self.license_frame.pack(fill="both", expand=True)
