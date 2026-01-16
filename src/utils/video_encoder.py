# std
from pathlib import Path
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
from utils.user_properties import USER_PROPERTIES
from utils.ais_logging import write_log


_H264_ENCODERS_CACHE: set[str] = set()


def _enumerate_encoders(ffmpeg_path: Path) -> set[str]:
    """
    ffmpeg で使用可能なエンコーダを列挙する。
    """
    # ユーザープロパティで指定があればそれをロード
    override = USER_PROPERTIES.get("h264_encoder", [])
    if override:
        return set(override)
    # キャッシュがあればそれを使う
    global _H264_ENCODERS_CACHE
    if _H264_ENCODERS_CACHE:
        return _H264_ENCODERS_CACHE
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
    pat = re.compile(r"([VAS\.])[F\.][S\.][X\.][B\.][D\.]\s+(\w+)")
    for line in encoders_str.splitlines():
        m = pat.search(line)
        if m and m.group(1) == "V":
            encoders.add(m.group(2))
    # キャッシュに保存
    _H264_ENCODERS_CACHE = encoders
    # 正常終了
    return encoders


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
    encoders = _enumerate_encoders(ffmpeg_path)

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
    #   エンコード速度の観点で x264 は対象外としたので LGPL 版 ffmpeg でも動く。
    #   優先順位は、ディスクリート GPU へのオフロードを期待できる順にして、
    #    h264_nvenc(nvidia) > h264_amf(AMD) > h264_qsv(Intel)
    #   とした。
    # NOTE
    #   環境依存で合法な引数が変わるので、最初は細かく指定をしたリッチな引数を試す。
    #   リッチ引数が全滅したら、エンコーダだけを指定した最小構成でリトライする。
    #   最小構成も全部失敗したら、関数として完全に失敗。
    # NOTE
    #   基本方針は「低速エンコード、高画質、可変ビットレート」
    #   その心は、
    #   - ハードウェア支援を受けられるから、重たい設定でも比較的高速にエンコードされるはず
    #   - ストリーミングじゃないので、ビットレートを一定にする意味はない
    #   - ごく短い動画の出力を想定していて、投稿先サービスのサイズ上限に引っかかることはまず無いだろうから、ファイルサイズは多少膨らんでも良い
    # fmt: off
    detailed_extra_args: list[list[str]] = []
    compat_extra_args: list[list[str]] = []
    if "h264_nvenc" in encoders:
        # NVIDIA NVENC
        # NOTE
        #   NVENC は個別パラメータ設定がちゃんと聞く
        detailed_extra_args.append([
            "-c:v", "h264_nvenc",
            "-preset", "p7",
            "-profile", "main", # 互換性重視
            "-multipass", "fullres",
            "-rc", "vbr_hq",
            "-cq", "19", # 低いほうが画質が良い
            "-b:v", "0",
            "-rc-lookahead", "20", # 推奨レンジ 10 ~ 20　で、めいいっぱい攻めても 32 くらい
            "-spatial-aq", "1",
            "-aq-strength", "10", # 値域は 1 ~ 15
            "-temporal-aq", "1",
            "-bf", "4" # 値域は -1 ~ 16 で、lookahead 有効なら 4 が推奨
        ])
        compat_extra_args.append([
            "-c:v", "h264_nvenc"
        ])
    if "h264_amf" in encoders:
        # AMD AMF
        # NOTE
        #   AMF は個別パラメータ指定を無視されやすい。
        #   細かいチューンは不毛なので、全面的にプリセットに任せる。
        #   なお、このプリセット設定も本当に効いてるかどうか分からない。
        detailed_extra_args.append([
            "-c:v", "h264_amf",
            "-usage", "high_quality",
            "-profile", "main", # 互換性重視
            "-quality", "quality",
            "-preset", "quality",
        ])
        compat_extra_args.append([
            "-c:v", "h264_amf"
        ])
    if "h264_qsv" in encoders:
        # INTEL QVS
        # NOTE
        #   ハードがないのでテストしてない。
        #   だれか助けて。
        detailed_extra_args.append([
            "-c:v", "h264_qsv",
            "-preset", "veryslow",
            "-global_quality", "19"
        ])
        compat_extra_args.append([
            "-c:v", "h264_qsv"
        ])
    # fmt: on

    # 試行引数リストを結合
    extra_args = detailed_extra_args + compat_extra_args
    if not extra_args:
        raise RuntimeError("h264 HW encoder is not available in this machine.")

    # ffmpeg 実行
    last_error = None
    for ea in extra_args:
        cmd = base_args + ea + [dest_file_path]
        try:
            # プロセス起動
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1024 * 1024,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if proc.stdin is None:
                raise ValueError("subprocess stdin is None")
            # フレームをパイプに流し込む
            # NOTE
            #   ffmpeg 側で何か失敗があったら、途中でパイプが壊れることもある。
            #   ので stdin への流し込み中のエラーはすべて飲み込む。
            try:
                for frame in frames:
                    if proc.returncode is not None:
                        raise RuntimeError("Cancel to feed frames into stdin")
                    proc.stdin.write(frame.tobytes())
            except Exception as e:
                write_log("error", "Failed to feed frames into stdin.", exception=e)
            proc.stdin.close()
            # 実行結果を処理
            out, _ = proc.communicate()
            out_str = out.decode("utf-8", "replace")
            if proc.returncode != 0:
                raise RuntimeError(out_str)
            # 正常終了
            write_log(
                "info", f"Succeded to ffmpeg encode with {ea}\nout_str:\n{out_str}"
            )
            return
        except Exception as e:
            write_log(
                "warning",
                f"video_encode_h264: fallback to next setting.",
                exception=e,
            )
            last_error = e
            continue

    # 全部失敗
    raise RuntimeError(f"ffmpeg encode failed with all candidated") from last_error


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
