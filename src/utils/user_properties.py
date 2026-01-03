# std
import json
from typing import TypeVar, Any
from threading import Thread, Lock
from copy import copy
import time

# utils
from utils.constants import USER_PROPERTIES_FILE_PATH
from utils.ais_logging import write_log

T = TypeVar("T")


def _is_json_serializable(obj: Any, path="$") -> bool:
    """
    value がプロパティとして合法な値なら True をかえす
    list, dict みたいな構造オブジェクトの場合は再帰的に全要素をチェックする。
    """
    if isinstance(obj, (list, tuple)):
        return all(_is_json_serializable(v) for v in obj)
    elif isinstance(obj, dict):
        return all(
            isinstance(k, str) and _is_json_serializable(v) for k, v in obj.items()
        )
    else:
        return isinstance(obj, (int, float, str)) or obj is None


class UserProperties:
    """
    ユーザー設定のファイル I/O を抽象化するクラス
    ファイルへの書き込みはメモリ上でバッファリングされて、
    指示があった時にファイルに書き込まれる。
    """

    # 最後に set されてから _DEBOUNS_DURATION sec 後にファイル書き込みが実行される
    # NOTE
    #   スライダー操作とかで頻繁に set が呼び出された場合にそれら呼び出しを１つにまとめるための措置
    _DEBOUNS_DURATION = 2.0

    def __init__(self):
        """
        コンストラクタ
        """
        # ファイルからプロパティを復元
        if not USER_PROPERTIES_FILE_PATH.exists():
            self._properties = dict()
        else:
            try:
                self._properties = json.load(open(USER_PROPERTIES_FILE_PATH))
            except Exception as e:
                write_log(
                    "error",
                    f"Failed to load user properties from {USER_PROPERTIES_FILE_PATH}",
                    exception=e,
                )
                self._properties = dict()

        # スレッド関係
        self._lock = Lock()
        self._flush_deadline = None
        self._does_thread_stop = False
        self._thread = Thread(target=self._thread_handler)
        self._thread.start()

    def close(self):
        """
        クローズ
        """
        # スレッド停止を通知
        # NOTE
        #   即時フラッシュしたいので _flush_deadline にデバウンス時間は加算しない
        with self._lock:
            self._flush_deadline = time.monotonic()
            self._does_thread_stop = True
        # スレッド停止を待機
        # NOTE
        #   異常系で呼ばれてる可能性もあるのでタイムアウトも許容
        self._thread.join(timeout=1.0)

    def get(self, key: str, default_value: T) -> T:
        """
        値を読み出す
        """
        with self._lock:
            if key in self._properties:
                return self._properties[key]
            else:
                self._properties[key] = default_value
                return default_value

    def set(self, key: str, value: int | float | str | None):
        """
        値を設定する
        """
        if _is_json_serializable(value):
            with self._lock:
                self._properties[key] = value
                self._flush_deadline = (
                    time.monotonic() + UserProperties._DEBOUNS_DURATION
                )
        else:
            raise ValueError(f"{value} is not json serializable")

    def _thread_handler(self):
        """
        スレッドハンドラ
        ファイルへの書き込みを非同期に行う
        """
        while True:
            # ロック取ってパラメータだけ取る
            snapshot = None
            does_thread_stop = False
            with self._lock:
                if (
                    self._flush_deadline is not None
                    and time.monotonic() >= self._flush_deadline
                ):
                    snapshot = copy(self._properties)
                    self._flush_deadline = None
                does_thread_stop = self._does_thread_stop
            # ロックの外でファイルに書き出す
            if snapshot is not None:
                with open(USER_PROPERTIES_FILE_PATH, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, ensure_ascii=False)
            # スレッド終了
            # NOTE 「ファイルに書き出しつつスレッド停止」をサポートしたいのでこの書き方になっている
            if does_thread_stop:
                return
            # スライスを譲る
            time.sleep(1 / 1000)
