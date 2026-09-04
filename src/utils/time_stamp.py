# std
import re
from datetime import datetime


def current_time_stamp() -> str:
    """
    現在時刻からタイムスタンプ文字列を生成（ミリ秒3桁）
    """
    now = datetime.now()
    ms = now.microsecond // 1000  # 0〜999
    return f"{now.strftime("%Y-%m-%d_%H-%M-%S")}_{ms:03d}"


def is_time_stamp(text: str) -> bool:
    """
    text が旧フォーマット or 新フォーマットのタイムスタンプ文字列なら True
    """
    # 新フォーマット（ミリ秒あり）
    m_new = re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d{3}", text)
    if m_new:
        return True

    # 旧フォーマット（秒まで）
    m_old = re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", text)
    if m_old:
        return True

    # どちらでもない
    return False
