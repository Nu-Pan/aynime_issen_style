# std
from typing import Tuple, Optional, Union, Self, Any, cast
from enum import Enum
from dataclasses import dataclass
from enum import Enum, auto
from math import gcd

# PIL
from PIL import Image
from PIL.ImageTk import PhotoImage

# numpy
import numpy as np

# scikit
from skimage.metrics import structural_similarity as ssim

# util
from utils.constants import THUMBNAIL_HEIGHT


class AspectRatioPattern(Enum):
    """
    典型的なアスペクト比の列挙値
    """

    E_RAW = "RAW"  # オリジナルのアスペクト比をそのまま使う
    E_16_9 = "16:9"
    E_4_3 = "4:3"
    E_1_1 = "1:1"


class AspectRatio:
    """
    アスペクト比を表すクラス
    """

    def __init__(self, width: Optional[int], height: Optional[int]):
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
        if pattern == AspectRatioPattern.E_RAW:
            return AspectRatio(None, None)
        elif pattern == AspectRatioPattern.E_16_9:
            return AspectRatio(16, 9)
        elif pattern == AspectRatioPattern.E_4_3:
            return AspectRatio(4, 3)
        elif pattern == AspectRatioPattern.E_1_1:
            return AspectRatio(1, 1)
        else:
            raise ValueError()

    @property
    def name(self) -> str:
        """
        人間用の名前を返す
        """
        return self._name

    @property
    def width(self) -> Optional[int]:
        """
        アスペクト比の水平方向成分
        """
        return self._width

    @property
    def height(self) -> Optional[int]:
        """
        アスペクト比の垂直方向成分
        """
        return self._height

    @property
    def size(self) -> Optional[Tuple[int, int]]:
        """
        スペクト比の水平・垂直方向成分を返す
        """
        if self._width is not None and self._height is not None:
            return (self._width, self._height)
        else:
            return None

    def __eq__(self, other: Any) -> bool:
        """
        比較演算子
        """
        if isinstance(other, AspectRatio):
            return self.width == other.width and self.height == other.height
        else:
            raise TypeError()


class ResizeDesc:
    """
    リサイズの挙動を記述するクラス。
    """

    class Pattern(Enum):
        """
        典型的な解像度を定義する列挙型
        横幅だけを定義する
        """

        E_RAW = "RAW"  # オリジナルの解像度をそのまま使う
        E_HVGA = "320"  # 320
        E_VGA = "640"  # 640
        E_QHD = "960"  # 960
        E_HD = "1280"  # 1280
        E_FHD = "1920"  # 1920
        E_3K = "2880"  # 2880
        E_4K = "3840"  # 3840

    def __init__(
        self,
        aspect_ratio: Union[AspectRatioPattern, AspectRatio],
        width: Optional[int],
        height: Optional[int],
    ):
        """
        コンストラクタ
        """
        # アス比をインスタンスで統一
        if isinstance(aspect_ratio, AspectRatioPattern):
            aspect_ratio = AspectRatio.from_pattern(aspect_ratio)

        # メンバー保存
        self._aspect_ratio = aspect_ratio
        self._width = width
        self._height = height

    @classmethod
    def from_pattern(
        cls,
        aspect_ratio: Union[AspectRatioPattern, AspectRatio],
        pattern: "ResizeDesc.Pattern",
    ) -> "ResizeDesc":
        """
        パターン列挙値からインスタンスを生成する。
        記述を簡略化するためのヘルパー関数。
        """
        # アス比をインスタンスで統一
        if isinstance(aspect_ratio, AspectRatioPattern):
            aspect_ratio = AspectRatio.from_pattern(aspect_ratio)

        # ResizeDesc のインスタンスを生成
        if pattern == ResizeDesc.Pattern.E_RAW:
            return ResizeDesc(aspect_ratio, None, None)
        else:
            return ResizeDesc(aspect_ratio, int(pattern.value), None)

    def resolve(self, source_width: int, source_height: int) -> Tuple[int, int]:
        """
        サイズ (source_width, source_height) の画像をリサイズする場合の適切な目標サイズを解決する。

        指定アスペクト比、指定サイズ、入力サイズの３種類の情報を統合する必要がある。
        基本的なルールは
        矛盾する指定が来た場合は例外を投げる。
        """
        # エイリアス
        desc_ar = self._aspect_ratio.size
        desc_width = self._width
        desc_height = self._height

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
            actual_width = desc_width
            actual_height = desc_height
        elif desc_width is not None and desc_height is None:
            actual_width = desc_width
            actual_height = round(desc_width * actual_ar_height / actual_ar_width)
        elif desc_width is None and desc_height is not None:
            actual_width = round(desc_height * actual_ar_width / actual_ar_height)
            actual_height = desc_height
        elif desc_width is None and desc_height is None:
            actual_width = source_width
            actual_height = source_height
        else:
            raise RuntimeError("Logic Error")

        # 正常終了
        return (actual_width, actual_height)

    def __eq__(self, other):
        """
        中身で一致を判定する
        """
        if isinstance(other, ResizeDesc):
            return (
                self._aspect_ratio == other._aspect_ratio
                and self._width == other._width
                and self._height == other._height
            )
        else:
            return NotImplemented


class ResizeMode(Enum):
    """
    リサイズの挙動を表す列挙値
    """

    # (width, height) のボックス内に image 全体が収まるように image をリサイズする
    CONTAIN = auto()

    # image の範囲内に (width, height) のボックスがちょうど収まるように image をリサイズする
    COVER = auto()


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
    def empty(cls, mode: str, width: int, height: int) -> "AISImage":
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
        target_width, target_height = resize_desc.resolve(image.width, image.height)

        # スケール後のサイズを解決
        width_scale = target_width / image.width
        height_scale = target_height / image.height
        if min(width_scale, height_scale) > 1.0:
            actual_width = image.width
            actual_height = image.height
        elif width_scale < height_scale:
            actual_width = target_width
            actual_height = int(image.height * target_width / image.width + 0.5)
        else:
            actual_width = int(image.width * target_height / image.height + 0.5)
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
        target_width, target_height = resize_desc.resolve(image.width, image.height)

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
            ResizeDesc(AspectRatioPattern.E_RAW, actual_width, actual_height),
            ResizeMode.COVER,
        )
        image_B = image_B.resize(
            ResizeDesc(AspectRatioPattern.E_RAW, actual_width, actual_height),
            ResizeMode.COVER,
        )

    # ndarray 化
    np_image_A = np.array(image_A.grayscale)
    np_image_B = np.array(image_B.grayscale)

    # ssim の計算処理を呼び出す
    ssim_result = ssim(np_image_A, np_image_B, full=True)

    # 結果をデコード
    if isinstance(ssim_result, tuple) and isinstance(ssim_result[0], float):
        score = ssim_result[0]
    else:
        raise TypeError()

    # 正常終了
    return score
