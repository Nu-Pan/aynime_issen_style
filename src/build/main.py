import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from inspect import cleandoc
from pathlib import Path
import shutil

from utils.constants import VERSION_FILE_PATH
from utils.constants import APP_NAME_EN

# 設定
DIST_DIR_PATH = Path(f"dist")
DIST_APP_DIR_PATH = DIST_DIR_PATH / APP_NAME_EN
BUILD_DIR_PATH = Path("build")
WORK_DIR_PATH = BUILD_DIR_PATH / "temp"
SPEC_DIR_PATH = BUILD_DIR_PATH / "spec"
ZIP_OUTPUT_DIR = Path("release")
APP_ICO_FILE_ABS_PATH = Path("app.ico").resolve()


def clean_build_artifacts():
    """
    古い中間・成果物を削除
    """
    for path in [BUILD_DIR_PATH, DIST_DIR_PATH]:
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
            f"--name={APP_NAME_EN}",
            "--onefile",
            "--strip",
            "--noconsole",
            "--log-level=WARN",
            "--collect-binaries=aynime_capture",
            "--collect-submodules=numpy",
            "--collect-submodules=aynime_capture",
            "--collect-data=numpy",
            f"--icon={APP_ICO_FILE_ABS_PATH}",
            f"--add-data={APP_ICO_FILE_ABS_PATH}:.",
            f"--distpath={DIST_APP_DIR_PATH}",
            f"--workpath={WORK_DIR_PATH}",
            f"--specpath={SPEC_DIR_PATH}",
        ],
        check=True,
    )


def zip_executable():
    """
    成果物を zip 圧縮する
    """
    # zip ファイルパスを生成
    date_str = datetime.now().strftime("%Y%m%d")
    zip_file_stem = f"{APP_NAME_EN}_{date_str}"
    zip_file_base_path = ZIP_OUTPUT_DIR / zip_file_stem

    # 出力フォルダを確保
    ZIP_OUTPUT_DIR.mkdir(exist_ok=True)

    # zip ファイルに圧縮
    shutil.make_archive(
        base_name=str(zip_file_base_path), format="zip", root_dir=DIST_DIR_PATH
    )


def main():
    """
    メイン関数
    """
    clean_build_artifacts()
    make_version_file()
    run_pyinstaller()
    zip_executable()


if __name__ == "__main__":
    main()
