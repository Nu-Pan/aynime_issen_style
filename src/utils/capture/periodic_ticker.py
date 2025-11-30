import time
import threading


class PeriodicTicker:
    """
    固定周期で tick を刻むユーティリティ（開始→開始基準）。
    ・残り > spin_threshold のあいだは Event.wait() で譲る
    ・最後のわずかな残りは軽いスピンで締める
    ・オーバーラン時は “追いつき”（複数周期スキップ）可
    """

    def __init__(
        self,
        fps: float,
        stop: threading.Event,
        spin_threshold: float = 0.001,  # 1ms
        catch_up: bool = True,
    ):
        self.period = 1.0 / fps
        self.stop = stop
        self.spin_threshold = spin_threshold
        self.catch_up = catch_up
        self.next_t = time.perf_counter()
        self.overrun_count = 0

    def wait_next(self) -> float | None:
        """
        次の理想時刻まで待つ。戻り値は “このフレームの予定開始時刻”。
        stop が立ったら None を返す。
        """
        # 次の理想開始時刻
        self.next_t += self.period

        while True:
            if self.stop.is_set():
                return None

            now = time.perf_counter()
            remain = self.next_t - now

            if remain <= 0:
                # 既に締切を過ぎた → オーバーラン
                self.overrun_count += 1
                if not self.catch_up:
                    # 追いつかず “次から” にする
                    self.next_t = now
                    return self.next_t
                else:
                    # 複数周期分まとめてスキップして追いつく
                    # 例：remain=-2.4*period なら 2周期スキップ
                    skip = int((-remain) // self.period) + 1
                    self.next_t += skip * self.period
                    # 追いついたのでループ継続して改めて待つ
                    continue

            # 残りが十分なら譲って待つ（CPU解放）
            if remain > self.spin_threshold:
                # ほんの少し手前まで待つ
                wait_time = remain - self.spin_threshold
                # Event.wait は timeout 中は他スレッドへ譲る
                self.stop.wait(wait_time)
                continue

            # 最後のわずかはスピンで締めてジッタ低減
            while True:
                if self.stop.is_set():
                    return None
                if time.perf_counter() >= self.next_t:
                    return self.next_t  # このフレームの予定開始時刻が返る
