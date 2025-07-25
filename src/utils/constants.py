# std
from pathlib import Path


# アプリ名
APP_NAME_EN = "aynime_issen_style"
APP_NAME_JP = "えぃにめ一閃流奥義「一閃」"

# ウィジェットのパディングサイズ
WIDGET_PADDING = 4

# ウィンドウの最小サイズ
# NOTE
#   最小サイズであると同時に初期サイズでもある
#   gif タブに事情を合わせて 1:1 になった
WINDOW_MIN_WIDTH = 640
WINDOW_MIN_HEIGHT = 640

# 共通して使用するフォント
DEFAULT_FONT_NAME = "Yu Gothic UI"

# バージョン情報ファイルのパス
VERSION_FILE_PATH = Path("src\\utils\\version_constants.py")

# キャプチャ保存先
# NOTE
#   nime はリサイズなどの処理適用済みの最終結果画像の保存先
#   raw は処理適用前のオリジナルのキャプチャ画像の保存先
NIME_DIR_PATH = Path.cwd() / "nime"
RAW_DIR_PATH = Path.cwd() / "raw"

# デフォルトのフレームレート
DEFAULT_FRAME_RATE = 15

# サムネイルの高さ方向のサイズ
# NOTE
#   本当は DPI に応じてスケールすべき値
#   なんだけど、対応ダルいので定数にしている
THUMBNAIL_HEIGHT = 135
