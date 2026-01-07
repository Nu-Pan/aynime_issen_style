# std
import os
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
import subprocess
import re
from copy import copy

# PIL
from PIL import Image

# utils
from utils.constants import TOOL_DIR_PATH, APP_NAME_EN
from utils.user_properties import USER_PROPERTIES
from utils.ais_logging import write_log


def _download_file(url: str, dest_file_path: Path) -> None:
    """
    url から dest_dir_path にファイルをダウンロードする。
    """
    try:
        # 定数
        _TIMEOUT_IN_SEC = 10
        _CHUNK_SIZE_IN_BYTES = 1024 * 1024

        # ダウンロード先ディレクトリを作成
        dest_file_path.parent.mkdir(parents=True, exist_ok=True)

        # リクエストを構築
        req = urllib.request.Request(
            url, headers={"User-Agent": f"{APP_NAME_EN}/ensure-web-tool (urllib)"}
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
    except Exception as e:
        write_log("error", f"Failed to download from {url} to {dest_file_path}")
        raise


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


# ファイル検索結果のキャッシュ
_FILE_UNDER_DIR_CACHE: dict[str, Path] = dict()


def _find_file_under_dir(dir_path: Path, file_name: str) -> Path | None:
    """
    dir_path 以下から再帰的に file_name を探す
    """
    # キャッシュがあるならそれを使う
    cache_key = str(dir_path / "**" / file_name)
    if cache_key in _FILE_UNDER_DIR_CACHE:
        return _FILE_UNDER_DIR_CACHE[cache_key]

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
    file_path = candidates[0][1]
    _FILE_UNDER_DIR_CACHE[cache_key] = file_path
    return file_path


def _ensure_web_tool(web_zip_url: str, tool_file_name: str) -> Path:
    """
    Web 上で公開されているツールを使えるようにする。
    ダウンロード --> 展開 --> ツールパス探索

    web_zip_url:
        ダウンロードする zip ファイルの URL

    tool_file_name:
        使用したいツールのファイル名（stem+suffix）

    return:
        ツールパス
    """
    # すでにローカルにツールがあるならそれを使う
    tool_stem = Path(tool_file_name).stem
    tood_dir_path = TOOL_DIR_PATH / tool_stem
    tool_file_path = _find_file_under_dir(tood_dir_path, tool_file_name)
    if tool_file_path:
        return tool_file_path

    # 展開先をクリア
    if tood_dir_path.exists():
        shutil.rmtree(tood_dir_path)
    tood_dir_path.mkdir(parents=True, exist_ok=True)

    # zip をダウンロード
    tool_zip_file_path = tood_dir_path / f"{tool_stem}.zip"
    _download_file(
        web_zip_url,
        tool_zip_file_path,
    )

    # zip を展開
    _extract_zip(tool_zip_file_path, tood_dir_path)
    tool_zip_file_path.unlink()

    # ツールのパスを返す
    tool_file_path = _find_file_under_dir(tood_dir_path, tool_file_name)
    if tool_file_path:
        return tool_file_path
    else:
        raise FileNotFoundError(f"{tool_file_name} not found under {tood_dir_path}")


# fmt: off
DEFAULT_FFMPEG_ZIP_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)
# fmt: on


def ensure_ffmpeg() -> Path:
    """
    ffmpeg を呼び出し可能な状態にする
    ffmpeg.exe のパスを返す
    """
    ffmpeg_zip_url = USER_PROPERTIES.get("ffmpeg_zip_url", DEFAULT_FFMPEG_ZIP_URL)
    return _ensure_web_tool(ffmpeg_zip_url, "ffmpeg.exe")


# fmt: off
DEFAULT_GIFSCICLE_ZIP_URL = (
    "https://eternallybored.org/misc/gifsicle/releases/"
    "gifsicle-1.95-win64.zip"
)
# fmt: on


def ensure_gifsicle() -> Path:
    """
    gifsicle を呼び出し可能な状態にする
    gifsicle.exe のパスを返す
    """
    gifscicle_zip_url = USER_PROPERTIES.get(
        "gifscicle_zip_url", DEFAULT_GIFSCICLE_ZIP_URL
    )
    return _ensure_web_tool(gifscicle_zip_url, "gifsicle.exe")
