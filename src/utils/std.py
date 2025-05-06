import sys
from pathlib import Path
from datetime import datetime
import logging


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
