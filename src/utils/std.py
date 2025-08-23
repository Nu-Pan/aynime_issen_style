# std
import sys
from pathlib import Path
from datetime import datetime
import logging
from typing import Any, Iterable
import traceback


def flatten(source: Any) -> Any:
    """
    入れ子になったリストをフラット化する

    Args:
        source (List[Any]): フラット化したいリスト

    Returns:
        List[Any]: フラット化されたリスト
    """
    if isinstance(source, list):
        for item in source:
            yield from flatten(item)
    elif isinstance(source, tuple):
        for item in source:
            yield from flatten(item)
    else:
        yield source


def traceback_str(exception: Exception) -> str:
    """
    excetpion からトレースバック文字列を生成する
    """
    return "".join(
        traceback.format_exception(type(exception), exception, exception.__traceback__)
    )


def replace_multi(
    text: str,
    repl_sources: Iterable[str],
    repl_target: str,
) -> str:
    """
    text 中に登場する repl_source を repl_target で置き換える。
    標準の replace の複数指定可能バージョン
    """
    for repl_source in repl_sources:
        text = text.replace(repl_source, repl_target)
    return text
