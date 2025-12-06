# std
from inspect import cleandoc
import re
import webbrowser
import sys

# Tk/CTk
import customtkinter as ctk

# utils
from utils.constants import DEFAULT_FONT_FAMILY, VERSION_FILE_PATH
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


class VersionFrame(AISFrame):
    """
    バージョン情報フレーム
    """

    UI_TAB_NAME = "バージョン"

    def __init__(self, master, **kwargs):
        """
        コンストラクタ

        Args:
            master (_type_): 親ウィジェット
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

        # プレビュー画像表示領域
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
