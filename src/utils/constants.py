# std
from pathlib import Path


# アプリ名
APP_NAME_EN = "aynime_issen_style"
APP_NAME_JP = "えぃにめ一閃流奥義「一閃」"

# ウィジェットのパディングサイズ
WIDGET_PADDING = 6

# ウィジェットの最小幅
WIDGET_MIN_WIDTH = 60

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
NUMERIC_FONT_FAMILY = "Consolas"
NUMERIC_FONT_PATH = Path("C:\\Windows\\Fonts\\Consolas.ttc")

# バージョン情報ファイルのパス
VERSION_FILE_PATH = Path("src\\utils\\version_constants.py")

# キャプチャ保存先
# NOTE
#   nime はリサイズなどの処理適用済みの最終結果画像の保存先
#   raw は処理適用前のオリジナルのキャプチャ画像の保存先
NIME_DIR_PATH = Path.cwd() / "nime"
TENSEI_DIR_PATH = Path.cwd() / "tensei"
RAW_DIR_PATH = Path.cwd() / "raw"
LOG_DIR_PATH = Path.cwd() / "log"

# サムネイルの高さ方向のサイズ
THUMBNAIL_HEIGHT = 120

# キャプチャフレームバッファの保持秒数
CAPTURE_FRAME_BUFFER_DURATION_IN_SEC = 5

# 拡張子(NIME)
# NOTE
#   OUT:
#       現行バージョンの一閃流が出力する形式
#   INOUT:
#       NIME フォルダ上に存在して良い拡張子
#       歴史的経緯でいろいろな拡張子があり得る
NIME_STILL_OUT_SUFFIX = ".webp"
NIME_STILL_OUT_PIL_FORMAT = "WEBP"
NIME_VIDEO_OUT_SUFFIX = ".avif"
# NIME_VIDEO_OUT_PIL_FORMAT = ...
NIME_STILL_INOUT_SUFFIXES = {NIME_STILL_OUT_SUFFIX, ".jpg", ".jpeg"}
NIME_VIDEO_INOUT_SUFFIXES = {NIME_VIDEO_OUT_SUFFIX, ".gif"}
NIME_CONTENT_INOUT_SUFFIXES = NIME_STILL_INOUT_SUFFIXES | NIME_VIDEO_INOUT_SUFFIXES

# 拡張子(RAW)
RAW_STILL_OUT_SUFFIX = ".png"
RAW_STILL_OUT_PIL_FORMAT = "PNG"
RAW_VIDEO_OUT_SUFFIX = ".webp"
# RAW_VIDEO_OUT_PIL_FORMAT = ...
RAW_STILL_INOUT_SUFFIXES = {RAW_STILL_OUT_SUFFIX}
RAW_VIDEO_INOUT_SUFFIXES = {RAW_VIDEO_OUT_SUFFIX, ".zip"}
RAW_CONTENT_INOUT_SUFFIXES = RAW_STILL_INOUT_SUFFIXES | RAW_VIDEO_INOUT_SUFFIXES

# 拡張子(NIME/RAW)
ALL_STILL_INOUT_SUFFIXES = NIME_STILL_INOUT_SUFFIXES | RAW_STILL_INOUT_SUFFIXES
ALL_VIDEO_INOUT_SUFFIXES = NIME_VIDEO_INOUT_SUFFIXES | RAW_VIDEO_INOUT_SUFFIXES
ALL_CONTENT_INOUT_SUFFIXES = ALL_STILL_INOUT_SUFFIXES | ALL_VIDEO_INOUT_SUFFIXES
