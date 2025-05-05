from inspect import (
    cleandoc
)
import re
import webbrowser

import customtkinter as ctk

from utils.constants import (
    WIDGET_PADDING,
    DEFAULT_FONT_NAME
)

# バージョン情報のインポート
# NOTE
#   バージョン情報はビルド時の動的生成が絡むため、
#   git のトラック対象外としている。
#   つまり、ファイルが存在しない場合があるため、その場合は動的に生成する。
from utils.constants import (
    VERSION_FILE_PATH
)
if not VERSION_FILE_PATH.exists():
    open(VERSION_FILE_PATH, 'w').write(cleandoc('''
    COMMIT_HASH = '-'
    BUILD_DATE = '----/--/-- --:--'
    '''))
from utils.version_constants import (
    COMMIT_HASH,
    BUILD_DATE
)


class VersionFrame(ctk.CTkFrame):
    '''
    ウィンドウ選択フレームクラス
    '''


    def __init__(
        self,
        master,
        **kwargs
    ):
        '''
        コンストラクタ
        :param master: 親ウィジェット
        :param kwargs: その他のキーワード引数
        '''
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_NAME)

        # 表示用バージョン文字列
        version_text = cleandoc(f'''
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
        ''')

        # プレビュー画像表示領域
        self.version_text_box = ctk.CTkTextbox(
            self,
            font=default_font,
            border_width=0,
            fg_color='transparent',
            wrap='word'
        )
        # self.version_text_box.insert('1.0', version_text)
        self.version_text_box.pack(
            fill='both',
            expand=True,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING
        )

        # クリックで URL を開けるようにタグを仕込む
        url_regex = re.compile(r"https?://\S+")
        pos = 0
        for m in url_regex.finditer(version_text):
            # 前の区間（プレーンテキスト）
            plain = version_text[pos:m.start()]
            self.version_text_box.insert(ctk.END, plain)

            # URL 区間
            url = m.group()
            start_index = self.version_text_box.index('end-1c')
            self.version_text_box.insert(ctk.END, url)
            end_index = self.version_text_box.index('end-1c')

            # タグ設定
            tag = f"url{start_index}"
            self.version_text_box.tag_add(tag, start_index, end_index)
            self.version_text_box.tag_config(
                tag,
                foreground="#4da3ff",
                underline=True
            )
            self.version_text_box.tag_bind(
                tag,
                "<Enter>",
                lambda e, t=tag: self.version_text_box.configure(cursor="hand2")
            )
            self.version_text_box.tag_bind(
                tag,
                "<Leave>",
                lambda e: self.version_text_box.configure(cursor="arrow")
            )
            self.version_text_box.tag_bind(
                tag,
                "<Button-1>",
                lambda e, u=url: webbrowser.open_new_tab(u)
            )

            pos = m.end()

        # 残りのテキスト
        self.version_text_box.insert(ctk.END, version_text[pos:])

        self.version_text_box.configure(state='disabled')
