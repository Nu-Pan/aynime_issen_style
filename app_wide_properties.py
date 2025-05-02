
from typing import (
    Optional
)
from dataclasses import dataclass, field

@dataclass
class AppWideProperties:
    '''
    アプリケーション全体で使用するプロパティを定義するクラス
    '''
    window_title_substring: Optional[str] = field(default=None, init=False)
