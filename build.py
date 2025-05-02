import subprocess
import zipfile
import shutil
from datetime import datetime
from pathlib import Path


# 設定
APP_NAME = 'aynime_issen_style'
SPEC_FILE = 'main.spec'
DIST_DIR = Path('dist')
BUILD_DIR = Path('build')
ZIP_OUTPUT_DIR = Path('release')


def clean_build_artifacts():
    print('🧹 古いビルドを削除中...')
    for path in [BUILD_DIR, DIST_DIR]:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def run_pyinstaller():
    print('🔧 PyInstaller ビルド中...')
    subprocess.run(['pyinstaller', '--noconfirm', SPEC_FILE], check=True)


def zip_executable():
    print('📦 ZIP 圧縮中...')

    # 日付付きファイル名
    date_str = datetime.now().strftime('%Y%m%d')
    zip_name = f'{APP_NAME}_{date_str}.zip'

    # 出力フォルダを確保
    ZIP_OUTPUT_DIR.mkdir(exist_ok=True)

    # 圧縮対象ファイル
    exe_path = DIST_DIR / f'{APP_NAME}.exe'
    zip_path = ZIP_OUTPUT_DIR / zip_name

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, arcname=f'{APP_NAME}.exe')

    print(f'✅ 完了: {zip_path}')


def main():
    clean_build_artifacts()
    run_pyinstaller()
    zip_executable()


if __name__ == '__main__':
    main()
