# std
from pathlib import Path
from typing import List, Tuple, Optional, Union, cast
from enum import Enum
from zipfile import ZipFile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

# PIL
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

# numpy
import numpy as np

# scikit
from skimage.metrics import structural_similarity as ssim

# utils
from utils.constants import RAW_DIR_PATH, NIME_DIR_PATH


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
    return dark_image


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


class IntegratedImage:
    """
    「統合」された画像を表すデータクラス
    - nime_image: NIME 用の画像（JPEG）
    - raw_image: 元画像（PNG）
    """

    def __init__(self, raw_image: Image.Image):
        """
        コンストラクタ

        Args:
            raw_image (Image.Image): 元画像
        """
        # RAW
        self._raw_image = raw_image

        # NIME
        self._nime_image = None
        self._nime_aspect_ratio = AspectRatio.E_RAW
        self._nime_resolution = Resolution.E_RAW

        # プレビュー
        self._preview_image = None
        self._preview_width = None
        self._preview_height = None

        # サムネ
        self._thumbnail_image_enabled = None
        self._thumbnail_image_disabled = None
        self._thumbnail_width = None
        self._thumbnail_height = None

    def raw(self) -> Image.Image:
        """
        RAW 画像を返す
        色々やる前の元の画像

        Returns:
            Image.Image: 元画像
        """
        return self._raw_image

    def nime(
        self,
        aspect_ratio: Optional[AspectRatio] = None,
        resolution: Optional[Resolution] = None,
    ) -> Image.Image:
        """
        NIME 画像を返す
        エクスポート用の画像

        Args:
            aspect_ratio (Optional[AspectRatio]): アスペクト比
            resolution (Optional[Resolution]): 解像度

        Returns:
            Image.Image: NIME 画像
        """
        # 再生成が不要な場合はキャッシュから返す
        if (
            self._nime_image is not None
            and self._nime_aspect_ratio == aspect_ratio
            and self._nime_resolution == resolution
        ):
            return self._nime_image

        # aspect_ratio, resolution を更新
        if aspect_ratio is not None:
            self._nime_aspect_ratio = aspect_ratio
        if resolution is not None:
            self._nime_resolution = resolution

        # リサイズ済み画像を生成
        self._nime_image = resize_cover_pattern_size(
            self._raw_image, self._nime_aspect_ratio, self._nime_resolution
        )

        # 影響先画像を無効化
        self._preview_image = None
        self._thumbnail_image_enabled = None

        # 正常終了
        return self._nime_image

    def preview(self, width: int, height: int) -> Image.Image:
        """
        プレビュー用の画像を返す
        NIME 画像を指定サイズにリサイズしたもの

        Args:
            width (int): プレビュー用の幅
            height (int): プレビュー用の高さ

        Returns:
            Image.Image: プレビュー用の画像
        """
        # サイズ情報がまったくないのは NG
        if width is None and self._preview_width is None:
            raise ValueError("No width info")
        elif height is None and self._preview_height is None:
            raise ValueError("No height info")

        # キャッシュ画像が存在するか
        cache_available = self._preview_image is not None

        # 画像サイズに変更が必要か
        width_changed = width != self._preview_width
        height_changed = height != self._preview_height

        # 再生成が不要な場合はキャッシュから返す
        use_cache = cache_available or not width_changed or not height_changed
        if use_cache:
            return cast(Image.Image, self._preview_image)

        # 横幅更新
        if width is not None:
            self._preview_width = width
        elif self._preview_width is None:
            raise ValueError("Logic Error")

        # 高さ更新
        if height is not None:
            self._preview_height = height
        elif self._preview_height is None:
            raise ValueError("Logic Error")

        # リサイズ済み画像を生成
        self._preview_image = resize_contain_free_size(
            self.nime(), self._preview_width, self._preview_height
        )

        # 正常終了
        return self._preview_image

    def thumbnail(
        self, enable: bool, width: Optional[int] = None, height: Optional[int] = None
    ) -> Image.Image:
        """
        サムネイル用の画像を返す
        NIME 画像を指定サイズにリサイズしたもの

        Args:
            enable (bool): True なら有効画像、 False なら無効画像を返す
            width (int): サムネイル用の幅
            height (int): サムネイル用の高さ

        Returns:
            Image.Image: サムネイル用の画像
        """
        # サイズ情報がまったくないのは NG
        if width is None and self._thumbnail_width is None:
            raise ValueError("No width info")
        elif height is None and self._thumbnail_height is None:
            raise ValueError("No height info")

        # キャッシュ画像が存在するか
        cache_available = (
            self._thumbnail_image_enabled is not None
            and self._thumbnail_image_disabled is not None
        )

        # 画像サイズに変更が必要か
        width_changed = width != self._thumbnail_width
        height_changed = height != self._thumbnail_height

        # 再生成が不要な場合はキャッシュから返す
        use_cache = cache_available or not width_changed or not height_changed
        if use_cache:
            if enable:
                return cast(Image.Image, self._thumbnail_image_enabled)
            else:
                return cast(Image.Image, self._thumbnail_image_disabled)

        # 横幅更新
        if width is not None:
            self._thumbnail_width = width
        elif self._thumbnail_width is None:
            raise ValueError("Logic Error")

        # 高さ更新
        if height is not None:
            self._thumbnail_height = height
        elif self._thumbnail_height is None:
            raise ValueError("Logic Error")

        # リサイズ済み画像を生成
        self._thumbnail_image_enabled = resize_contain_free_size(
            self.nime(), self._thumbnail_width, self._thumbnail_height
        )
        self._thumbnail_image_disabled = make_disabled_image(
            self._thumbnail_image_enabled
        )

        # 正常終了
        if enable:
            return self._thumbnail_image_enabled
        else:
            return self._thumbnail_image_disabled


def integrated_save_image(
    image: Union[IntegratedImage, List[IntegratedImage]], interval_in_ms: int = 100
) -> Union[Path, List[Path]]:
    """
    image を file_path に保存する。
    画像・動画の両方に対応している。

    動画の場合は、動画のフレームを全て保存する。

    Args:
        image (Union[Image.Image, List[Image.Image]]): 保存したい画像
        file_path (Path): 保存先ファイルパス
        interval_in_ms (int, optional): gif アニメーションのフレーム間隔（ミリ秒）
    """
    # 保存先ディレクトリを生成
    NIME_DIR_PATH.mkdir(parents=True, exist_ok=True)
    RAW_DIR_PATH.mkdir(parents=True, exist_ok=True)

    # ファイル名に使う日時文字列を生成
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # 画像・動画を保存する
    if isinstance(image, IntegratedImage):
        # nime ディレクトリに jpeg 画像を保存
        jpeg_file_path = NIME_DIR_PATH / (date_str + ".jpg")
        image.nime().convert("RGB").save(
            str(jpeg_file_path),
            format="JPEG",
            quality=92,
            optimize=True,
            progressive=True,
        )

        # raw ディレクトリに png 画像を保存
        png_file_path = RAW_DIR_PATH / (date_str + ".png")
        image.raw().convert("RGB").save(
            str(png_file_path),
            format="PNG",
            optimize=True,
            compress_levvel=9,
            transparency=0,
        )

        # 正常終了
        return jpeg_file_path

    elif isinstance(image, list):
        # nime ディレクトリに gif アニメーションを保存
        gif_file_path = NIME_DIR_PATH / (date_str + ".gif")
        image[0].nime().save(
            str(gif_file_path),
            save_all=True,
            append_images=[img.nime() for img in image[1:]],
            duration=interval_in_ms,
            loop=0,
            disposal=2,
            optimize=True,
        )

        # raw ディレクトリに zip ファイルを保存
        zip_file_path = RAW_DIR_PATH / (date_str + ".zip")
        with ZipFile(zip_file_path, "w") as zip_file:
            for idx, img in enumerate(image):
                # png ファイルメモリに書き出し
                buf = BytesIO()
                img.raw().save(buf, format="PNG", optimize=True)
                buf.seek(0)
                # png メモリイメージを zip ファイルに書き出し
                png_file_name = f"{date_str}_{idx:03d}.png"
                zip_file.writestr(png_file_name, buf.read())

        # 正常終了
        return gif_file_path

    else:
        raise TypeError(
            f"Unsupported type: {type(image)}. Expected IntegratedImage or List[IntegratedImage]."
        )


def integrated_load_image(
    file_path: Path,
) -> Union[IntegratedImage, List[IntegratedImage]]:
    """
    file_path から画像を読み込む。
    画像・動画の両方に対応している。

    動画の場合は、動画のフレームを全て読み込んでリストで返す。

    同名のファイルが raw に存在する場合はそちらを読み込み、
    それ以外の場合は file_path そのものを読み込む。

    Args:
        file_path (Path): 読み込み元ファイルパス

    Returns:
        Image.Image: 読み込んだ画像
    """
    # 実際に読み込むべきファイルパスを解決する
    IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")
    MOVIE_EXTENSIONS = (".gif",)
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        raw_png_file_path = RAW_DIR_PATH / (file_path.stem + ".png")
        if raw_png_file_path.exists():
            actual_file_path = raw_png_file_path
        elif file_path.exists():
            actual_file_path = file_path
        else:
            raise FileNotFoundError(f"{raw_png_file_path} or {file_path}")
    elif file_path.suffix.lower in MOVIE_EXTENSIONS:
        raw_zip_file_path = RAW_DIR_PATH / (file_path.stem + ".zip")
        if raw_zip_file_path.exists():
            actual_file_path = raw_zip_file_path
        elif file_path.exists():
            actual_file_path = file_path
        else:
            raise FileNotFoundError(f"{raw_zip_file_path} or {file_path}")
    else:
        raise ValueError(
            f"Unsuported file type. Only extensions {IMAGE_EXTENSIONS + MOVIE_EXTENSIONS} are supported."
        )

    # 画像・動画を読み込む
    if actual_file_path.suffix.lower() in IMAGE_EXTENSIONS:
        # 画像ファイルの場合はそのまま読み込む
        pil_image = Image.open(actual_file_path).convert("RGB")
        return IntegratedImage(pil_image)
    elif actual_file_path.suffix.lower() in MOVIE_EXTENSIONS:
        # 動画ファイルの場合はフレームを全て読み込む
        frames: List[IntegratedImage] = []
        with Image.open(actual_file_path) as img:
            try:
                while True:
                    pil_image = img.copy().convert("RGB")
                    frames.append(IntegratedImage(pil_image))
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
        return frames
    elif actual_file_path.suffix.lower() == ".zip":
        # ZIP ファイルの場合は中身を読み込む
        # NOTE
        #   ZIP ファイルはこのアプリによって出力されたものであることを前提としている
        #   その中身は .png であることを前提としている
        with ZipFile(actual_file_path, "r") as zip_file:
            file_list = zip_file.namelist()
            frames = [
                IntegratedImage(Image.open(zip_file.open(file_name)).convert("RGB"))
                for file_name in file_list
            ]
            return frames
    else:
        raise ValueError("Logic Error")
