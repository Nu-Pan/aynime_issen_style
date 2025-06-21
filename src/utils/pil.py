# std
from typing import Tuple, Optional
from enum import Enum

# PIL
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

# numpy
import numpy as np

# scikit
from skimage.metrics import structural_similarity as ssim


class AspectRatio(Enum):
    """
    アスペクト比を定義する列挙型
    """

    E_RAW = "RAW"  # オリジナルのアスペクト比をそのまま使う
    E_16_9 = "16:9"
    E_4_3 = "4:3"
    E_1_1 = "1:1"

    @property
    def int_value(self) -> Optional[Tuple[int, int]]:
        """
        列挙値を数値に変換する

        Args:
            default_value (Tuple[int, int]): RAW だった場合のデフォルト値

        Returns:
            Optional[Tuple[int, int]]:
                アスペクト比（横：縦）
                E_RAW の場合 None
        """
        if self == AspectRatio.E_RAW:
            return None
        elif self == AspectRatio.E_16_9:
            return (16, 9)
        elif self == AspectRatio.E_4_3:
            return (4, 3)
        elif self == AspectRatio.E_1_1:
            return (1, 1)
        else:
            raise ValueError(f"Invalid AspectRatio({self})")


class Resolution(Enum):
    """
    典型的な解像度を定義する列挙型
    """

    E_RAW = "RAW"  # オリジナルの解像度をそのまま使う
    E_HVGA = "320"  # 320
    E_VGA = "640"  # 640
    E_QHD = "960"  # 960
    E_HD = "1280"  # 1280
    E_FHD = "1920"  # 1920
    E_3K = "2880"  # 2880
    E_4K = "3840"  # 3840

    @property
    def int_value(self) -> Optional[int]:
        """
        列挙値を数値に変換する

        Returns:
            Optional[Tuple[int, int]]:
                解像度（横：縦）
                E_RAW の場合 None
        """
        if self == Resolution.E_RAW:
            return None
        elif self == Resolution.E_HVGA:
            return 320
        elif self == Resolution.E_VGA:
            return 640
        elif self == Resolution.E_QHD:
            return 960
        elif self == Resolution.E_HD:
            return 1280
        elif self == Resolution.E_FHD:
            return 1920
        elif self == Resolution.E_3K:
            return 2880
        elif self == Resolution.E_4K:
            return 3840
        else:
            raise ValueError(f"Invalid Resolution({self})")


def resolve_target_size(
    source_width: int,
    source_height: int,
    aspect_ratio: AspectRatio,
    resolution: Resolution,
) -> Tuple[int, int]:
    """
    サイズ (source_width, source_height) の画像を
    aspect_ratio, resolution にリサイズする場合の適切な目標サイズを解決する。

    Args:
        source_width (int): 元画像のサイズ（横）
        source_height (int): 元画像のサイズ（縦）
        aspect_ratio (AspectRatio): 目標アスペクト比（パターン）
        resolution (Resolution): 目標解像度（パターン）

    Returns:
        Tuple[int, int]: 目標サイズ（横：縦）
    """
    # アスペクト比を解決
    aspect_ratio_int = aspect_ratio.int_value
    if aspect_ratio_int is None:
        aspect_ratio_int = (source_width, source_height)

    # 幅を解決
    target_width = resolution.int_value
    if target_width is None:
        target_width = source_width

    # 高さを解決
    target_height = target_width * aspect_ratio_int[1] // aspect_ratio_int[0]

    # 正常終了
    return (target_width, target_height)


def resize_contain_free_size(
    image: Image.Image, target_width: int, target_height: int
) -> Image.Image:
    """
    (width, height) のボックス内に image 全体が収まるようにリサイズする。
    リサイズ前後でアスペクト比は維持される。
    拡大は行われない。

    Args:
        image (Image.Image): 元画像
        target_width (int): リサイズ後のサイズ（横）
        target_height (int): リサイズ後のサイズ（縦）

    Returns:
        Image.Image: リサイズ後の画像
    """
    # スケール後のサイズを解決
    width_scale = target_width / image.width
    height_scale = target_height / image.height
    if min(width_scale, height_scale) > 1.0:
        actual_width = image.width
        actual_height = image.height
    elif width_scale < height_scale:
        actual_width = target_width
        actual_height = image.height * target_width // image.width
    else:
        actual_width = image.width * target_height // image.height
        actual_height = target_height

    # スケール不要ならコピーを返す
    if actual_width == image.width and actual_height == image.height:
        return image.copy()

    # リサイズして返す
    return image.resize(
        (actual_width, actual_height), Image.Resampling.LANCZOS, reducing_gap=2.0
    )


def resize_contain_pattern_size(
    image: Image.Image, aspect_ratio: AspectRatio, resolution: Resolution
) -> Image.Image:
    """
    resize_contain_free_size のパターン指定版。
    """
    target_width, target_height = resolve_target_size(
        image.width, image.height, aspect_ratio, resolution
    )
    return resize_contain_free_size(image, target_width, target_height)


def resize_cover_free_size(
    image: Image.Image, target_width: int, target_height: int
) -> Image.Image:
    """
    image の範囲内に (width, height) のボックスがちょうど収まるように image をリサイズする。
    リサイズ前後でアスペクト比は維持される。
    はみ出た分はカットされる。
    拡大・縮小両方が行われる。

    Args:
        image (Image.Image): 元画像
        target_width (int): リサイズ後のサイズ（横）
        target_height (int): リサイズ後のサイズ（縦）

    Returns:
        Image.Image: リサイズ後の画像
    """
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
    return croped_image


def resize_cover_pattern_size(
    image: Image.Image, aspect_ratio: AspectRatio, resolution: Resolution
) -> Image.Image:
    """
    resize_cover_pattern_size のパターン指定版。
    """
    target_width, target_height = resolve_target_size(
        image.width, image.height, aspect_ratio, resolution
    )
    return resize_cover_free_size(image, target_width, target_height)


def get_text_bbox_size(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont
) -> Tuple[float, float]:
    """
    指定された条件でのテキストバウンディングボックスのサイズを返す

    Args:
        draw (ImageDraw.ImageDraw): 描画コンテキスト
        text (str): テキスト
        font (ImageFont.FreeTypeFont): フォント

    Returns:
        Tuple[int, int]: バウンディングボックスの幅・高さ
    """
    x0, y0, x1, y1 = draw.textbbox((0, 0), text, font=font, anchor=None)
    return x1 - x0, y1 - y0


def make_disabled_image(
    source_image: Image.Image, text="DISABLED", darkness=0.35
) -> Image.Image:
    """
    source_image を元に「無効っぽい見た目の画像」を生成する

    Args:
        source_image (Image.Image): 元画像
        text (str, optional): オーバーレイする文字列
        darkness (float, optional): 画像の暗さ

    Returns:
        Image.Image: 無効っぽい見た目の画像
    """
    # 輝度を割合で下げる
    enhancer = ImageEnhance.Brightness(source_image.convert("RGBA"))
    dark_image = enhancer.enhance(darkness)

    # 黒画像を半透明合成して更に暗くする
    w, h = dark_image.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 120))
    dark_image.alpha_composite(overlay)

    # テキストを描画
    draw = ImageDraw.Draw(dark_image)
    font = ImageFont.truetype("arial.ttf", size=h // 8)
    tw, th = get_text_bbox_size(draw, text, font)
    center_w = (w - tw) / 2
    center_h = (h - th) / 2
    center_pos = (center_w, center_h)
    draw.text(center_pos, text, font=font, fill=(255, 255, 255, 230))

    # 正常終了
    return dark_image.convert("RGB")


def calc_ssim(image_A: Image.Image, image_B: Image.Image) -> float:
    """
    ２枚の画像の差分を撮って、１ピクセルあたりの輝度誤差を計算する

    Args:
        image_A (Image.Image): 比較対象 A
        image_B (Image.Image): 比較対象 B

    Returns:
        float: 平均ピクセル誤差
    """
    # 画像にサイズ差がある場合は小さい方に合わせる
    if image_A.width != image_B.width or image_A.height != image_B.height:
        actual_width = min(image_A.width, image_B.width)
        actual_height = min(image_A.height, image_B.height)
        image_A = resize_cover_free_size(image_A, actual_width, actual_height)
        image_B = resize_cover_free_size(image_B, actual_width, actual_height)

    # ndarray 化
    np_image_A = np.array(image_A.convert("L"))
    np_image_B = np.array(image_B.convert("L"))

    # ssim の計算処理を呼び出す
    ssim_result = ssim(np_image_A, np_image_B, full=True)

    # 結果をデコード
    if isinstance(ssim_result, tuple) and isinstance(ssim_result[0], float):
        score = ssim_result[0]
    else:
        raise TypeError()

    # 正常終了
    return score
