from inspect import (
    cleandoc
)
import subprocess
from datetime import datetime

import customtkinter as ctk

from constants import (
    WIDGET_PADDING,
    DEFAULT_FONT_NAME
)
try:
    from version_constants import (
        COMMIT_HASH,
        BUILD_DATE
    )
except:
    COMMIT_HASH = '-'
    BUILD_DATE = '----/--/-- --:--'


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
        Author: NU-Pan
                                
        GitHub: https://github.com/Nu-Pan/aynime_issen_style
                                
        Commit Hash: {COMMIT_HASH}

        Build Date: {BUILD_DATE}
        ''')

        # プレビュー画像表示用ラベル
        self.version_text_label = ctk.CTkLabel(
            self,
            text=version_text,
            font=default_font,
            anchor='w',
            justify='left'
        )
        self.version_text_label.pack(
            fill='none',
            expand=True,
            padx=WIDGET_PADDING,
            pady=WIDGET_PADDING
        )
