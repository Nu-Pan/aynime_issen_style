# std
from typing import Any, cast, Self, Callable
from enum import Enum, auto
from math import gcd
from pathlib import Path
import json, zlib, base64
from xml.sax import saxutils
from dataclasses import dataclass
from zipfile import ZipFile
import re

# PIL
from PIL import Image, ImageOps, ImageFile
from PIL.PngImagePlugin import PngInfo
from PIL.ImageTk import PhotoImage

# numpy
import numpy as np

# scikit
from skimage.metrics import structural_similarity as ssim

# utils
from utils.constants import *
from utils.duration_and_frame_rate import DFR_MAP
from utils.ais_logging import write_log


class AspectRatioPattern(Enum):
    """
    典型的なアスペクト比の列挙値
    """

    E_16_9 = "16:9"
    E_4_3 = "4:3"
    E_1_1 = "1:1"
    E_RAW = "RAW"  # オリジナルのアスペクト比をそのまま使う


class AspectRatio:
    """
    アスペクト比を表すクラス
    """

    def __init__(self, width: int | None, height: int | None):
        """
        コンストラクタ
        指定されたアスペクト比を約分した状態で保持する
        """
        # アスペクト比
        if width is None and height is None:
            self._width = None
            self._height = None
        elif width is not None and height is not None:
            den = gcd(width, height)
            self._width = width // den
            self._height = height // den
        else:
            raise

        # 名前
        if self._width is None and self._height is None:
            self._name = "RAW"
        else:
            self._name = f"{self._width}:{self._height}"

    @classmethod
    def from_pattern(cls, pattern: AspectRatioPattern) -> "AspectRatio":
        """
        パターン列挙値からインスタンスを生成する
        """
        if pattern == AspectRatioPattern.E_16_9:
            return AspectRatio(16, 9)
        elif pattern == AspectRatioPattern.E_4_3:
            return AspectRatio(4, 3)
        elif pattern == AspectRatioPattern.E_1_1:
            return AspectRatio(1, 1)
        elif pattern == AspectRatioPattern.E_RAW:
            return AspectRatio(None, None)
        else:
            raise TypeError(f"Invalid AspectRatioPattern(pattern={pattern})")

    @property
    def pattern(self) -> AspectRatioPattern:
        """
        パターン列挙値へ変換する
        """
        # マッチするパターンを整形探索
        for pattern in AspectRatioPattern:
            if self == AspectRatio.from_pattern(pattern):
                return pattern
        # どれともマッチしなかったらエラー
        raise TypeError(
            f"Aspect ratio not matched for AspectRatioPattern (self={self})"
        )

    @property
    def name(self) -> str:
        """
        人間用の名前を返す
        """
        return self._name

    @property
    def width(self) -> int | None:
        """
        アスペクト比の水平方向成分
        """
        return self._width

    @property
    def height(self) -> int | None:
        """
        アスペクト比の垂直方向成分
        """
        return self._height

    @property
    def size(self) -> tuple[int, int] | None:
        """
        スペクト比の水平・垂直方向成分を返す
        """
        if self._width is not None and self._height is not None:
            return (self._width, self._height)
        else:
            return None

    def __str__(self) -> str:
        """
        人間優しい文字列にする
        """
        readable_width = "*" if self._width is None else str(self._width)
        readable_height = "*" if self._height is None else str(self._height)
        return f"{readable_width}:{readable_height}"

    def __eq__(self, other: Any) -> bool:
        """
        比較演算子
        """
        if isinstance(other, AspectRatio):
            return self.width == other.width and self.height == other.height
        elif isinstance(other, AspectRatioPattern):
            return self == AspectRatio.from_pattern(other)
        elif isinstance(other, str):
            return self == AspectRatioPattern(other)
        else:
            raise TypeError(f"other is not AspectRatio(other={other})")


class ResolutionPattern(Enum):
    """
    典型的な解像度を定義する列挙型
    横幅だけを定義する
    """

    E_DISCORD_EMOJI = "128"  # Dsicord 絵文字の上限
    E_DISCORD_STAMP = "320"  # 320
    E_VGA = "640"  # 640
    E_QHD = "960"  # 960
    E_HD = "1280"  # 1280
    E_FHD = "1920"  # 1920
    E_3K = "2880"  # 2880
    E_4K = "3840"  # 3840
    E_X_TWITTER_STILL_LIMIT = "4096"  # X(Twitter) の静止画の上限サイズ（長辺側）
    E_RAW = "RAW"  # オリジナルの解像度をそのまま使う


class Resolution:
    """
    解像度を表すクラス
    """

    def __init__(self, width: int | None, height: int | None, name: str | None = None):
        """
        コンストラクタ
        """
        self._width = width
        self._height = height
        if name is None:
            if width is None and height is None:
                self._name = "RAW"
            elif width is not None:
                self._name = str(width)
            elif height is not None:
                self._name = str(height)
        else:
            self._name = name

    @classmethod
    def from_pattern(cls, pattern: ResolutionPattern) -> "Resolution":
        """
        パターン列挙値からインスタンスを生成する
        """
        if pattern == ResolutionPattern.E_DISCORD_EMOJI:
            return Resolution(128, None, "DISCORD EMOJI")
        elif pattern == ResolutionPattern.E_DISCORD_STAMP:
            return Resolution(320, None, "DISCORD STAMP")
        elif pattern == ResolutionPattern.E_VGA:
            return Resolution(640, None, "640")
        elif pattern == ResolutionPattern.E_QHD:
            return Resolution(960, None, "960")
        elif pattern == ResolutionPattern.E_HD:
            return Resolution(1280, None, "1280")
        elif pattern == ResolutionPattern.E_FHD:
            return Resolution(1920, None, "1920")
        elif pattern == ResolutionPattern.E_3K:
            return Resolution(2880, None, "2880")
        elif pattern == ResolutionPattern.E_4K:
            return Resolution(3840, None, "3840")
        elif pattern == ResolutionPattern.E_X_TWITTER_STILL_LIMIT:
            # NOTE X(Twitetr) は長辺 4096 が上限なので、ここだけ width, height 両方を指定する
            return Resolution(4096, 4096, "X(Twitter) STILL LIMIT")
        elif pattern == ResolutionPattern.E_RAW:
            return Resolution(None, None, "RAW")
        else:
            raise TypeError(f"Invalid ResolutionPattern(pattern={pattern})")

    @property
    def pattern(self) -> ResolutionPattern:
        """
        解像度パターンに変換する
        """
        # マッチするパターンを整形探索
        for pattern in ResolutionPattern:
            if self == Resolution.from_pattern(pattern):
                return pattern
        # どれともマッチしなかったらエラー
        raise TypeError(f"Resolution not matched for ResolutionPattern (self={self})")

    @property
    def name(self) -> str:
        """
        人間用の名前を返す
        """
        return self._name

    @property
    def width(self) -> int | None:
        """
        水平方向解像度
        """
        return self._width

    @property
    def height(self) -> int | None:
        """
        垂直方向解像度
        """
        return self._height

    def __str__(self) -> str:
        """
        人間優しい文字列にする
        """
        readable_width = "*" if self._width is None else str(self._width)
        readable_height = "*" if self._height is None else str(self._height)
        return f"{readable_width}x{readable_height}"

    def __eq__(self, other: Any) -> bool:
        """
        比較演算子
        """
        if isinstance(other, Resolution):
            return self.width == other.width and self.height == other.height
        elif isinstance(other, ResolutionPattern):
            return self == Resolution.from_pattern(other)
        elif isinstance(other, str):
            return self == ResolutionPattern(other)
        else:
            raise TypeError(f"other is not Resolution(other={other})")


class ResizeMode(Enum):
    """
    リサイズの挙動を表す列挙値
    """

    # (width, height) のボックス内に image 全体が収まるように image をリサイズする
    CONTAIN = auto()

    # image の範囲内に (width, height) のボックスがちょうど収まるように image をリサイズする
    COVER = auto()


class ResizeDesc:
    """
    リサイズの挙動を記述するクラス。
    """

    def __init__(
        self,
        aspect_ratio: AspectRatio | AspectRatioPattern,
        resolution: Resolution | ResolutionPattern,
    ):
        """
        コンストラクタ
        """
        # アス比をインスタンスで統一
        if isinstance(aspect_ratio, AspectRatioPattern):
            aspect_ratio = AspectRatio.from_pattern(aspect_ratio)

        # 解像度をインスタンスで統一
        if isinstance(resolution, ResolutionPattern):
            resolution = Resolution.from_pattern(resolution)

        # メンバー保存
        self._aspect_ratio = aspect_ratio
        self._resolution = resolution

    @property
    def aspect_ratio(self) -> AspectRatio:
        """
        要求アスペクト比を取得する
        """
        return self._aspect_ratio

    @property
    def resolution(self) -> Resolution:
        """
        要求解像度を取得する
        """
        return self._resolution

    def resolve(
        self, source_width: int, source_height: int, mode: ResizeMode
    ) -> tuple[int, int]:
        """
        サイズ (source_width, source_height) の画像をリサイズする場合の適切な目標サイズを解決する。

        指定アスペクト比、指定サイズ、入力サイズの３種類の情報を統合する必要がある。
        基本的なルールは
        矛盾する指定が来た場合は例外を投げる。
        """
        # エイリアス
        desc_ar = self._aspect_ratio.size
        desc_width = self._resolution.width
        desc_height = self._resolution.height

        # 実際のアスペクト比を解決する
        if desc_ar is not None:
            actual_ar = AspectRatio(*desc_ar)
        elif desc_width is not None and desc_height is not None:
            actual_ar = AspectRatio(desc_width, desc_height)
        else:
            actual_ar = AspectRatio(source_width, source_height)

        # 外枠のサイズを解決する
        actual_ar_width = cast(int, actual_ar.width)
        actual_ar_height = cast(int, actual_ar.height)
        if desc_width is not None and desc_height is not None:
            if desc_ar is None:
                actual_width = desc_width
                actual_height = desc_height
            else:
                raise ValueError("Aspect Ratio and size collision")
        elif desc_width is not None and desc_height is None:
            actual_width = desc_width
            actual_height = round(desc_width * actual_ar_height / actual_ar_width)
        elif desc_width is None and desc_height is not None:
            actual_width = round(desc_height * actual_ar_width / actual_ar_height)
            actual_height = desc_height
        elif desc_width is None and desc_height is None:
            # TODO アス比指定を無視してる
            if desc_ar is None:
                actual_width = source_width
                actual_height = source_height
            else:
                actual_width_from_width = round(
                    source_height * actual_ar_width / actual_ar_height
                )
                actual_height_from_width = round(
                    source_width * actual_ar_height / actual_ar_width
                )
                if mode == ResizeMode.CONTAIN:
                    if actual_width_from_width > source_width:
                        actual_width = actual_width_from_width
                        actual_height = source_height
                    else:
                        actual_width = source_width
                        actual_height = actual_height_from_width
                elif mode == ResizeMode.COVER:
                    if actual_width_from_width > source_width:
                        actual_width = source_width
                        actual_height = actual_height_from_width
                    else:
                        actual_width = actual_width_from_width
                        actual_height = source_height
                else:
                    raise ValueError("Logic Error")
        else:
            raise RuntimeError("Logic Error")

        # 正常終了
        return (actual_width, actual_height)

    def __str__(self) -> str:
        """
        人間優しい文字列にする
        """
        return f"{self._resolution}({self._aspect_ratio})"

    def __eq__(self, other):
        """
        中身で一致を判定する
        """
        if isinstance(other, ResizeDesc):
            return (
                self._aspect_ratio == other._aspect_ratio
                and self._resolution == other._resolution
            )
        else:
            return NotImplemented


class AISImage:
    """
    えぃにめ一閃流画像クラス
    PIL.Image.Image が使いづらすぎなので、その代替となる画像クラス。
    """

    def __init__(self, source: Image.Image):
        """
        コンストラクタ
        """
        self._pil_image = source
        self._photo_image = None

    @classmethod
    def from_bytes(cls, width: int, height: int, image_bytes: bytes) -> "AISImage":
        """
        bytes から画像を生成する。
        aynime_capture から取得したバッファを前提とする。
        """
        pil_image = Image.frombuffer(
            "RGB", (width, height), image_bytes, "raw", "BGR", 0, 1
        )
        return AISImage(pil_image)

    @classmethod
    def empty(cls, mode: str = "RGB", width: int = 8, height: int = 8) -> "AISImage":
        """
        空の画像を生成する
        """
        return AISImage(Image.new(mode, (width, height)))

    @property
    def width(self) -> int:
        """
        画像の横幅
        """
        return self._pil_image.width

    @property
    def height(self) -> int:
        """
        画像の高さ
        """
        return self._pil_image.height

    @property
    def pil_image(self) -> Image.Image:
        """
        中身の PIL 画像を取得
        中身に対する in-place 処理は禁止なので注意
        """
        return self._pil_image

    @property
    def photo_image(self) -> PhotoImage:
        """
        中身の PhotoImage を取得
        """
        # 無ければ生成
        if self._photo_image is None:
            self._photo_image = PhotoImage(self._pil_image)

        # 正常終了
        return self._photo_image

    def __eq__(self, other: Any) -> bool:
        """
        他画像と「一致」するなら True
        画像同士の比較はオブジェクト ID の一致で代替
        """
        if isinstance(other, AISImage):
            return self._pil_image is other._pil_image
        elif isinstance(other, Image.Image):
            return self._pil_image is other
        elif other is None:
            return False
        else:
            raise TypeError(f"Invalid type {type(other)}")

    def resize_contain(self, resize_desc: ResizeDesc) -> "AISImage":
        """
        (width, height) のボックス内に image 全体が収まるようにリサイズする。
        リサイズ前後でアスペクト比は維持される。
        拡大は行われない。

        Args:
            target_width (int): リサイズ後のサイズ（横）
            target_height (int): リサイズ後のサイズ（縦）

        Returns:
            AISImage: リサイズ後の画像
        """
        # エイリアス
        image = self._pil_image

        # 目標サイズを解決
        target_width, target_height = resize_desc.resolve(
            image.width, image.height, ResizeMode.CONTAIN
        )

        # スケール後のサイズを解決
        width_scale = target_width / image.width
        height_scale = target_height / image.height
        if min(width_scale, height_scale) > 1.0:
            actual_width = image.width
            actual_height = image.height
        elif width_scale < height_scale:
            actual_width = target_width
            actual_height = round(image.height * target_width / image.width)
        else:
            actual_width = round(image.width * target_height / image.height)
            actual_height = target_height

        # スケール不要ならコピーを返す
        if actual_width == image.width and actual_height == image.height:
            return AISImage(image.copy())

        # リサイズして返す
        return AISImage(
            image.resize(
                (actual_width, actual_height),
                Image.Resampling.LANCZOS,
                reducing_gap=2.0,
            )
        )

    def resize_cover(self, resize_desc: ResizeDesc) -> "AISImage":
        """
        self の範囲内に (width, height) のボックスがちょうど収まるように self をリサイズする。
        リサイズ前後でアスペクト比は維持される。
        はみ出た分はカットされる。
        拡大・縮小両方が行われる。

        Args:
            target_width (int): リサイズ後のサイズ（横）
            target_height (int): リサイズ後のサイズ（縦）

        Returns:
            AISImage: リサイズ後の画像
        """
        # エイリアス
        image = self._pil_image

        # 目標サイズを解決
        target_width, target_height = resize_desc.resolve(
            image.width, image.height, ResizeMode.COVER
        )

        # スケール後のサイズを解決
        width_scale = target_width / image.width
        height_scale = target_height / image.height
        if width_scale > height_scale:
            pre_crop_width = target_width
            pre_crop_height = image.height * target_width // image.width
        else:
            pre_crop_width = image.width * target_height // image.height
            pre_crop_height = target_height

        # スケーリング
        # NOTE
        #   まずはアスペクト比を維持したスケーリングを行う
        #   スケール不要ならコピーを返す
        if pre_crop_width == image.width and pre_crop_height == image.height:
            scaled_image = image
        else:
            scaled_image = image.resize(
                (pre_crop_width, pre_crop_height),
                Image.Resampling.LANCZOS,
                reducing_gap=2.0,
            )

        # 切り取り
        croped_image = scaled_image.crop(
            (
                scaled_image.width // 2 - target_width // 2,
                scaled_image.height // 2 - target_height // 2,
                scaled_image.width // 2 + target_width // 2,
                scaled_image.height // 2 + target_height // 2,
            )
        )

        # 正常終了
        return AISImage(croped_image)

    def resize(self, resize_desc: ResizeDesc, mode: ResizeMode) -> "AISImage":
        """
        image を target_size にリサイズする
        リサイズの挙動は mode に従う

        Args:
            target_size (Union[SizePixel, SizePattern]): リサイズ先サイズ
            mode (ResizeMode): リサイズ挙動

        Returns:
            AISImage: リサイズ済み画像
        """
        if mode == ResizeMode.CONTAIN:
            return self.resize_contain(resize_desc)
        elif mode == ResizeMode.COVER:
            return self.resize_cover(resize_desc)
        else:
            raise ValueError(mode)

    @property
    def grayscale(self) -> "AISImage":
        """
        グレースケール画像を生成
        """
        return AISImage(self._pil_image.convert("L"))


def calc_ssim(image_A: AISImage, image_B: AISImage) -> float:
    """
    ２枚の画像の差分を撮って、１ピクセルあたりの輝度誤差を計算する

    Args:
        image_A (AISImage): 比較対象 A
        image_B (AISImage): 比較対象 B

    Returns:
        float: 平均ピクセル誤差
    """
    # 画像にサイズ差がある場合は小さい方に合わせる
    if image_A.width != image_B.width or image_A.height != image_B.height:
        actual_width = min(image_A.width, image_B.width)
        actual_height = min(image_A.height, image_B.height)
        image_A = image_A.resize(
            ResizeDesc(
                AspectRatioPattern.E_RAW, Resolution(actual_width, actual_height)
            ),
            ResizeMode.COVER,
        )
        image_B = image_B.resize(
            ResizeDesc(
                AspectRatioPattern.E_RAW, Resolution(actual_width, actual_height)
            ),
            ResizeMode.COVER,
        )

    # ndarray 化
    np_image_A = np.array(image_A.grayscale.pil_image)
    np_image_B = np.array(image_B.grayscale.pil_image)

    # ssim の計算処理を呼び出す
    ssim_result = ssim(np_image_A, np_image_B, full=True)

    # 結果をデコード
    if isinstance(ssim_result, tuple) and isinstance(ssim_result[0], float):
        score = ssim_result[0]
    else:
        raise TypeError()

    # 正常終了
    return score


def apply_color_palette(pil_frames: list[Image.Image]) -> list[Image.Image]:
    """
    pil_frames にカラーパレットを適用する
    カラーパレットは pil_frames 全体から計算され、これが全フレームに適用される。
    """
    # フレームの横幅を解決
    frame_width = {f.width for f in pil_frames}
    if len(frame_width) == 1:
        frame_width = frame_width.pop()
    else:
        raise ValueError("Multiple frame width contaminated.")

    # フレームの高さを解決
    frame_height = {f.height for f in pil_frames}
    if len(frame_height) == 1:
        frame_height = frame_height.pop()
    else:
        raise ValueError("Multiple frame height contaminated.")

    # すべての NIME フレームを１つの atlas 画像に結合
    nime_atlas = Image.new(
        "RGB", (frame_width, frame_height * len(pil_frames)), color=None
    )
    for frame_index, nime_frame in enumerate(pil_frames):
        nime_atlas.paste(nime_frame, (0, frame_index * frame_height))

    # atlas 画像を 256 色パレット化
    # NOTE
    #   ちらつき対策として 6bit 量子化を先にやる
    #   メディアンフィルタは輪郭線がちらつく原因になるので却下
    #   FASTOCTREE はフリッカーが出やすい傾向があったので却下
    #   kmeans は品質と速度の兼ね合いで 2 にした
    nime_atlas = ImageOps.posterize(nime_atlas, bits=6)
    nime_atlas = nime_atlas.quantize(
        colors=256, method=Image.Quantize.MEDIANCUT, kmeans=2
    )
    nime_atlas = nime_atlas.convert("P", dither=Image.Dither.NONE, colors=256)
    atlas_palette = nime_atlas.getpalette()
    if atlas_palette is None:
        raise TypeError("Failed to getpalette")

    # atlas から 256 色パレット化された NIME 画像を切り出す
    out_pil_frames: list[Image.Image] = []
    for frame_index in range(len(pil_frames)):
        pil_cropped_frame = nime_atlas.crop(
            (
                0,
                frame_index * frame_height,
                frame_width,
                (frame_index + 1) * frame_height,
            )
        )
        pil_cropped_frame.putpalette(atlas_palette)
        out_pil_frames.append(pil_cropped_frame)

    # 正常終了
    return out_pil_frames


def is_video_file(file_path: Path) -> bool:
    """
    file_path がビデオなら True を返す
    """
    # 静画・動画を判定
    # NOTE
    #   webp, png はどっちもありえるので、ヘッダで判断する。
    #   それ以外は拡張子で判断する。
    if file_path.suffix in [".webp", ".png"]:
        with Image.open(file_path) as im:
            return getattr(im, "is_animated", False) and getattr(im, "n_frames", 1) > 1
    elif file_path.suffix.lower() in ALL_STILL_INOUT_SUFFIXES:
        return False
    elif file_path.suffix.lower() in ALL_VIDEO_INOUT_SUFFIXES:
        return True
    else:
        raise ValueError(
            f"Unsupported file type. Only extensions {ALL_CONTENT_INOUT_SUFFIXES} are supported."
        )


class PlaybackMode(Enum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    REFLECT = "REFLECT"


class ExportTarget(Enum):
    UNKNOWN = "Unknown"
    DISCORD_POST = "Discord Post"
    DISCORD_EMOJI = "Discord Emoji"
    DISCORD_STAMP = "Discord Stamp"
    X_TWITTER = "X(Twitter)"


class ContentsMetadata:
    """
    一閃流が出力するスチル・ビデオファイルに格納されるメタデータ
    シリアライズ・デシリアライズの挙動をこのクラスで記述する
    """

    _PREFIX = f"aismeta1:zlib+b64:"
    _XMP_NAME_SPACE = "ais"
    _XMP_PROPERTY_PATH = f"{_XMP_NAME_SPACE}:metadata_body"
    _XMP_PROPERTY_RE = re.compile(_XMP_PROPERTY_PATH + r'="([^"]*)"')

    def __init__(
        self,
        *,
        _overlay_nime_name: Any = None,
        _crop_params: Any = None,
        _resize_aspect_ratio_pattern: Any = None,
        _resize_resolution_pattern: Any = None,
        _playback_mode: Any = None,
        _disabled_frame_indices: Any = None,
        **_ignored: Any,
    ):
        """
        コンストラクタ

        NOTE
            ファイルから読み出されたメタデータ dict がそのまま渡されることを想定している
            キーが足りてなければ、デフォルト値にフォールバックする
            値が合法でなければ、デフォルト値にフォールバックする
        """
        # NIME 名オーバーレイ表示可否
        if isinstance(_overlay_nime_name, bool):
            self._overlay_nime_name = _overlay_nime_name
        else:
            self._overlay_nime_name = None

        # 正方形切り出し設定
        # NOTE
        #   pylance が型情報をうまく拾ってくれないので cast でダメ押し
        if (
            isinstance(_crop_params, list)
            and len(_crop_params) == 3
            and all(isinstance(x, float) or x is None for x in _crop_params)
        ):
            self._crop_params = cast(
                tuple[float | None, float | None, float | None], tuple(_crop_params)
            )
        else:
            self._crop_params = None

        # リサイズアス比
        try:
            self._resize_aspect_ratio_pattern = AspectRatioPattern(
                _resize_aspect_ratio_pattern
            )
        except:
            self._resize_aspect_ratio_pattern = None

        # リサイズ解像度
        try:
            self._resize_resolution_pattern = ResolutionPattern(
                _resize_resolution_pattern
            )
        except:
            self._resize_resolution_pattern = None

        # 再生モード
        try:
            self._playback_mode = PlaybackMode(_playback_mode)
        except:
            self._playback_mode = None

        # フレーム個別無効化
        if isinstance(_disabled_frame_indices, set) and all(
            isinstance(x, int) for x in _disabled_frame_indices
        ):
            self._disabled_frame_indices = _disabled_frame_indices
        else:
            self._disabled_frame_indices = None

        # TODO _ignored がある場合は警告出す

    @property
    def overlay_nime_name(self) -> bool | None:
        return self._overlay_nime_name

    def set_overlay_nime_name(self, overlay_nime_name: bool | None) -> Self:
        self._overlay_nime_name = overlay_nime_name
        return self

    @property
    def crop_params(self) -> tuple[float | None, float | None, float | None] | None:
        return self._crop_params

    def set_crop_params(
        self, crop_params: tuple[float | None, float | None, float | None] | None
    ) -> Self:
        self._crop_params = crop_params
        return self

    @property
    def resize_aspect_ratio_pattern(self) -> AspectRatioPattern | None:
        return self._resize_aspect_ratio_pattern

    def set_resize_aspect_ratio_pattern(
        self, resize_aspect_ratio_pattern: AspectRatioPattern | None
    ) -> Self:
        self._resize_aspect_ratio_pattern = resize_aspect_ratio_pattern
        return self

    @property
    def resize_resolution_pattern(self) -> ResolutionPattern | None:
        return self._resize_resolution_pattern

    def set_resize_resolution_pattern(
        self, resize_resolution_pattern: ResolutionPattern | None
    ) -> Self:
        self._resize_resolution_pattern = resize_resolution_pattern
        return self

    @property
    def playback_mode(self) -> PlaybackMode | None:
        return self._playback_mode

    def set_playback_mode(self, playback_mode: PlaybackMode | None) -> Self:
        self._playback_mode = playback_mode
        return self

    @property
    def disable_frame_indices_is_none(self) -> bool:
        return self._disabled_frame_indices is None

    def is_frame_enable(self, frame_index: int) -> bool:
        if self._disabled_frame_indices is None:
            return True
        else:
            return frame_index not in self._disabled_frame_indices

    def set_frame_enable(self, frame_index: int, frame_enable: bool) -> Self:
        # 無効化フレーム集合がある状態にする
        if self._disabled_frame_indices is None:
            self._disabled_frame_indices = set()
        # 集合を編集
        if frame_enable:
            if frame_index in self._disabled_frame_indices:
                self._disabled_frame_indices.remove(frame_index)
        else:
            self._disabled_frame_indices.add(frame_index)
        # 正常終了
        return self

    def erase_frame_enable(self):
        self._disabled_frame_indices = None

    @property
    def to_str(self) -> str:
        """
        str にシリアライズする
        """

        # 型変換ヘルパー
        def _sanitize_vars(
            d: dict[str, Any],
            k: str,
            c: Callable[
                [
                    Any,
                ],
                Any,
            ],
        ) -> None:
            if k in d and d[k] is not None:
                d[k] = c(d[k])

        # メンバーを dict 化
        # NOTE
        #   値は json シリアライズ可能な型に変換する
        metadata_dict = dict(vars(self))
        _sanitize_vars(metadata_dict, "_resize_aspect_ratio_pattern", lambda v: v.value)
        _sanitize_vars(metadata_dict, "_resize_resolution_pattern", lambda v: v.value)
        _sanitize_vars(metadata_dict, "_playback_mode", lambda v: v.value)
        _sanitize_vars(metadata_dict, "_disabled_frame_indices", lambda v: list(v))

        # 　シリアライズ
        # NOTE
        #   要件としては…
        #   - 文字コード関連のトラブルを避けたいので base64 エンコードしたい
        #   - ファイルサイズ増大を避けたいから zip 圧縮したい
        #   で、結果的に、
        #   dict --> str(json) --> bytes(zip) --> str(base64)
        #   という流れに落ち着いた。
        metadata_body = json.dumps(
            metadata_dict,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        metadata_body = metadata_body.encode("utf-8")
        metadata_body = zlib.compress(metadata_body, level=9)
        metadata_body = ContentsMetadata._PREFIX + base64.b64encode(
            metadata_body
        ).decode("ascii")
        # 正常終了
        return metadata_body

    @property
    def to_xmp(self) -> bytes:
        """
        xmp 用にシリアライズする
        """
        # NOTE
        #   namespace 内にプロパティが１つあるだけの簡単な構造
        #   プロパティの中身は to_str をそのまま使う
        #   to_str が返すのは base64 エンコード済みなので XMP エスケープは不要
        xmp_body = (
            f"""<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">"""
            f"""<rdf:Description xmlns:{ContentsMetadata._XMP_NAME_SPACE}="https://example.com/aynime/1.0/" {ContentsMetadata._XMP_PROPERTY_PATH}="{self.to_str}" />"""
            f"""</rdf:RDF>"""
        )
        return xmp_body.encode("utf-8")

    @classmethod
    def from_str(cls, body: str | bytes | bytearray) -> "ContentsMetadata":
        """
        str からデシリアライズする
        途中失敗した場合はデフォルト値でフォールバック
        """
        # 入力を str に統一
        if isinstance(body, str):
            body_str = body
        elif isinstance(body, (bytes, bytearray)):
            body_str = body.decode("ascii", errors="strict")
        else:
            raise TypeError(f"Invalid type of body ({type(body)})")

        # プリフィックスが想定通りかチェック
        actual_prefix = body_str[: len(ContentsMetadata._PREFIX)]
        if actual_prefix != ContentsMetadata._PREFIX:
            # NOTE
            #   外部画像をロードした場合、 一閃流と関係ないコメントが入ってくる可能性がある。
            #   普通にありえる話なので、正常系とみなしてログは出さない。
            return ContentsMetadata()

        # デシリアライズ
        try:
            result = body_str[len(ContentsMetadata._PREFIX) :]
            result = base64.b64decode(result)
            result = zlib.decompress(result).decode("utf-8")
            result = json.loads(result)
        except:
            write_log(
                "warning",
                f"Failed to deserialize contents metadata (body_str={body_str})",
            )
            return ContentsMetadata()

        # メンバー復元ヘルパー
        def _restore_vars(d: dict[str, Any], k: str, c: Callable[[Any], Any]) -> None:
            if k in d and d[k] is not None:
                d[k] = c(d[k])

        # json の都合で無毒化されているメンバを復元する
        _restore_vars(
            result, "_resize_aspect_ratio_pattern", lambda v: AspectRatioPattern(v)
        )
        _restore_vars(
            result, "_resize_resolution_pattern", lambda v: ResolutionPattern(v)
        )
        _restore_vars(result, "_playback_mode", lambda v: PlaybackMode(v))
        _restore_vars(result, "_disabled_frame_indices", lambda v: set(v))

        # 正常終了
        return ContentsMetadata(**result)

    @classmethod
    def from_xmp(cls, body: bytes | bytearray) -> "ContentsMetadata":
        """
        xmp からデシリアライズする
        """
        # str にデコード
        try:
            body_str = body.decode("utf-8", errors="replace")
        except:
            write_log("warning", f"Failed to decode contents metadata bytes")
            return ContentsMetadata()

        # 正規表現でパース
        property_match = ContentsMetadata._XMP_PROPERTY_RE.search(body_str)
        if not property_match:
            # NOTE
            #   外部画像をロードした場合、 一閃流と関係ない XMP が入ってくる可能性がある。
            #   普通にありえる話なので、正常系とみなしてログは出さない。
            return ContentsMetadata()

        # comment 版に転送
        return ContentsMetadata.from_str(property_match.group(1))


def smart_pil_save(
    file_path: Path,
    contents: Image.Image | AISImage | list[Image.Image] | list[AISImage],
    *,
    duration_in_msec: int | None,
    metadata: ContentsMetadata,
    lossless: bool,
    quality_ratio: float,
    encode_speed_ratio: float,
):
    """
    contents を file_path に保存する。
    実質的には PIL.Image.Image.save のラッパー。

    contents:
        スチル画像 or 連番スチル画像
        これをファイル保存する

    duration_in_msec:
        ビデオ表示時の更新周期
        スチルの場合は無視される

    metadata:
        ファイルに持たせるメタデータ

    lossless:
        False: 非可逆圧縮
        True: 可逆圧縮

    quality_ratio:
        lossless = False:
            画質
            [0.0, 1.0] で指定する
            大きいほど高品質
        lossless = True:
            圧縮レベル
            [0.0, 1.0] で指定する
            大きいほど高圧縮

    encode_speed_ratio: float
        エンコード速度
        [0.0, 1.0] で指定する
        大きいほど高速にエンコードできるが、圧縮率・画質が低下する
    """

    # duration 解決ヘルパ
    def _resolve_duration_in_msec(
        resolution_in_msec: int,
    ) -> int:
        # ここに処理が回ってきたということは動画パターンなので duration は必須
        if duration_in_msec is None:
            raise ValueError("duration_in_msec is None")
        else:
            result = duration_in_msec
        # 分解能を適用
        if resolution_in_msec > 1:
            result = round(result / resolution_in_msec) * resolution_in_msec
        # 正常終了
        return result

    # 指定された比率を PIL 引数に変換する関数
    def _ratio_to_pil_param(param_min: int, param_max: int, ratio: float):
        raw_param = round(ratio * (param_max - param_min) + param_min)
        return max(param_min, min(param_max, raw_param))

    # PIL Image に統一する関数
    def _to_pil_image(any_image: Any) -> Image.Image:
        if isinstance(any_image, Image.Image):
            return any_image
        elif isinstance(any_image, AISImage):
            return any_image.pil_image
        else:
            raise TypeError(f"Invalid image type (any_image={type(any_image)})")

    # 入力を PIL Image で統一
    if isinstance(contents, AISImage):
        contents = contents.pil_image
    if isinstance(contents, list):
        contents = [_to_pil_image(f) for f in contents]

    # 引数の指定内容で分岐
    suffix = file_path.suffix
    if suffix == ".png" and isinstance(contents, Image.Image) and lossless:
        # still png
        png_info = PngInfo()
        png_info.add_itxt(APP_NAME_EN, metadata.to_str, zip=False)
        contents.save(
            str(file_path),
            optimize=True,
            compress_level=_ratio_to_pil_param(0, 9, quality_ratio),
            pnginfo=png_info,
        )
    elif suffix == ".png" and isinstance(contents, list) and lossless:
        # video png (Animated PNG)
        png_info = PngInfo()
        png_info.add_itxt(APP_NAME_EN, metadata.to_str, zip=False)
        contents[0].save(
            str(file_path),
            save_all=True,
            append_images=contents[1:],
            duration=_resolve_duration_in_msec(1),
            loop=0,
            disposal=0,
            blend=0,  # TODO チューニング
            optimize=True,
            compress_level=_ratio_to_pil_param(0, 9, quality_ratio),
            pnginfo=png_info,
        )
    elif suffix == ".jpg" and isinstance(contents, Image.Image) and not lossless:
        # still jpg
        contents.save(
            str(file_path),
            quality=_ratio_to_pil_param(0, 95, quality_ratio),
            subsampling=0,
            optimize=True,
            progressive=True,
            comment=metadata.to_str,
        )
    elif (
        file_path.suffix == ".webp"
        and isinstance(contents, Image.Image)
        and not lossless
    ):
        # still webp (lossy)
        quality = _ratio_to_pil_param(0, 100, quality_ratio)
        contents.save(
            str(file_path),
            lossless=False,
            quality=quality,
            alpha_quality=quality,
            method=_ratio_to_pil_param(0, 6, 1.0 - encode_speed_ratio),
            exact=False,  # 透明画素の RGB 値は保持しない
            xmp=metadata.to_xmp,
        )
    elif file_path.suffix == ".webp" and isinstance(contents, list) and lossless:
        # video webp (lossless)
        quality = _ratio_to_pil_param(0, 100, quality_ratio)
        contents[0].save(
            str(file_path),
            save_all=True,
            append_images=contents[1:],
            duration=_resolve_duration_in_msec(1),
            loop=0,  # 無限ループ
            lossless=True,
            quality=quality,
            alpha_quality=quality,
            method=_ratio_to_pil_param(0, 6, 1.0 - encode_speed_ratio),
            exact=True,  # バイトレベルの可逆性を保証したいので、透明画素の RGB 値を保持する
            xmp=metadata.to_xmp,
        )
    elif file_path.suffix == ".avif" and isinstance(contents, list) and not lossless:
        # avif
        contents[0].save(
            str(file_path),
            save_all=True,
            append_images=contents[1:],
            duration=_resolve_duration_in_msec(1),
            quality=_ratio_to_pil_param(0, 100, quality_ratio),
            subsampling="4:2:0",
            speed=_ratio_to_pil_param(0, 10, encode_speed_ratio),
            range="full",
            codec="auto",
            xmp=metadata.to_xmp,
        )
    elif file_path.suffix == ".gif" and isinstance(contents, list) and not lossless:
        # gif
        # NOTE
        #   gif の仕様として更新周期の分解能は 10 msec
        #   チラつき防止のため、全フレームで共通のパレットを使う
        contents = apply_color_palette(contents)
        contents[0].save(
            str(file_path),
            save_all=True,
            append_images=contents[1:],
            duration=_resolve_duration_in_msec(10),
            loop=0,
            disposal=0,
            optimize=False,
            comment=metadata.to_str,
        )
    else:
        raise ValueError(
            f"Unsupported combination (suffix={file_path.suffix}, type(content)={type(contents)}, lossless={lossless})"
        )


@dataclass
class SmartPILLoadResult:
    contents: Image.Image | list[Image.Image]
    duration_in_msec: int | None
    metadata: ContentsMetadata


def smart_pil_load(
    file_path: Path,
) -> SmartPILLoadResult:
    """
    smart_pil_save と対応するロード関数
    file_path をロードする
    """
    # zip の場合特別処理
    # NOTE
    #   以前のバージョンでは raw video を zip で保存していたので、
    #   後方互換性のために zip をサポートする。
    if file_path.suffix == ".zip":
        # zip をパースして画像を取得
        pil_frames: list[Image.Image] = []
        frame_enable_list: list[bool] = []
        with ZipFile(file_path, "r") as zip_file:
            for file_name in zip_file.namelist():
                # ステムを抽出
                # NOTE
                #   拡張子が想定通りじゃない場合はスキップ
                file_name = Path(file_name)
                if file_name.suffix not in RAW_STILL_INOUT_SUFFIXES:
                    continue
                # フレームの有効・無効を解決する
                # NOTE
                #   ファイル名から解決する
                #   なんかおかしい時は何も言わずに有効扱いする
                enable_match = re.search(r"_([de])$", file_name.stem)
                if enable_match is None:
                    frame_enable = True
                else:
                    enable_str = enable_match.group(1)
                    if enable_str == "d":
                        frame_enable = False
                    else:
                        frame_enable = True
                # パース結果を保存
                pil_frames.append(Image.open(zip_file.open(file_name.name)))
                frame_enable_list.append(frame_enable)
        # 結果を返す
        return SmartPILLoadResult(
            pil_frames,
            DFR_MAP.default_entry.duration_in_msec,
            ContentsMetadata(frame_enable=frame_enable_list),
        )

    # メタデータロードヘルパ
    # NOTE
    #   フォーマットによって取得方法が違うが、スチル・ビデオは関係しない
    #   何らかの理由でロードに失敗した場合はデフォルト値を返す
    def _load_metadata(image_file: ImageFile.ImageFile) -> ContentsMetadata:
        file_suffix = file_path.suffix
        if file_suffix in [".webp", ".avif"]:
            xmp_body = image_file.info.get("xmp")
            if isinstance(xmp_body, (bytes, bytearray)):
                return ContentsMetadata.from_xmp(xmp_body)
            else:
                write_log(
                    "warning",
                    f"Unexpected XMP object (file={image_file.filename}, xmp_body={type(xmp_body)})",
                )
                return ContentsMetadata()
        elif file_suffix in [".jpg", ".gif"]:
            comment_body = image_file.info.get("comment")
            if isinstance(comment_body, (bytes, bytearray)):
                return ContentsMetadata.from_str(comment_body)
            else:
                write_log(
                    "warning",
                    f"Unexpected comment object (file={image_file.filename}, xmp_body={type(comment_body)})",
                )
                return ContentsMetadata()
        elif file_suffix in [".png"]:
            # itxt を取り出す
            # NOTE 大抵は info に居るが text も見に行く
            itxt_body = image_file.info.get(APP_NAME_EN)
            if itxt_body is None and hasattr(image_file, "text"):
                itxt_body = vars(image_file)["text"].get(APP_NAME_EN)
            # メタデータへ
            if isinstance(itxt_body, (str, bytes, bytearray)):
                return ContentsMetadata.from_str(itxt_body)
            else:
                write_log(
                    "warning",
                    f"Unexpected itxt object (file={image_file.filename}, xmp_body={type(itxt_body)})",
                )
                return ContentsMetadata()
        else:
            write_log(
                "warning",
                f"Unexpected contents suffix (file={image_file.filename})",
            )
            return ContentsMetadata()

    # ロード
    contents: Image.Image | list[Image.Image]
    if is_video_file(file_path):  # ビデオ
        # ファイルから読み出す
        contents = []
        delays: list[int] = []
        with Image.open(file_path) as image_file:
            # フレームを取り出す
            try:
                while True:
                    contents.append(image_file.copy())
                    delay = image_file.info.get("duration", None)
                    if delay is not None:
                        delays.append(delay)
                    image_file.seek(image_file.tell() + 1)
            except EOFError:
                pass
            # メタデータを抽出
            metadata = _load_metadata(image_file)
        # アニメーション更新間隔を集計
        if len(delays) >= 1:
            avg_delay = round(sum(delays) / len(delays))
        else:
            avg_delay = None

    else:  # スチル
        # ファイルから読み出す
        with Image.open(file_path) as image_file:
            contents = image_file.copy()
            avg_delay = None
            metadata = _load_metadata(image_file)

    # 正常終了
    return SmartPILLoadResult(contents, avg_delay, metadata)
