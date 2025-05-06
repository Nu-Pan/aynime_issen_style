from pathlib import Path


# ウィジェットのパディングサイズ
WIDGET_PADDING = 4

# ウィンドウの最小サイズ
# NOTE
#   最小サイズであると同時に初期サイズでもある
#   いろいろあって 8:5 になった
WINDOW_MIN_WIDTH = 640
WINDOW_MIN_HEIGHT = 400

# 共通して使用するフォント
DEFAULT_FONT_NAME = "Yu Gothic UI"

# バージョン情報ファイルのパス
VERSION_FILE_PATH = Path("src\\utils\\version_constants.py")
