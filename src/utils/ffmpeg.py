# std
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
import subprocess
import re
import tempfile

# PIL
from PIL import Image

# utils
from utils.constants import FFMPEG_DIR_PATH, APP_NAME_EN
from utils.ais_logging import write_log
from utils.image import ContentsMetadata, smart_pil_save


# ffmpeg のダウンロード先 URL
BTBN_LATEST_WIN64_LGPL_ZIP = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-lgpl.zip"
)


def _download_file(url: str, dest_file_path: Path) -> None:
    """
    url から dest_dir_path にファイルをダウンロードする。
    """
    # 定数
    _TIMEOUT_IN_SEC = 10
    _CHUNK_SIZE_IN_BYTES = 1024 * 1024

    # ダウンロード先ディレクトリを作成
    dest_file_path.parent.mkdir(parents=True, exist_ok=True)

    # リクエストを構築
    req = urllib.request.Request(
        url, headers={"User-Agent": f"{APP_NAME_EN}/ffmpeg-bootstrap (urllib)"}
    )

    # ダウンロード
    # NOTE
    #   直接的なダウンロード先は .part ファイル
    #   ダウンロード完了時にリネームする
    with urllib.request.urlopen(req, timeout=_TIMEOUT_IN_SEC) as resp:
        temp_file_path = dest_file_path.with_suffix(dest_file_path.suffix + ".part")
        with temp_file_path.open("wb") as f:
            while True:
                chunk = resp.read(_CHUNK_SIZE_IN_BYTES)
                if not chunk:
                    break
                f.write(chunk)
        temp_file_path.replace(dest_file_path)


def _extract_zip(zip_file_path: Path, dest_dir_path: Path):
    """
    zip_file_path の内容物を dest_dir_path に展開する
    """
    # パスを正規化
    zip_file_path = zip_file_path.resolve()
    dest_dir_path = dest_dir_path.resolve()

    # 展開先ディレクトリを作成
    dest_dir_path.mkdir(parents=True, exist_ok=True)

    # zip の中身を読み出す
    with zipfile.ZipFile(zip_file_path, "r") as zf:
        infos = zf.infolist()
        for info in infos:
            # 中身の相対パスを構築
            # NOTE
            #   filename は / 区切りなので Path で解釈可能
            entry_relative_path = Path(info.filename)

            # ディレクトリはスキップ
            if info.is_dir():
                continue

            # dest_dir_path の外への展開は危ないのでエラー
            out_file_path = (dest_dir_path / entry_relative_path).resolve()
            if not str(out_file_path).startswith(str(dest_dir_path)):
                raise RuntimeError(f"Unsafe zip entry: {info.filename}")

            # 展開
            out_file_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, out_file_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)


def _find_file_under_dir(dir_path: Path, file_name: str) -> Path | None:
    """
    dir_path 以下から再帰的に file_name を探す
    """
    # 候補を列挙
    # NOTE
    #   bin 以下のファイルがあればそっちが優先
    #   それ以外についてはパスが短い方を優先
    candidates = []
    for file_path in dir_path.rglob(file_name):
        parts_lower = [s.lower() for s in file_path.parts]
        if "bin" in parts_lower:
            score = len(file_path.parts) - 100
        else:
            score = len(file_path.parts)
        candidates.append((score, file_path))

    # 候補が１つも無ければ None を返す
    if not candidates:
        return None

    # 候補からスコアが最も低いものを選択
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def _run(args: list[Any]) -> subprocess.CompletedProcess[str]:
    """
    コマンドを実行する
    ffmpeg 呼び出し用のヘルパ
    """
    # 引数を str で統一
    args_str = [str(v) for v in args]
    return subprocess.run(
        args_str,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _detect_h264_encoder(ffmpeg_path: Path) -> str:
    """
    ffmpeg で使用可能な H.264 エンコーダを検出する。
    優先順位は NVENC > QSV > AMF
    """
    # ffmpeg にエンコーダを問い合わせ
    cp = _run([ffmpeg_path, "-hide_banner", "-encoders"])
    encoders_str = cp.stdout + "\n" + cp.stderr

    # 問い合わせ結果をパース
    encoders: set[str] = set()
    for line in encoders_str.splitlines():
        m = re.search(r"\b(h264_\w+)\b", line)
        if m:
            encoders.add(m.group(1))

    # 候補とヒットしたらそれを返す
    CANDIDATES = ("h264_nvenc", "h264_qsv", "h264_amf")
    for cand in CANDIDATES:
        if cand in encoders:
            return cand

    # 見つからなかったら例外
    raise RuntimeError(
        f"H.264 hardware encoder not found {CANDIDATES}. "
        f"This BTBN lgpl build does not include libx264, so software H.264 may be unavailable."
    )


class FFmpeg:
    """
    ffmpeg による連番静止画の動画エンコードをラップするクラス。
    ポータブル版 ffmpeg をダウンロードしてそれを呼び出す。
    """

    def __init__(self):
        """
        コンストラクタ
        """
        # ffmpeg をインストール
        self._ffmpeg_path = FFmpeg.ensure_ffmpeg()

        # エンコーダーを決定
        self._encoder = _detect_h264_encoder(self._ffmpeg_path)

        # 試行する引数を展開
        # NOTE
        #   環境依存で合法な引数が変わるので、最初はリッチに、ダメなら最小構成で。
        QUALITY = 24
        if self._encoder == "h264_nvenc":
            self._extra_args = [
                # 推奨（CQベースのVBR）
                [
                    "-c:v",
                    "h264_nvenc",
                    "-rc",
                    "vbr",
                    "-cq",
                    str(QUALITY),
                    "-b:v",
                    "0",
                    "-preset",
                    "p5",
                ],
                # 最低限
                ["-c:v", "h264_nvenc"],
            ]
        elif self._encoder == "h264_qsv":
            self._extra_args = [
                # QSV は -global_quality が通りやすい（値は概ね“品質パラメータ”）
                [
                    "-c:v",
                    "h264_qsv",
                    "-global_quality",
                    str(QUALITY),
                    "-preset",
                    "medium",
                ],
                ["-c:v", "h264_qsv"],
            ]
        elif self._encoder == "h264_amf":
            self._extra_args = [
                # AMF は rc/qp 系が環境差大きいので、まずはCQP寄せ
                [
                    "-c:v",
                    "h264_amf",
                    "-rc",
                    "cqp",
                    "-qp_i",
                    str(QUALITY),
                    "-qp_p",
                    str(QUALITY),
                    "-quality",
                    "speed",
                ],
                ["-c:v", "h264_amf"],
            ]
        else:
            raise ValueError(f"Unexpected encoder ({self._encoder})")

    @classmethod
    def ensure_ffmpeg(cls) -> Path:
        """
        ffmpeg を呼び出し可能な状態にする
        内部的にはダウンロードして展開してるだけ
        ffmpeg.exe のパスを返す
        """
        # すでに ffmpeg があるならそれを使う
        ffmpeg_exe_file_path = _find_file_under_dir(FFMPEG_DIR_PATH, "ffmpeg.exe")
        if ffmpeg_exe_file_path:
            return ffmpeg_exe_file_path

        # 展開先をクリア
        if FFMPEG_DIR_PATH.exists():
            shutil.rmtree(FFMPEG_DIR_PATH)
        FFMPEG_DIR_PATH.mkdir(parents=True, exist_ok=True)

        # zip をダウンロード
        ffmpeg_zip_file_path = FFMPEG_DIR_PATH / "ffmpeg.zip"
        _download_file(
            BTBN_LATEST_WIN64_LGPL_ZIP,
            ffmpeg_zip_file_path,
        )

        # zip を展開
        _extract_zip(ffmpeg_zip_file_path, FFMPEG_DIR_PATH)

        # ffmpeg.exe のパスを返す
        ffmpeg_exe_file_path = _find_file_under_dir(FFMPEG_DIR_PATH, "ffmpeg.exe")
        if ffmpeg_exe_file_path:
            return ffmpeg_exe_file_path
        else:
            raise FileNotFoundError(f"ffmpeg.exe not found under {FFMPEG_DIR_PATH}")

    def encode(
        self, dest_file_path: Path, frames: list[Image.Image], frame_rate: float
    ):
        """
        frames を mp4(h264) エンコードして dest_file_path に保存する。
        """
        # 空はエラー
        if not frames:
            raise ValueError("frames is empty")

        # フレームのサイズチェック
        head_frame = frames[0]
        for frame_index, frame in enumerate(frames[1:]):
            if frame.size != head_frame.size:
                raise ValueError(
                    f"Frame size missmatch (head={head_frame.size}, index={frame_index}, frame={frame.size})"
                )

        # エンコード
        with tempfile.TemporaryDirectory(prefix=f"{APP_NAME_EN}_ffmpeg_frames") as td:
            # 全てのフレームを png で保存する
            # TODO できれば .webp (lossless) で保存したい...
            for frame_index, frame in enumerate(frames):
                frame_png_path = Path(td) / f"{frame_index:06d}.png"
                smart_pil_save(
                    frame_png_path,
                    frame,
                    duration_in_msec=None,
                    metadata=ContentsMetadata(),
                    lossless=True,
                    quality_ratio=0.0,
                    encode_speed_ratio=1.0,
                )

            # 基本コマンド
            base_args = [
                str(self._ffmpeg_path),
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-framerate",
                str(frame_rate),
                "-i",
                Path(td) / "%06d.png",
                "-vf",
                "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-an",  # 音声なし
            ]

            # ffmpeg 実行
            last_error = None
            for extra_args in self._extra_args:
                try:
                    _run(base_args + extra_args + [dest_file_path])
                    return
                except Exception as e:
                    last_error = e
                    continue

            # 全部失敗
            raise RuntimeError(
                f"ffmpeg encode failed with encoder={self._encoder}"
            ) from last_error
