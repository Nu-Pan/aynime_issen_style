# std
from pathlib import Path


# アプリ名
APP_NAME_EN = "aynime_issen_style"
APP_NAME_JP = "えぃにめ一閃流奥義「一閃」"

# ウィジェットのパディングサイズ
WIDGET_PADDING = 6

# ウィンドウの最小サイズ
# NOTE
#   16:9 をスチルキャプチャしたときにちょうど良いサイズ。
WINDOW_MIN_WIDTH = 640
WINDOW_MIN_HEIGHT = 480

# ウィンドウの初期サイズ
# NOTE
#   16:9 をビデオキャプチャしたときにちょうど良いサイズ。
WINDOW_INIT_WIDTH = 640
WINDOW_INIT_HEIGHT = 960

# 共通して使用するフォント
DEFAULT_FONT_FAMILY = "Yu Gothic UI"
DEFAULT_FONT_PATH = Path("C:\\Windows\\Fonts\\YuGothM.ttc")
OVERLAY_FONT_FAMILY = "Meiryo UI Bold"
OVERLAY_FONT_PATH = Path("C:\\Windows\\Fonts\\Meiryob.ttc")

# バージョン情報ファイルのパス
VERSION_FILE_PATH = Path("src\\utils\\version_constants.py")

# キャプチャ保存先
# NOTE
#   nime はリサイズなどの処理適用済みの最終結果画像の保存先
#   raw は処理適用前のオリジナルのキャプチャ画像の保存先
NIME_DIR_PATH = Path.cwd() / "nime"
RAW_DIR_PATH = Path.cwd() / "raw"
LOG_DIR_PATH = Path.cwd() / "log"

# サムネイルの高さ方向のサイズ
THUMBNAIL_HEIGHT = 120

# キャプチャフレームバッファの保持秒数
CAPTURE_FRAME_BUFFER_HOLD_IN_SEC = 3.0
