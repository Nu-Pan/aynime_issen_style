# std
import sys
from pathlib import Path
from datetime import datetime
import logging
from typing import Any, Iterable
import traceback


def redirect_to_file() -> None:
    """
    プログラムの stdout, stderr がファイルにリダイレクトされるように設定する
    ログローテーションも行われる
    """
    # ログディレクトリを作成
    log_dir_path = Path.cwd() / "log"
    if not log_dir_path.exists():
        log_dir_path.mkdir()

    # 既存ログファイルを列挙
    existing_log_files = [p for p in log_dir_path.glob("*.log")]
    existing_log_files.sort()

    # 最大数から溢れないように、古い方のログファイルを削除
    NUM_MAX_LOG_FILES = 10
    num_overflow_log_files = max(0, len(existing_log_files) - NUM_MAX_LOG_FILES + 1)
    for p in existing_log_files[:num_overflow_log_files]:
        p.unlink()

    # リダイレクト先ファイルパス
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_path = log_dir_path / (date_str + ".log")

    # stdout, stderr をファイルへリダイレクト
    sys.stdout = open(log_file_path, "w", encoding="utf-8", buffering=1)
    sys.stderr = sys.stdout

    # logging もファイルへ
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_file_path, encoding="utf-8")],
    )


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
