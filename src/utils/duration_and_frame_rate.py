# std
from typing import Generator
import math

# 映画の標準的なフレームレート
# NOTE
#   アニメも基本これ
FILM_TIMELINE_IN_FPS = 24 * 1000 / 1001

# 世の中的に標準的なフレームレートのリスト
# NOTE
#   60 fps はツールのメモリフットプリント的にも gif 的にも過剰なので除外
STANDARD_FRAME_RATES = sorted(
    [
        # 映画・アニメ向け
        # 23.976 FPS ベース
        # 1 ~ 4 コマ打ちが対象
        FILM_TIMELINE_IN_FPS,
        FILM_TIMELINE_IN_FPS / 2.0,
        FILM_TIMELINE_IN_FPS / 3.0,
        FILM_TIMELINE_IN_FPS / 4.0,
        # Youtube とかの動画・ライブ向け
        # 60 FPS ベース
        # 10 ~ 30 FPS の程よい範囲が対象
        60.0 / 2.0,
        60.0 / 3.0,
        60.0 / 4.0,
        60.0 / 5.0,
        60.0 / 6.0,
    ]
)


class DFREntry:
    """
    Duration and Frame Rate Map を構成するエントリー
    """

    def __init__(self, duration_in_msec: int):
        """
        コンストラクタ
        """
        self._duration_in_msec = duration_in_msec
        self._frame_rate = 1000 / duration_in_msec

    @property
    def duration_in_msec(self) -> int:
        """
        duration(msec) を取得
        """
        return self._duration_in_msec

    @property
    def frame_rate(self) -> float:
        """
        フレームレートを取得
        """
        return self._frame_rate


class DFRMap:
    """
    Duration and Frame Rate Map
    gif の更新周期の分解能が 10msec であることに端を発するマップ
    合法で意味のある周期・フレームレートを提供する
    モジュール外からのアクセスは GIF_DURATION_MAP の方を使うこと
    """

    def __init__(self):
        """
        コンストラクタ
        """
        # フレームレートの候補を列挙
        # NOTE
        #   標準フレームレート的にあり得る範囲内で、
        #   かつ gif 的に合法なフレームレートが対象
        min_frame_rate = min(STANDARD_FRAME_RATES)
        max_frame_rate = max(STANDARD_FRAME_RATES)
        max_duration_in_sec = 10 * math.ceil(100 / min_frame_rate)
        min_duration_in_sec = 10 * math.floor(100 / max_frame_rate)
        cands = [
            DFREntry(gd)
            for gd in range(min_duration_in_sec, max_duration_in_sec + 10, 10)
        ]

        # 各標準フレームレートから、最も近い候補を選択
        self._entries = [
            min(cands, key=lambda c: abs(c.frame_rate - tgt_fr))
            for tgt_fr in STANDARD_FRAME_RATES
        ]

    def __len__(self) -> int:
        """
        エントリー数
        """
        return len(self._entries)

    def __getitem__(self, index: int) -> DFREntry:
        """
        添字アクセス
        """
        return self._entries[index]

    def __iter__(self) -> Generator[DFREntry, None, None]:
        """
        イテレーション
        """
        for e in self._entries:
            yield e

    def by_duration_in_msec(self, duration_in_msec: int) -> DFREntry:
        """
        duration(msec) からエントリーを得る
        一番値が近いものが選ばれる
        """
        return min(
            self._entries, key=lambda e: abs(e.duration_in_msec - duration_in_msec)
        )

    def by_frame_rate(self, frame_rate: float) -> DFREntry:
        """
        フレームレートからエントリーを得る
        一番値が近いものが選ばれる
        """
        return min(self._entries, key=lambda e: abs(e.frame_rate - frame_rate))

    @property
    def default_entry(self) -> DFREntry:
        """
        デフォルトのエントリーを取得する
        """
        return self.by_frame_rate(FILM_TIMELINE_IN_FPS)


# 合法で意味のある周期・フレームレートのマップ
DFR_MAP = DFRMap()
