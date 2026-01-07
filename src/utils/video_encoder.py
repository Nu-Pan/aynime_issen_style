# std
from pathlib import Path
from typing import Any
import subprocess
import re
from copy import copy
import threading
import subprocess

# PIL
from PIL import Image

# utils
from utils.ensure_web_tool import ensure_ffmpeg, ensure_gifsicle
from utils.constants import METADATA_KEY
from utils.metadata import ContentsMetadata


def _detect_h264_encoder(ffmpeg_path: Path) -> str:
    """
    ffmpeg で使用可能な H.264 エンコーダを検出する。
    優先順位は NVENC > QSV > AMF
    """
    # ffmpeg にエンコーダを問い合わせ
    cp = subprocess.run(
        [str(ffmpeg_path), "-hide_banner", "-encoders"],
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
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


def video_encode_h264(
    dest_file_path: Path,
    frames: list[Image.Image],
    frame_rate: float,
    metadata: ContentsMetadata,
):
    """
    frames を h264 エンコードして dest_file_path に保存する。
    """
    # 空はエラー
    if not frames:
        raise ValueError("frames is empty")

    # 呼び出し元の変数を壊さないようにコピー
    frames = copy(frames)

    # 先頭フレームの情報を取得
    head_frame = frames[0]
    head_width, head_height = head_frame.size
    head_even_width = head_width - (head_width % 2)
    head_even_height = head_height - (head_height % 2)

    # フレームを h264 エンコード用に正規化
    for i in range(len(frames)):
        # フレームサイズ不一致はエラー
        if (head_width, head_height) != head_frame.size:
            raise ValueError(
                f"Frame size missmatch (head={head_frame.size}, index={i}, frame={frames[i].size})"
            )
        # サイズを偶数化
        width, height = frames[i].size
        if width != head_even_width or height != head_even_height:
            frames[i] = frames[i].crop((0, 0, head_even_width, head_even_height))
        # RGB フォーマット化
        if frames[i].mode != "RGB":
            frames[i] = frames[i].convert("RGB")

    # ツールをインストール
    ffmpeg_path = ensure_ffmpeg()

    # エンコーダーを決定
    encoder = _detect_h264_encoder(ffmpeg_path)

    # 基本コマンド
    # fmt: off
    base_args = [
        str(ffmpeg_path),
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        # 入力関係
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{head_even_width}x{head_even_height}",
        "-r", str(frame_rate),
        "-i", "pipe:0",
        # no audio/subs/data
        "-an",
        "-sn",
        "-dn",
        # 出力関係
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart+use_metadata_tags",
        "-metadata", f"{METADATA_KEY}={metadata.to_str}"
    ]
    # fmt: on

    # 試行する引数を展開
    # NOTE
    #   環境依存で合法な引数が変わるので、最初はリッチに、ダメなら最小構成で。
    # fmt: off
    QUALITY = 24
    if encoder == "h264_nvenc":
        extra_args = [
            # 推奨（CQベースのVBR）
            [
                "-c:v", "h264_nvenc",
                "-rc", "vbr",
                "-cq", str(QUALITY),
                "-b:v", "0",
                "-preset", "p5",
            ],
            # 最低限
            [
                "-c:v", "h264_nvenc"
            ],
        ]
    elif encoder == "h264_qsv":
        extra_args = [
            # QSV は -global_quality が通りやすい（値は概ね“品質パラメータ”）
            [
                "-c:v", "h264_qsv",
                "-global_quality", str(QUALITY),
                "-preset", "medium",
            ],
            [
                "-c:v", "h264_qsv"
            ],
        ]
    elif encoder == "h264_amf":
        extra_args = [
            # AMF は rc/qp 系が環境差大きいので、まずはCQP寄せ
            [
                "-c:v", "h264_amf",
                "-rc", "cqp",
                "-qp_i", str(QUALITY),
                "-qp_p", str(QUALITY),
                "-quality", "speed",
            ],
            [
                "-c:v", "h264_amf"
            ],
        ]
    else:
        raise ValueError(f"Unexpected encoder ({encoder})")
    # fmt: on

    # ffmpeg 実行
    last_error = None
    for extra_args in extra_args:
        cmd = base_args + extra_args + [dest_file_path]
        try:
            # プロセス起動
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1024 * 1024,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if proc.stdin is None:
                raise ValueError("subprocess stdin is None")
            # フレームをパイプに流し込む
            for frame in frames:
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
            # 実行結果を処理
            _, err = proc.communicate()
            err_str = err.decode("utf-8", "replace")
            if proc.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg failed (return code={proc.returncode})\n"
                    f"stderr:\n{err_str}"
                )
            # 正常終了
            return
        except Exception as e:
            last_error = e
            continue

    # 全部失敗
    raise RuntimeError(f"ffmpeg encode failed with encoder={encoder}") from last_error


def _collect_stderr(
    proc: subprocess.Popen[bytes], sink: list[bytes]
) -> threading.Thread:
    """
    パイプが詰まらないよう、別スレッドで proc の stderr を吸い出す
    """

    # 読み出しハンドラ
    def _reader():
        if proc.stderr is None:
            raise ValueError("proc.stderr is None")
        else:
            try:
                sink.append(proc.stderr.read() or b"")
            except Exception:
                sink.append(b"")

    # スレッドを開始
    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    return t


def video_encode_gif(
    dest_file_path: Path,
    frames: list[Image.Image],
    frame_rate: float,
    metadata: ContentsMetadata,
    num_colors: int,
    bayer_scale: int,
):
    """
    frames を gif エンコードして dest_file_path に保存する。
    ffmpeg で gif ファイル化して gifsicle で最適化する。

    dest_file_path:
        出力ファイルパス

    frames:
        エンコードしたいフレーム列

    frame_rate:
        フレームレート

    num_colors:
        gif パレット色数
        最大 256 色まで

    bayer_scale:
        ディザリングのスケール
        0 ... 5 で指定
        0 が最も強烈にディザがかかる
    """
    # 空はエラー
    if not frames:
        raise ValueError("frames is empty")

    # 呼び出し元の変数を壊さないようにコピー
    frames = copy(frames)

    # 先頭フレームの情報を取得
    head_frame = frames[0]
    head_width, head_height = head_frame.size

    # フレームを gif エンコード用に正規化
    for i in range(len(frames)):
        # フレームサイズ不一致はエラー
        if (head_width, head_height) != head_frame.size:
            raise ValueError(
                f"Frame size missmatch (head={head_frame.size}, index={i}, frame={frames[i].size})"
            )
        # RGB フォーマット化
        if frames[i].mode != "RGB":
            frames[i] = frames[i].convert("RGB")

    # ツールをインストール
    ffmpeg_path = ensure_ffmpeg()
    gifsicle_path = ensure_gifsicle()

    # ffmpeg のフィルタを構築
    # NOTE
    #   一閃流の使われ方から考えて、キャラが動いているシーンがメインストリームなはず。
    #   ということは、キャラの階調が足りないとものすごく悪目立ちするはず。
    #   逆に動かない背景は注目度が低いので階調が足りなくてもオタクは気にしなさそう。
    #   つまり、キャラに階調を割くべきなので stats_mode=diff が適切。
    # NOTE
    #   diff_mode は none, rectangle で切り替えても画質・サイズにほとんど変化がなかった。
    #   理論上で言えば rectangle のほうがサイズが小さくなりやすいはずなので、そうした。
    STATS_MODE = "diff"
    DIFF_MODE = "rectangle"
    filter_complex = (
        f"split[a][b];"
        f"[a]palettegen=max_colors={num_colors}:stats_mode={STATS_MODE}[p];"
        f"[b][p]paletteuse=dither=bayer:bayer_scale={bayer_scale}:diff_mode={DIFF_MODE}"
    )

    # ffmpeg のコマンドを構築
    # fmt: off
    ffmpeg_cmd = [
        str(ffmpeg_path),
        "-hide_banner",
        "-loglevel", "error",
        # input: rawvideo from stdin
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{head_width}x{head_height}",
        "-framerate", str(frame_rate),
        "-i", "pipe:0",
        # no audio/subs/data
        "-an",
        "-sn",
        "-dn",
        # palette pipeline
        "-filter_complex", filter_complex,
        # output GIF to stdout
        "-f", "gif",
        "-loop", "0",
        "pipe:1",
    ]
    # fmt: on

    # gifsicle のコマンドを構築
    # NOTE
    #   --no-comments --comments の同時指定は「消して書く」という意味。
    #   追記じゃないよということを明示しているだけ。
    # fmt: off
    gifsicle_cmd = [
        str(gifsicle_path),
        "--no-comments",
        "--no-names",
        "--no-extensions",
        "--loopcount", # 無限ループ指定
        "--comment", metadata.to_str,
        "-O3",
        "-o", "-", # stdout
        "-", # stdin
        # "--lossy=80",
    ]
    # fmt: on

    # コマンドを実行
    # NOTE
    #   コマンドの入出力はすべてパイプでつなぐ
    ff_err: list[bytes] = []
    gs_err: list[bytes] = []
    with dest_file_path.open("wb") as f_out:
        # ffmpeg のプロセス
        p_ff = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if p_ff.stdin is None:
            raise ValueError("p_ff.stdin is None")
        if p_ff.stdout is None:
            raise ValueError("p_ff.stdout is None")

        # gifsicle のプロセス
        p_gs = subprocess.Popen(
            gifsicle_cmd,
            stdin=p_ff.stdout,
            stdout=f_out,  # 直接ファイルへ（メモリに溜めない）
            stderr=subprocess.PIPE,
            bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # 親プロセス側では ffmpeg の stdout を閉じる（gifsicle 側が読み切る）
        p_ff.stdout.close()

        # パイプが詰まらないように stderr は非同期で読み出す
        t_ff = _collect_stderr(p_ff, ff_err)
        t_gs = _collect_stderr(p_gs, gs_err)

        # ffmpeg に raw RGB を流し込む
        broken_pipe = False
        try:
            for im in frames:
                p_ff.stdin.write(im.tobytes())
        except BrokenPipeError:
            # 下流（ffmpeg or gifsicle）が先に落ちた
            broken_pipe = True
        finally:
            try:
                p_ff.stdin.close()
            except Exception:
                pass

        # 終了待ち（下流から）
        gs_rc = p_gs.wait()
        ff_rc = p_ff.wait()

        # stderr 吸い出しスレッドの停止を待機
        t_gs.join(timeout=1.0)
        t_ff.join(timeout=1.0)

    # BrokenPipeが出たのに成功扱い
    # NOTE
    #   かなりレアなケース
    #   一応ハンドルしておく
    if broken_pipe and (ff_rc == 0 and gs_rc == 0):
        raise RuntimeError(
            "BrokenPipeError occurred but processes returned success. Check tool behavior."
        )

    # 普通に失敗した場合
    if gs_rc != 0 or ff_rc != 0:
        ff_msg = (ff_err[0] if ff_err else b"").decode("utf-8", errors="replace")
        gs_msg = (gs_err[0] if gs_err else b"").decode("utf-8", errors="replace")
        raise RuntimeError(
            "GIF pipeline failed.\n"
            f"[ffmpeg rc={ff_rc}]\n{ff_msg}\n"
            f"[gifsicle rc={gs_rc}]\n{gs_msg}\n"
            f"ffmpeg_cmd={ffmpeg_cmd}\n"
            f"gifsicle_cmd={gifsicle_cmd}\n"
        )
