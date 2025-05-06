import subprocess
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from inspect import cleandoc
from pathlib import Path


# 設定
APP_NAME = "aynime_issen_style"
VERSION_FILE_PATH = Path("src\\utils\\version_constants.py")
SPEC_FILE = "main.spec"
DIST_DIR = Path("dist")
BUILD_DIR = Path("build")
ZIP_OUTPUT_DIR = Path("release")


def clean_build_artifacts():
    """
    古い中間・成果物を削除
    """
    for path in [BUILD_DIR, DIST_DIR]:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def make_version_file():
    """
    バージョン情報ファイルを生成する
    """
    # git コミットハッシュ
    commit_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
        text=True,
    ).stdout.strip()

    # ビルド日時
    build_date = datetime.now().strftime("%Y/%m/%d %H:%M")

    # 中身作ってファイルに書き込み
    version_constants_text = f"""
    COMMIT_HASH = '{commit_hash}'
    BUILD_DATE = '{build_date}'
    """
    open(VERSION_FILE_PATH, "w").write(cleandoc(version_constants_text))


def run_pyinstaller():
    """
    pyinstaller を呼び出してビルド
    """
    subprocess.run(
        [
            "pyinstaller",
            "src\\gui\\main.py",
            "--name=aynime_issen_style",
            "--onefile",
            "--strip",
            "--noconsole",
            "--icon=app.ico",
            "--log-level=WARN",
            "--collect-submodules=numpy",
            "--collect-data=numpy",
            "--add-data",
            "app.ico;.",
        ],
        check=True,
    )


def zip_executable():
    """
    成果物を zip 圧縮する
    """
    # 日付付きファイル名
    date_str = datetime.now().strftime("%Y%m%d")
    zip_name = f"{APP_NAME}_{date_str}.zip"

    # 出力フォルダを確保
    ZIP_OUTPUT_DIR.mkdir(exist_ok=True)

    # 圧縮対象ファイル
    exe_path = DIST_DIR / f"{APP_NAME}.exe"
    zip_path = ZIP_OUTPUT_DIR / zip_name

    # 圧縮・保存
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, arcname=f"{APP_NAME}.exe")


def cleanup_file():
    """
    自動生成されたファイルの後始末
    """
    for p in Path(".").glob("*.spec"):
        p.unlink()


def main():
    """
    メイン関数
    """
    clean_build_artifacts()
    make_version_file()
    run_pyinstaller()
    zip_executable()
    cleanup_file()


if __name__ == "__main__":
    main()
