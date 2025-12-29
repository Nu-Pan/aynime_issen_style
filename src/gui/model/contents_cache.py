# std
from typing import (
    Callable,
    Generator,
    Self,
    Any,
    cast,
    Iterable,
)
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile, ZIP_STORED
from io import BytesIO
import re
from abc import ABC, abstractmethod
from enum import Enum

# numpy
import numpy as np

# PIL
from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageEnhance,
    ImageFilter,
)

# utils
from utils.image import (
    AspectRatioPattern,
    ResolutionPattern,
    ResizeDesc,
    ResizeMode,
    AISImage,
)
from utils.duration_and_frame_rate import DFR_MAP
from utils.constants import *
from utils.windows import sanitize_text
from utils.std import PerfLogger


type AuxProcess = Callable[[AISImage], AISImage]
type NotifyHandler = Callable[[], None]


class FontCache:
    """
    フォントをキャッシュするクラス
    """

    _cache: dict[float, ImageFont.FreeTypeFont] = dict()

    @classmethod
    def query(cls, font_size: float):
        if font_size in cls._cache:
            return cls._cache[font_size]
        else:
            new_font = ImageFont.truetype(OVERLAY_FONT_PATH, size=font_size)
            cls._cache[font_size] = new_font
            return new_font


_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"


def current_time_stamp() -> str:
    """
    現在時刻からタイムスタンプ文字列を生成（ミリ秒3桁）
    """
    now = datetime.now()
    ms = now.microsecond // 1000  # 0〜999
    return f"{now.strftime(_TIMESTAMP_FORMAT)}_{ms:03d}"


def is_time_stamp(text: str) -> bool:
    """
    text が旧フォーマット or 新フォーマットのタイムスタンプ文字列なら True
    """
    # 新フォーマット（ミリ秒あり）
    m_new = re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_\d{3}", text)
    if m_new:
        return True

    # 旧フォーマット（秒まで）
    m_old = re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", text)
    if m_old:
        return True

    # どちらでもない
    return False


def parse_nime_file_stem(stem: str) -> tuple[str | None, str | None]:
    """
    stem をパースして (アニメ名, タイムスタンプ) を返す。
    NOTE
        最初は新形式を仮定してパースして、ダメだった場合は旧形式を仮定する。
        パースに失敗した要素は None を返す。
    """
    file_stem_match = re.match("(.+)__(.+)", stem)
    if file_stem_match is None:
        nime_name = None
        if is_time_stamp(stem):
            time_stamp = stem
        else:
            time_stamp = None
    else:
        nime_name = file_stem_match.group(1)
        if is_time_stamp(file_stem_match.group(2)):
            time_stamp = file_stem_match.group(2)
        else:
            time_stamp = None
    return nime_name, time_stamp


class CachedContent(ABC):
    """
    キャッシュツリーの基底クラス
    """

    def __init__(self, parent: "CachedContent | None"):
        """
        コンストラクタ
        """
        # メンバ初期化
        self._parent = parent
        self._known_parent_output: Any = None
        self._is_dirty = False

    @property
    def parent_output(self) -> AISImage | None:
        if self._parent is None:
            return None
        else:
            return self._parent.output

    def mark_dirty(self, does_set: bool = True) -> Self:
        """
        ダーティ状態としてマークする
        立てるかどうかを source_state で指定可能
        """
        self._is_dirty |= does_set
        return self

    def mark_resolved(self) -> Self:
        """
        ダーティ状態が解除されたとしてマークする
        """
        if self._parent is not None:
            self._known_parent_output = self._parent.output
        self._is_dirty = False
        return self

    @property
    def is_dirty(self) -> bool:
        """
        ダーティー状態なら True を返す
        """
        # 親の状態を自身のダーティフラグに反映
        if self._parent is not None:
            parent = self._parent
            if parent.is_dirty:
                self.mark_dirty()
            elif parent.output != self._known_parent_output:
                self.mark_dirty()

        # 内部状態を返す
        return self._is_dirty

    @property
    @abstractmethod
    def output(self) -> AISImage | None:
        """
        出力を取得する
        ダーティー状態は暗黙に解決される。
        """
        pass


class CachedSourceImage(CachedContent):
    """
    キャッシュツリーに画像を流し込むための「源泉」に当たるクラス。
    """

    type Output = AISImage

    def __init__(self):
        """
        コンストラクタ
        """
        super().__init__(None)
        self._source = None

    def set_source(self, source: AISImage | None) -> Self:
        """
        ソース画像を設定する
        """
        if self._source != source:
            self.mark_dirty()
            self._source = source
        return self

    @property
    def output(self) -> AISImage | None:
        """
        出力を取得する
        ダーティー状態は暗黙に解決される。
        """
        # NOTE
        #   ソースを素通しなので画像処理は不要
        #   ダーティフラグを下げてソース画像をそのまま返す
        self.mark_resolved()
        return self._source


class CachedCropSquareImage(CachedContent):
    """
    正方形領域の切り出しとそのキャッシュ機能を持つ画像クラス
    """

    type Output = AISImage

    def __init__(self, parent: CachedContent):
        """
        コンストラクタ
        """
        super().__init__(parent)
        self._size_ratio = None
        self._x_ratio = None
        self._y_ratio = None
        self._output: AISImage | None = None

    def set_crop_params(
        self, size_ratio: float | None, x_ratio: float | None, y_ratio: float | None
    ) -> Self:
        """
        切り出しパラメータを設定する
        元画像上のどこを切り出すか？　これを決める
        位置・サイズ共に元画像に対する比率で指定する
        """
        if (
            self._size_ratio != size_ratio
            or self._x_ratio != x_ratio
            or self._y_ratio != y_ratio
        ):
            self._size_ratio = size_ratio
            self._x_ratio = x_ratio
            self._y_ratio = y_ratio
            self.mark_dirty()
        return self

    @property
    def crop_params(self) -> tuple[float | None, float | None, float | None]:
        """
        切り出しパラメータを取得する
        """
        return self._size_ratio, self._x_ratio, self._y_ratio

    @property
    def output(self) -> AISImage | None:
        """
        出力を取得する
        ダーティー状態は暗黙に解決される。
        """
        # ダーティ状態を解消
        if self.is_dirty:
            # 必要なものが…
            parent_output = self.parent_output
            if (
                isinstance(parent_output, AISImage)
                and self._size_ratio is not None
                and self._x_ratio is not None
                and self._y_ratio is not None
            ):
                # すべて揃っている場合、更新
                square_size = self._size_ratio * min(
                    parent_output.width, parent_output.height
                )
                left = self._x_ratio * parent_output.width - square_size / 2
                right = self._x_ratio * parent_output.width + square_size / 2
                if left < 0:
                    left = 0
                    right = square_size
                elif right > parent_output.width:
                    left = parent_output.width - square_size
                    right = parent_output.width
                top = self._y_ratio * parent_output.height - square_size / 2
                bottom = self._y_ratio * parent_output.height + square_size / 2
                if top < 0:
                    top = 0
                    bottom = square_size
                elif bottom > parent_output.height:
                    top = parent_output.height - square_size
                    bottom = parent_output.height
                self._output = AISImage(
                    parent_output.pil_image.crop(
                        (round(left), round(top), round(right), round(bottom))
                    )
                )
            elif isinstance(parent_output, AISImage):
                # 元画像はあるけど切り出しパラメータが未指定なら、パススルー
                self._output = parent_output
            else:
                # 画像すらない場合、単にクリア
                self._output = None
            self.mark_resolved()

        # 正常終了
        return self._output


class CachedScalableImage(CachedContent):
    """
    拡大縮小とそのキャッシュ機能を持つ画像クラス
    """

    type Output = AISImage

    def __init__(
        self,
        parent: CachedContent,
        resize_mode: ResizeMode,
        aux_process: AuxProcess | None = None,
    ):
        """
        コンストラクタ
        """
        # 基底クラス初期化
        super().__init__(parent)

        # 定数
        self._resize_mode = resize_mode
        self._aux_process = aux_process

        # 遅延変数
        self._size = ResizeDesc(AspectRatioPattern.E_RAW, ResolutionPattern.E_RAW)
        self._output = None

    def set_size(self, size: ResizeDesc) -> Self:
        """
        スケーリング後のサイズを設定
        """
        if self._size != size:
            self.mark_dirty()
            self._size = size
        return self

    def set_resize_mode(self, resize_mode: ResizeMode) -> Self:
        """
        リサイズモードを設定
        """
        if self._resize_mode != resize_mode:
            self.mark_dirty()
            self._resize_mode = resize_mode
        return self

    @property
    def size(self) -> ResizeDesc:
        """
        スケーリング後のサイズを取得
        """
        return self._size

    @property
    def resize_mode(self) -> ResizeMode:
        """
        リサイズモードを取得
        """
        return self._resize_mode

    @property
    def output(self) -> AISImage | None:
        """
        スケーリング済み画像
        ダーティー状態は暗黙に解決される。
        """
        # ダーティ状態を解消
        if self.is_dirty:
            # 必要なものが…
            parent_output = self.parent_output
            if parent_output is not None and self._size is not None:
                # 揃っている場合、更新
                if isinstance(parent_output, AISImage):
                    self._output = parent_output.resize(self._size, self._resize_mode)
                else:
                    raise TypeError(type(parent_output))
                if self._aux_process is not None:
                    self._output = self._aux_process(self._output)
                self.mark_resolved()
            else:
                # 揃っていない場合、単にクリア
                self._output = None
                self.mark_resolved()

        # 正常終了
        return self._output


class ImageLayer(Enum):
    """
    ImageModel のレイヤー列挙値
    """

    RAW = "RAW"
    NIME = "NIME"
    PREVIEW = "PREVIEW"
    THUMBNAIL = "THUMBNAIL"


def get_text_bbox_size(
    image_size: tuple[int, int], text: str, font: ImageFont.FreeTypeFont
) -> tuple[int, int]:
    """
    指定された条件でのテキストバウンディングボックスのサイズを返す

    Args:
        draw (ImageDraw.ImageDraw): 描画コンテキスト
        text (str): テキスト
        font (ImageFont.FreeTypeFont): フォント

    Returns:
        tuple[int, int]: バウンディングボックスの幅・高さ
    """
    dummy_image = Image.new("L", image_size, None)
    dummy_draw = ImageDraw.Draw(dummy_image)
    x0, y0, x1, y1 = dummy_draw.textbbox((0, 0), text, font=font, anchor=None)
    return round(x1 - x0), round(y1 - y0)


def make_disabled_image(
    source_image: AISImage, text="DISABLED", darkness=0.35
) -> AISImage:
    """
    source_image を元に「無効っぽい見た目の画像」を生成する

    Args:
        text: オーバーレイする文字列
        darkness: 画像の暗さ

    Returns:
        AISImage: 無効っぽい見た目の画像
    """
    # エイリアス
    source_pil_image = source_image.pil_image

    # 輝度を割合で下げる
    enhancer = ImageEnhance.Brightness(source_pil_image.convert("RGBA"))
    dark_image = enhancer.enhance(darkness)

    # 黒画像を半透明合成して更に暗くする
    w, h = dark_image.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 120))
    dark_image.alpha_composite(overlay)

    # テキストを描画
    font = FontCache.query(h / 8)
    tw, th = get_text_bbox_size(dark_image.size, text, font)
    center_w = (w - tw) / 2
    center_h = (h - th) / 2
    center_pos = (center_w, center_h)
    draw = ImageDraw.Draw(dark_image)
    draw.text(center_pos, text, font=font, fill=(255, 255, 255, 230))

    # 正常終了
    return AISImage(dark_image.convert("RGB"))


def pil_to_np(pil_image: Image.Image) -> np.ndarray:
    """
    PIL 画像を ndarray 画像に変換
    値域 [0.0, 1.0] の float に変換される
    """
    return np.asanyarray(pil_image).astype(np.float32) / 255.0


def np_to_pil(np_image: np.ndarray) -> Image.Image:
    """
    ndarray 画像を PIL 画像に変換
    """
    np_image = (np_image * 255.0).clip(0, 255).astype(np.uint8)
    return Image.fromarray(np_image)


def split_rgba(np_image: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    """
    np_image を RGB, A に分離する
    A がない場合は None が返る
    """
    if len(np_image.shape) == 2:
        return np_image, None
    elif np_image.shape[2] <= 3:
        return np_image, None
    else:
        np_image_rgb = np_image[..., :3]
        np_image_a = np_image[..., 3:]
        return np_image_rgb, np_image_a


def concat_rgba(np_image_rgb: np.ndarray, np_image_a: np.ndarray | None) -> np.ndarray:
    """
    np_image_rgb, np_image_a を結合して RGBA 画像を生成する
    """
    if np_image_a is None:
        return np_image_rgb
    else:
        return np.concatenate([np_image_rgb, np_image_a], axis=-1)


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    """
    x が sRGB と仮定して Linear RGB に変換する
    """
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    """
    x が Linear RGB と仮定して sRGB に変換する
    """
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * (x ** (1 / 2.4)) - 0.055)


def normalize(np_image: np.ndarray) -> np.ndarray:
    """
    画像の輝度が最大 255 になるように正規化
    """
    max_value: np.ndarray = np_image.max()
    scale = 1.0 / max_value
    np_image = scale * np_image
    return np_image


def overlay_nime_name(source_image: AISImage, nime_name: str | None) -> AISImage:
    """
    source_image に nime_name をオーバーレイする。
    """
    # 名前が無い場合は何もしない
    if nime_name is None:
        return AISImage(source_image.pil_image.copy())

    # フォントサイズを決定
    # NOTE
    #   フォントサイズが一定を切る場合は文字が潰れちゃうのでフォント描画なし
    FONT_SCALE_DEN = 24
    MIN_FONT_SIZE = 10
    font_size = source_image.height // FONT_SCALE_DEN
    if font_size < MIN_FONT_SIZE:
        return AISImage(source_image.pil_image.copy())

    # 構築先画像
    result_image = source_image.pil_image.convert("RGB")

    # 編集領域マージン定数
    EDIT_MERGIN_PCT = 1.0
    edit_box_mergin_width = round(EDIT_MERGIN_PCT * font_size)
    edit_box_mergin_height = round(EDIT_MERGIN_PCT * font_size)

    # 画像内に収まるようにテキストの中央を切り詰める
    # NOTE
    #   末尾には話数が入っている可能性があるので、そこは避ける。
    nime_name_first = nime_name[: len(nime_name) // 2]
    nime_name_second = nime_name[len(nime_name) // 2 :]
    actual_nime_name = nime_name
    while True:
        font = FontCache.query(font_size)
        text_box_width, text_box_height = get_text_bbox_size(
            result_image.size, actual_nime_name, font
        )
        if text_box_width + edit_box_mergin_width <= source_image.width:
            break
        else:
            nime_name_first = nime_name_first[:-1]
            nime_name_second = nime_name_second[1:]
            actual_nime_name = nime_name_first + "…" + nime_name_second

    # テキスト矩形領域（グローバル）を解決
    text_box_left = 0
    text_box_top = source_image.height - text_box_height
    text_box = (
        text_box_left,
        text_box_top,
        text_box_left + text_box_width,
        text_box_top + text_box_height,
    )

    # 編集対象の矩形領域を解決
    # NOTE
    #   こちらはテキスト矩形領域よりも広い
    #   ブラーがクリップされないように広く取る
    edit_box_left = 0
    edit_box_top = text_box_top - edit_box_mergin_height
    edit_box_width = text_box_width + edit_box_mergin_width
    edit_box_height = text_box_height + edit_box_mergin_height
    edit_box = (
        edit_box_left,
        edit_box_top,
        edit_box_left + edit_box_width,
        edit_box_top + edit_box_height,
    )

    # テキスト矩形領域（編集領域内）を解決
    text_box_left_in_edit_box = 0
    text_box_top_in_edit_box = edit_box_mergin_height
    text_box_in_edit_box = (
        text_box_left_in_edit_box,
        text_box_top_in_edit_box,
        text_box_width,
        text_box_top_in_edit_box + text_box_height,
    )

    # バックドロップ局所ブラー
    # NOTE
    #   テキスト描画の背景をぼかして明度・彩度を落とす
    #   背景のエッジを丸めて文字のエッジが目立つようにする
    if True:
        # 定数
        BDLB_MASK_RADIUS_PCT = 0.08
        BDLB_BLUR_RADIUS_PCT = 0.10
        BDLB_CORNER_RADIUS_PCT = 0.3

        # ソフトマスク画像
        bdlb_mask_radius = max(1, BDLB_MASK_RADIUS_PCT * font_size)
        bdlb_corner_radius = max(1, BDLB_CORNER_RADIUS_PCT * font_size)
        bdlb_mask = Image.new("L", (edit_box_width, edit_box_height), 0)
        ImageDraw.Draw(bdlb_mask).rounded_rectangle(
            text_box_in_edit_box, radius=bdlb_corner_radius, fill=255
        )
        bdlb_mask = bdlb_mask.filter(ImageFilter.GaussianBlur(bdlb_mask_radius))
        bdlb_mask = pil_to_np(bdlb_mask)
        bdlb_mask = normalize(bdlb_mask)
        bdlb_mask = bdlb_mask ** (1 / 1.8)  # NOTE サチュレーション
        bdlb_mask = np_to_pil(bdlb_mask)

        # ブラー画像
        bdlb_blur_radius = max(1, BDLB_BLUR_RADIUS_PCT * font_size)
        bdlb_blur = result_image.crop(edit_box)
        bdlb_blur = bdlb_blur.filter(ImageFilter.GaussianBlur(bdlb_blur_radius))

        # ブラーを合成
        bdlb_out = result_image.crop(edit_box)
        bdlb_out = Image.composite(bdlb_blur, bdlb_out, bdlb_mask)
        result_image.paste(bdlb_out, edit_box)
        # result_image.paste(bdlb_mask.convert("RGB"), edit_box)  # DBUG マスク可視化
        # result_image.paste(bdlb_blur, edit_box)  # DBUG ブラー可視化

    # ノックアウト暗化
    # NOTE
    #   文字の線の周辺を暗くして文字を目立たせる
    #   暗くなっていることが分かるかどうかのギリギリを狙っている
    if True:
        # 定数
        KD_DARK_DEPTH_PCT = 0.80
        KD_BLUR_1ST_MIN_RADIUS = 1.0
        KD_BLUR_1ST_PCT = 0.08
        KD_BLUR_2ND_SCALE = 2.0
        KD_BLUR_2ND_MIN_RADIUS = KD_BLUR_2ND_SCALE * KD_BLUR_1ST_MIN_RADIUS
        KD_BLUR_2ND_PCT = KD_BLUR_2ND_SCALE * KD_BLUR_1ST_PCT
        KD_MASK_GAMMA = 1.8

        # ソフトマスク画像
        kd_mask = Image.new("L", (edit_box_width, edit_box_height), 255)
        ImageDraw.Draw(kd_mask).text(
            (text_box_left_in_edit_box, text_box_top_in_edit_box),
            actual_nime_name,
            font=font,
            fill=round(KD_DARK_DEPTH_PCT * 255),
            anchor="lt",
        )
        kd_radius_1st = max(KD_BLUR_1ST_MIN_RADIUS, KD_BLUR_1ST_PCT * font_size)
        kd_radius_2nd = max(KD_BLUR_2ND_MIN_RADIUS, KD_BLUR_2ND_PCT * font_size)
        kd_mask = kd_mask.filter(ImageFilter.GaussianBlur(kd_radius_1st))
        kd_mask = kd_mask.filter(ImageFilter.GaussianBlur(kd_radius_2nd))
        kd_mask = pil_to_np(kd_mask)
        kd_mask = srgb_to_linear(kd_mask)
        kd_mask = kd_mask**KD_MASK_GAMMA

        # マスクに基づいて暗化
        kd_out = result_image.crop(edit_box)
        kd_out = pil_to_np(kd_out)
        kd_out = srgb_to_linear(kd_out)
        kd_out = kd_out * np.expand_dims(kd_mask, -1)
        kd_out = linear_to_srgb(kd_out)
        kd_out = np_to_pil(kd_out)
        result_image.paste(kd_out, edit_box)

    # 方向付きソフトシャドウ
    # NOTE
    #   ダメ押しでふんわりと影を落とす
    if True:
        # 定数
        DSS_DARK_DEPTH_PCT = 0.7
        DSS_DX_PCT = 0.04
        DSS_DY_PCT = 0.06
        DSS_BLUR_PCT = 0.08
        DSS_MASK_GAMMA = 1.8

        # ソフトマスク画像
        dss_text_draw_left = max(1, DSS_DX_PCT * font_size) + text_box_left_in_edit_box
        dss_text_draw_top = max(1, DSS_DY_PCT * font_size) + text_box_top_in_edit_box
        dss_radius = max(1, DSS_BLUR_PCT * font_size)
        dss_mask = Image.new("L", (edit_box_width, edit_box_height), 255)
        ImageDraw.Draw(dss_mask).text(
            (dss_text_draw_left, dss_text_draw_top),
            actual_nime_name,
            font=font,
            fill=round(DSS_DARK_DEPTH_PCT * 255),
            anchor="lt",
        )
        dss_mask = dss_mask.filter(ImageFilter.GaussianBlur(dss_radius))
        dss_mask = pil_to_np(dss_mask)
        dss_mask = srgb_to_linear(dss_mask)
        dss_mask = dss_mask**DSS_MASK_GAMMA

        # マスクに基づいて暗化
        dss_out = result_image.crop(edit_box)
        dss_out = pil_to_np(dss_out)
        dss_out = srgb_to_linear(dss_out)
        dss_out = dss_out * np.expand_dims(dss_mask, -1)
        dss_out = linear_to_srgb(dss_out)
        dss_out = np_to_pil(dss_out)
        result_image.paste(dss_out, edit_box)

    # テキスト描画
    if True:
        ImageDraw.Draw(result_image).text(
            (text_box_left, text_box_top),
            actual_nime_name,
            font=font,
            fill=(255, 255, 255),
            anchor="lt",
        )

    # 正常終了
    return AISImage(result_image)


class ImageModel:
    """
    画像を表すクラス
    View-Model 的な意味でのモデル
    """

    def __init__(
        self,
        raw_image: AISImage | None = None,
        nime_name: str | None = None,
        time_stamp: str | None = None,
        enable: bool = True,
        nime_resize_mode: ResizeMode | None = None,
    ):
        """
        コンストラクタ

        Args:
            raw_image (AISImage): 元画像
        """
        # 各画像メンバ
        self._raw_image = CachedSourceImage()
        self._crop_square_image = CachedCropSquareImage(self._raw_image)
        self._nime_image = CachedScalableImage(
            self._crop_square_image,
            ResizeMode.COVER if nime_resize_mode is None else nime_resize_mode,
            aux_process=self._aux_process_nime,
        )
        self._preview_image = CachedScalableImage(self._nime_image, ResizeMode.CONTAIN)
        self._thumbnail_image_enable = CachedScalableImage(
            self._nime_image, ResizeMode.COVER
        )
        self._thumbnail_image_disable = CachedScalableImage(
            self._thumbnail_image_enable,
            ResizeMode.COVER,
            aux_process=make_disabled_image,
        )

        # 通知ハンドラ
        self._notify_handlers = {
            image_layer: cast(list[NotifyHandler], []) for image_layer in ImageLayer
        }

        # 初期設定
        self._raw_image.set_source(raw_image)
        self._nime_name = nime_name
        self._overlay_nime_name = True
        self._time_stamp = time_stamp
        self._enable = enable

    @property
    def nime_name(self) -> str | None:
        """
        アニメ名を取得する
        """
        return self._nime_name

    @property
    def overlay_nime_name(self) -> bool:
        """
        True なら、画像のアニメ名をオーバーレイする
        """
        return self._overlay_nime_name

    @property
    def time_stamp(self) -> str | None:
        """
        この画像の撮影日時を表すタイムスタンプ
        """
        return self._time_stamp

    @property
    def enable(self) -> bool:
        """
        モデルの有効・無効を取得する
        """
        return self._enable

    @property
    def crop_params(self) -> tuple[float | None, float | None, float | None]:
        """
        切り出しパラメータを取得する
        """
        return self._crop_square_image.crop_params

    def get_size(self, layer: ImageLayer) -> ResizeDesc:
        """
        指定 layer のリサイズ挙動を取得する。
        """
        match layer:
            case ImageLayer.RAW:
                raise ValueError("RAW set_size NOT supported.")
            case ImageLayer.NIME:
                return self._nime_image.size
            case ImageLayer.PREVIEW:
                return self._preview_image.size
            case ImageLayer.THUMBNAIL:
                if self._enable:
                    return self._thumbnail_image_enable.size
                else:
                    return self._thumbnail_image_disable.size
            case _:
                raise ValueError(layer)

    def get_resize_mode(self, layer: ImageLayer) -> ResizeMode:
        """
        指定 layer のリサイズモードを取得する。
        """
        match layer:
            case ImageLayer.RAW:
                raise ValueError("RAW set_size NOT supported.")
            case ImageLayer.NIME:
                return self._nime_image.resize_mode
            case ImageLayer.PREVIEW:
                return self._preview_image.resize_mode
            case ImageLayer.THUMBNAIL:
                if self._enable:
                    return self._thumbnail_image_enable.resize_mode
                else:
                    return self._thumbnail_image_disable.resize_mode
            case _:
                raise ValueError(layer)

    def get_image(self, layer: ImageLayer) -> AISImage | None:
        """
        指定 layer の画像を取得する。
        """
        match layer:
            case ImageLayer.RAW:
                return self._raw_image.output
            case ImageLayer.NIME:
                return self._nime_image.output
            case ImageLayer.PREVIEW:
                return self._preview_image.output
            case ImageLayer.THUMBNAIL:
                if self._enable:
                    return self._thumbnail_image_enable.output
                else:
                    return self._thumbnail_image_disable.output
            case _:
                raise ValueError(layer)

    def register_notify_handler(
        self, layer: ImageLayer, handler: NotifyHandler
    ) -> Self:
        """
        画像に「何か」があったあった時にコールバックされる「通知ハンドラ」を登録する。
        画像がダーティー化した時の通知に使われることを想定。
        """
        self._notify_handlers[layer].append(handler)
        return self

    def _aux_process_nime(self, source_image: AISImage) -> AISImage:
        """
        NIME 用の外部プロセス
        """
        if self._overlay_nime_name:
            return overlay_nime_name(source_image, self._nime_name)
        else:
            return source_image


class ImageModelEditSession:
    """
    ImageModel 編集セッション
    with 句で使用する
    """

    def __init__(self, image_model: ImageModel, *, _does_notify: bool = True):
        """
        コンストラクタ
        """
        self._model = image_model
        self._does_notify = _does_notify

    def __enter__(self) -> Self:
        """
        with 句開始
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        with 句終了
        """
        if exc_type is None and self._does_notify:
            self._notify(ImageLayer.RAW)

    def _notify(self, layer: ImageLayer) -> Self:
        """
        あらかじめ登録しておいた通知ハンドラを呼び出す。
        layer と、その影響受けるすべてのレイヤーの通知ハンドラが呼び出される。
        """
        # エイリアス
        model = self._model

        # ダーティフラグを解決
        match layer:
            case ImageLayer.RAW:
                is_dirty = model._raw_image.is_dirty
            case ImageLayer.NIME:
                is_dirty = model._nime_image.is_dirty
            case ImageLayer.PREVIEW:
                is_dirty = model._preview_image.is_dirty
            case ImageLayer.THUMBNAIL:
                is_dirty = (
                    model._thumbnail_image_enable.is_dirty
                    or model._thumbnail_image_disable
                )
            case _:
                raise ValueError(f"Invalid ImageLayer(={layer})")

        # ダーティ状態ならハンドラを呼び出す
        if is_dirty:
            for handler in model._notify_handlers[layer]:
                handler()

        # 影響先のレイヤーの通知ハンドラを再帰的に呼び出す
        match layer:
            case ImageLayer.RAW:
                self._notify(ImageLayer.NIME)
            case ImageLayer.NIME:
                self._notify(ImageLayer.PREVIEW)
                self._notify(ImageLayer.THUMBNAIL)
            case ImageLayer.PREVIEW:
                pass
            case ImageLayer.THUMBNAIL:
                pass
            case _:
                raise ValueError(f"Invalid ImageLayer(={layer})")

        # 正常終了
        return self

    def set_raw_image(self, raw_image: AISImage | None) -> Self:
        """
        RAW 画像を設定する。
        タイムスタンプなどの関連要素は触らないので注意
        """
        # 設定
        self._model._raw_image.set_source(raw_image)

        # 正常終了
        return self

    def set_nime_name(self, nime_name: str | None) -> Self:
        """
        アニメ名を設定する。
        NIME 画像が影響を受ける。
        """
        # サニタイズ
        if nime_name is not None:
            nime_name = sanitize_text(nime_name)

        # アニメ名更新・通知
        model = self._model
        if model._nime_name != nime_name:
            model._nime_name = nime_name
            model._nime_image.mark_dirty()

        # 正常終了
        return self

    def set_overlay_nime_name(self, overlay_nime_name: bool) -> Self:
        """
        アニメ名オーバーレイの有効・無効を設定するする。
        NIME 画像が影響を受ける。
        """
        # アニメ名更新・通知
        model = self._model
        if model._overlay_nime_name != overlay_nime_name:
            model._overlay_nime_name = overlay_nime_name
            model._nime_image.mark_dirty()

        # 正常終了
        return self

    def set_time_stamp(self, time_stamp: str | None) -> Self:
        """
        タイムスタンプを設定する
        RAW 画像は更新されない。
        """
        # タイムスタンプ更新
        model = self._model
        if isinstance(time_stamp, str):
            if is_time_stamp(time_stamp):
                model._time_stamp = time_stamp
            else:
                raise ValueError(time_stamp)
        elif time_stamp is None:
            model._time_stamp = current_time_stamp()
        else:
            raise TypeError(time_stamp)

        # 正常終了
        return self

    def set_enable(self, enable: bool) -> Self:
        """
        モデルの有効・無効を切り替える
        """
        model = self._model
        if model._enable != enable:
            model._enable = enable
            model._thumbnail_image_enable.mark_dirty()
            model._thumbnail_image_disable.mark_dirty()
        return self

    def set_crop_params(
        self, size_ratio: float | None, x_ratio: float | None, y_ratio: float | None
    ) -> Self:
        """
        正方形切り出しのパラメータを設定する。
        パラメータに１つでも None が混じっている場合、切り出しを行わない。
        初期値はすべて None になっている。

        size_ratio:
            正方形の大きさ
            元画像の短辺側に対する比率で指定

        x_ratio:
            正方形の中心位置（水平）
            元画像の横幅に対する比率で指定

        y_ratio:
            正方形の中心位置（垂直）
            元画像の高さに対する比率で指定
        """
        self._model._crop_square_image.set_crop_params(size_ratio, x_ratio, y_ratio)
        return self

    def set_size(self, layer: ImageLayer, size: ResizeDesc) -> Self:
        """
        指定 layer のリサイズ挙動を設定する。
        """
        # layer 分岐
        model = self._model
        match layer:
            case ImageLayer.RAW:
                raise ValueError("RAW set_size NOT supported.")
            case ImageLayer.NIME:
                model._nime_image.set_size(size)
            case ImageLayer.PREVIEW:
                model._preview_image.set_size(size)
            case ImageLayer.THUMBNAIL:
                model._thumbnail_image_enable.set_size(size)
                model._thumbnail_image_disable.set_size(size)
            case _:
                raise ValueError(layer)

        # 正常終了
        return self

    def set_resize_mode(self, layer: ImageLayer, resize_mode: ResizeMode) -> Self:
        """
        指定 layer のリサイズモードを設定する。
        """
        # layer 分岐
        model = self._model
        match layer:
            case ImageLayer.RAW:
                raise ValueError("RAW set_size NOT supported.")
            case ImageLayer.NIME:
                model._nime_image.set_resize_mode(resize_mode)
            case ImageLayer.PREVIEW:
                model._preview_image.set_resize_mode(resize_mode)
            case ImageLayer.THUMBNAIL:
                model._thumbnail_image_enable.set_resize_mode(resize_mode)
                model._thumbnail_image_disable.set_resize_mode(resize_mode)
            case _:
                raise ValueError(layer)

        # 正常終了
        return self


class PlaybackMode(Enum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    REFLECT = "REFLECT"


class VideoModel:
    """
    動画を表すクラス
    View-Model 的な意味でのモデル
    """

    def __init__(self, nime_resize_mode: ResizeMode | None = None):
        """
        コンストラクタ
        """
        # モデル
        # NOTE
        #   サイズとかの全フレーム共通の情報は self._global_model をマスターとして管理する
        #   フレーム個別の情報は self._frame で管理する
        self._global_model = ImageModel(nime_resize_mode=nime_resize_mode)
        self._frames: list[ImageModel] = []

        # 再生時の更新間隔
        self._duration_in_msec = DFR_MAP.default_entry.duration_in_msec
        self._duration_is_dirty = False
        self._duration_change_handlers: list[NotifyHandler] = []

        # 再生モード
        self._playback_mode = PlaybackMode.FORWARD
        self._playback_mode_is_dirty = False
        self._playback_mode_change_handlers: list[NotifyHandler] = []

    @property
    def nime_name(self) -> str | None:
        """
        アニメ名
        """
        return self._global_model.nime_name

    @property
    def overlay_nime_name(self) -> bool:
        """
        アニメ名オーバーレイ有効・無効
        """
        return self._global_model.overlay_nime_name

    @property
    def time_stamp(self) -> str | None:
        """
        この動画の撮影日時を表すタイムスタンプ
        """
        return self._global_model.time_stamp

    def get_enable(self, frame_index: int) -> bool:
        """
        指定フレームの有効・無効を取得する
        """
        return self._frames[frame_index].enable

    @property
    def crop_params(self) -> tuple[float | None, float | None, float | None]:
        """
        切り出しパラメータを取得する
        """
        return self._global_model.crop_params

    def get_size(self, layer: ImageLayer) -> ResizeDesc:
        """
        フレームサイズを取得する
        """
        return self._global_model.get_size(layer)

    def get_resize_mode(self, layer: ImageLayer) -> ResizeMode:
        """
        リサイズモードを取得する
        """
        return self._global_model.get_resize_mode(layer)

    @property
    def num_total_frames(self) -> int:
        """
        有効・無効を問わない総フレーム数を取得

        Returns:
            int: 有効・無効を問わない総フレーム数
        """
        return len(self._frames)

    @property
    def num_enable_frames(self) -> int:
        """
        有効なフレーム数を取得

        Returns:
            int: 有効なフレーム数
        """
        return len([f for f in self._frames if f.enable])

    def iter_frames(
        self, layer: ImageLayer, enable_only: bool = True
    ) -> Generator[AISImage | None, None, None]:
        """
        全てのフレームをイテレートする
        """
        for f in self._frames:
            if not enable_only or f.enable:
                yield f.get_image(layer)

    def get_frame(self, layer: ImageLayer, frame_index: int) -> AISImage | None:
        """
        指定レイヤー・インデックスのフレームを取得する。
        インデックスは有効・無効を考慮しないトータルの番号。
        """
        return self._frames[frame_index].get_image(layer)

    @property
    def duration_in_msec(self) -> int:
        """
        再生時の更新間隔
        """
        return self._duration_in_msec

    @property
    def playback_mode(self) -> PlaybackMode:
        """
        再生モード
        """
        return self._playback_mode

    def register_notify_handler(self, layer: ImageLayer, handler: NotifyHandler):
        """
        通知ハンドラーを登録する
        各画像に変更があった時にコールバックされる
        """
        self._global_model.register_notify_handler(layer, handler)

    def register_duration_change_handler(self, handler: NotifyHandler):
        """
        再生時更新間隔の変更ハンドラーを登録する
        """
        self._duration_change_handlers.append(handler)

    def register_playback_mode_change_handler(self, handler: NotifyHandler):
        """
        再生モードの変更ハンドラーを登録する
        """
        self._playback_mode_change_handlers.append(handler)


class VideoModelEditSession:
    """
    VideoModel 編集セッション
    with 句で使用する
    """

    def __init__(self, video_model: VideoModel):
        """
        コンストラクタ
        """
        self._model = video_model

    def __enter__(self) -> Self:
        """
        with 句開始
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        with 句終了
        """
        if exc_type is None:
            self._notify(ImageLayer.RAW)

    def _notify(self, layer: ImageLayer) -> Self:
        """
        あらかじめ登録しておいた通知ハンドラを呼び出す。
        layer と、その影響受けるすべてのレイヤーの通知ハンドラが呼び出される。
        """
        # エイリアス
        model = self._model

        # グローバルモデルによる通知
        with ImageModelEditSession(model._global_model):
            pass

        # フレーム更新間隔による通知
        if model._duration_is_dirty:
            for handler in model._duration_change_handlers:
                handler()

        # 正常終了
        return self

    def set_nime_name(self, nime_name: str | None) -> Self:
        """
        アニメ名を設定する。
        """
        # エイリアス
        model = self._model

        # 各フレーム
        for frame in model._frames:
            with ImageModelEditSession(frame, _does_notify=False) as e:
                e.set_nime_name(nime_name)

        # グローバル
        with ImageModelEditSession(model._global_model, _does_notify=False) as e:
            e.set_nime_name(nime_name)

        # 正常終了
        return self

    def set_overlay_nime_name(self, overlay_nime_name: bool) -> Self:
        """
        アニメ名を設定する。
        """
        # エイリアス
        model = self._model

        # 各フレーム
        for frame in model._frames:
            with ImageModelEditSession(frame, _does_notify=False) as e:
                e.set_overlay_nime_name(overlay_nime_name)

        # グローバル
        with ImageModelEditSession(model._global_model, _does_notify=False) as e:
            e.set_overlay_nime_name(overlay_nime_name)

        # 正常終了
        return self

    def set_time_stamp(self, time_stamp: str | None) -> Self:
        """
        動画のタイムスタンプを設定する。
        """
        # エイリアス
        model = self._model

        # 各フレーム
        for frame in model._frames:
            with ImageModelEditSession(frame, _does_notify=False) as e:
                e.set_time_stamp(time_stamp)

        # グローバル
        with ImageModelEditSession(model._global_model, _does_notify=False) as e:
            e.set_time_stamp(time_stamp)

        # 正常終了
        return self

    def set_enable(self, frame_indices: int | list[int] | None, enable: bool) -> Self:
        """
        指定フレームの有効・無効を設定する
        """
        model = self._model
        if frame_indices is None:
            return self.set_enable_batch(
                [(frame_index, enable) for frame_index in range(len(model._frames))]
            )
        elif isinstance(frame_indices, list):
            return self.set_enable_batch(
                [(frame_index, enable) for frame_index in frame_indices]
            )
        elif isinstance(frame_indices, int):
            return self.set_enable_batch([(frame_indices, enable)])
        else:
            raise TypeError()

    def set_enable_batch(self, entries: list[tuple[int, bool]]) -> Self:
        """
        指定フレームの有効・無効を設定する
        indices は (インデックス, 有効・無効) のリスト
        """
        # 各フレームに有効・無効を反映
        model = self._model
        does_change = False
        for entry in entries:
            frame_index = entry[0]
            enable = entry[1]
            frame = model._frames[frame_index]
            if frame.enable != enable:
                does_change = True
                with ImageModelEditSession(frame, _does_notify=False) as e:
                    e.set_enable(enable)

        # グローバルモデルに状態を反映
        # NOTE
        #   原則として、１フレームでも変更があれば動画全体として通知が飛ぶ
        #   よって、グローバルモデルに対して変化を発生させる
        #   グローバルモデルの enable の値そのものは整合する必要がなくて、変化させることが重要
        if does_change:
            with ImageModelEditSession(model._global_model, _does_notify=False) as e:
                e.set_enable(not model._global_model.enable)

        # 正常終了
        return self

    def set_crop_params(
        self, size_ratio: float | None, x_ratio: float | None, y_ratio: float | None
    ) -> Self:
        """
        正方形切り出しのパラメータを設定する。
        """
        # エイリアス
        model = self._model

        # 各フレーム
        for frame in model._frames:
            with ImageModelEditSession(frame, _does_notify=False) as e:
                e.set_crop_params(size_ratio, x_ratio, y_ratio)

        # グローバル
        with ImageModelEditSession(model._global_model, _does_notify=False) as e:
            e.set_crop_params(size_ratio, x_ratio, y_ratio)

        # 正常終了
        return self

    def set_size(self, layer: ImageLayer, size: ResizeDesc) -> Self:
        """
        フレームサイズを設定する
        """
        # エイリアス
        model = self._model

        # 各フレーム
        for frame in model._frames:
            with ImageModelEditSession(frame, _does_notify=False) as e:
                e.set_size(layer, size)

        # グローバル
        with ImageModelEditSession(model._global_model, _does_notify=False) as e:
            e.set_size(layer, size)

        # 正常終了
        return self

    def set_resize_mode(self, layer: ImageLayer, resize_mode: ResizeMode) -> Self:
        """
        リサイズモードを設定する
        """
        # エイリアス
        model = self._model

        # 各フレーム
        for frame in model._frames:
            with ImageModelEditSession(frame, _does_notify=False) as e:
                e.set_resize_mode(layer, resize_mode)

        # グローバル
        with ImageModelEditSession(model._global_model, _does_notify=False) as e:
            e.set_resize_mode(layer, resize_mode)

        # 正常終了
        return self

    def append_frames(
        self,
        new_obj: (
            AISImage
            | Iterable[AISImage]
            | ImageModel
            | Iterable[ImageModel]
            | "VideoModel"
            | Iterable["VideoModel"]
        ),
        *,
        _does_notify: bool = True,
    ) -> Self:
        """
        動画フレームを末尾に追加する

        Args:
            frames (list[ImageModel]): 挿入するフレーム

        Returns:
            VideoModel: 自分自身
        """
        # エイリアス
        model = self._model

        # 追加フレームが…
        if isinstance(new_obj, ImageModel):
            # ImageModel の場合、通常の追加フロー

            with ImageModelEditSession(new_obj, _does_notify=False) as e:
                # いろいろ統一
                e.set_crop_params(*model._global_model.crop_params)
                for layer in ImageLayer:
                    if layer != ImageLayer.RAW:
                        e.set_size(layer, model._global_model.get_size(layer))
                        e.set_resize_mode(
                            layer, model._global_model.get_resize_mode(layer)
                        )
                e.set_time_stamp(model._global_model.time_stamp)
                e.set_nime_name(model._global_model.nime_name)

                # フレームリストに挿入
                model._frames.append(new_obj)
        else:
            # ImageModel ではない場合、 ImageModel の呼び出しに変換
            if isinstance(new_obj, Iterable):
                for new_frame in new_obj:
                    self.append_frames(new_frame, _does_notify=False)
            elif isinstance(new_obj, AISImage):
                self.append_frames(
                    ImageModel(new_obj, model.time_stamp), _does_notify=False
                )
            elif isinstance(new_obj, VideoModel):
                for new_frame in new_obj._frames:
                    self.append_frames(new_frame, _does_notify=False)

            else:
                raise TypeError(f"Invalid type {type(new_obj)}")

        # グローバルモデルに状態を反映
        # NOTE
        #   原則、１フレームでも変更があれば動画全体として通知が飛ぶ
        #   フレームの追加・削除については RAW レイヤーでの変更とみなす
        #   よってグローバルモデルに新規生成した画像を渡して強制的に通知を発生させる
        if _does_notify:
            with ImageModelEditSession(model._global_model, _does_notify=False) as e:
                e.set_raw_image(AISImage.empty())

        # 正常終了
        return self

    def delete_frame(self, position: int) -> Self:
        """
        指定インデックスのフレームを削除する
        """
        # エイリアス
        model = self._model

        # 指定フレームを削除
        model._frames.pop(position)

        # グローバルモデルに状態を反映
        with ImageModelEditSession(model._global_model, _does_notify=False) as e:
            e.set_raw_image(AISImage.empty())

        # 正常終了
        return self

    def clear_frames(self) -> Self:
        """
        全フレームを削除する
        """
        # エイリアス
        model = self._model

        # 全フレームを削除
        model._frames.clear()

        # グローバルモデルに状態を反映
        with ImageModelEditSession(model._global_model, _does_notify=False) as e:
            e.set_raw_image(AISImage.empty())

        # 正常終了
        return self

    def set_duration_in_msec(self, duration_in_msec: int) -> Self:
        """
        再生時更新間隔を設定する
        """
        model = self._model
        if model._duration_in_msec != duration_in_msec:
            model._duration_in_msec = duration_in_msec
            model._duration_is_dirty |= True
        return self

    def set_playback_mode(self, playback_mode: PlaybackMode) -> Self:
        """
        再生モードを設定する
        """
        model = self._model
        if model._playback_mode != playback_mode:
            model._playback_mode = playback_mode
            model._playback_mode_is_dirty |= True
        return self


def save_content_model(model: ImageModel | VideoModel) -> Path:
    """
    model をファイル保存する。
    画像・動画の両方に対応している。

    Return:
        Path: 保存先ファイルパス
    """
    # 保存先ディレクトリを生成
    NIME_DIR_PATH.mkdir(parents=True, exist_ok=True)
    RAW_DIR_PATH.mkdir(parents=True, exist_ok=True)

    # タイムスタンプ必須
    if model.time_stamp is None:
        raise ValueError()

    # モデルを保存する
    if isinstance(model, ImageModel):
        # ImageModel

        # raw 画像は必須
        raw_image = model.get_image(ImageLayer.RAW)
        if not isinstance(raw_image, AISImage):
            raise ValueError("Invalid RAW Image")

        # nime 画像は必須
        nime_image = model.get_image(ImageLayer.NIME)
        if not isinstance(nime_image, AISImage):
            raise ValueError("Invalid NIME Image")

        # raw ディレクトリに png 画像を保存
        # NOTE
        #   スチル画像の場合は raw 画像に後から変更が入ることはありえない。
        #   よって、ローカルにファイルが無い場合だけ保存する。
        raw_file_path = (
            RAW_DIR_PATH
            / f"{model.nime_name}__{model.time_stamp}{RAW_STILL_OUT_SUFFIX}"
        )
        if not raw_file_path.exists():
            raw_image.pil_image.convert("RGB").save(
                str(raw_file_path),
                format=RAW_STILL_OUT_PIL_FORMAT,
                optimize=True,
                compress_level=9,
            )

        # nime ディレクトリにスチル画像を保存
        # NOTE
        #   NIME 画像はサイズ変更がかかっている可能性があるので、必ず保存処理を通す。
        still_file_path = (
            NIME_DIR_PATH
            / f"{model.nime_name}__{model.time_stamp}{NIME_STILL_OUT_SUFFIX}"
        )
        nime_image.pil_image.convert("RGB").save(
            str(still_file_path),
            format=NIME_STILL_OUT_PIL_FORMAT,
            lossless=False,
            quality=88,
            alpha_quality=88,
            method=6,
            exact=False,  # 透明画素の RGB 値は保持しない
        )

        # 正常終了
        return still_file_path

    elif isinstance(model, VideoModel):
        # VideoModel

        # RAW ディレクトリに保存
        with PerfLogger("Save RAW Video"):
            raw_file_path = (
                RAW_DIR_PATH
                / f"{model.nime_name}__{model.time_stamp}{RAW_VIDEO_OUT_SUFFIX}"
            )
            if not raw_file_path.exists():
                # RAW フレームを展開
                raw_frames = [
                    f.pil_image
                    for f in model.iter_frames(ImageLayer.RAW)
                    if isinstance(f, AISImage)
                ]

                # 再生モードを反映
                match model.playback_mode:
                    case PlaybackMode.FORWARD:
                        pass
                    case PlaybackMode.BACKWARD:
                        raw_frames.reverse()
                    case PlaybackMode.REFLECT:
                        if len(raw_frames) >= 3:
                            raw_frames = (
                                raw_frames + [f for f in reversed(raw_frames)][1:-1]
                            )
                    case _:
                        raise RuntimeError()

                # ファイル保存
                # NOTE
                #   - 無圧縮で保存（これはマスト）
                #   - 保存にかかる時間の短縮を最優先
                #   - 完全な無圧縮は避けたい
                #   という観点から WebP(lossless) を選択した。
                #   エンコード時間を短縮したいので、圧縮率は最大限妥協している。
                raw_frames[0].save(
                    str(raw_file_path),
                    save_all=True,
                    append_images=raw_frames[1:],
                    duration=model.duration_in_msec,
                    loop=0,  # 無限ループ
                    lossless=True,  # 可逆圧縮
                    quality=0,  # エンコード時間を最優先
                    method=0,  # エンコード時間を最優先
                )

        # NIME ディレクトリに保存
        with PerfLogger("Save NIME Video"):
            # NIME フレームを展開
            nime_frames = [
                f.pil_image
                for f in model.iter_frames(ImageLayer.NIME)
                if isinstance(f, AISImage)
            ]

            # 再生モードを反映
            match model.playback_mode:
                case PlaybackMode.FORWARD:
                    pass
                case PlaybackMode.BACKWARD:
                    nime_frames.reverse()
                case PlaybackMode.REFLECT:
                    if len(nime_frames) >= 3:
                        nime_frames = (
                            nime_frames + [f for f in reversed(nime_frames)][1:-1]
                        )
                case _:
                    raise RuntimeError()

            # nime ディレクトリに動画ファイルを保存
            nime_file_path = (
                NIME_DIR_PATH
                / f"{model.nime_name}__{model.time_stamp}{NIME_VIDEO_OUT_SUFFIX}"
            )
            nime_frames[0].save(
                str(nime_file_path),
                save_all=True,
                append_images=nime_frames[1:],
                duration=model.duration_in_msec,
                quality=65,
                subsampling="4:2:0",
                speed=7,
                range="full",
                codec="auto",
            )

            # 正常終了
            return nime_file_path

    else:
        raise TypeError(type(model))


def load_content_model(file_path: Path) -> ImageModel | VideoModel:
    """
    file_path から画像を読み込む。
    画像・動画の両方に対応している。

    動画の場合は、動画のフレームを全て読み込んでリストで返す。

    同名のファイルが raw に存在する場合はそちらを読み込み、
    それ以外の場合は file_path そのものを読み込む。

    Args:
        file_path (Path): 読み込み元ファイルパス

    Returns:
        AISImage: 読み込んだ画像
    """
    # 先に静画・動画を判定
    # NOTE
    #   webp はどっちもありえるので、ヘッダで判断する。
    #   それ以外は拡張子で判断する。
    if file_path.suffix == ".webp":
        with Image.open(file_path) as im:
            if getattr(im, "is_animated", False) and getattr(im, "n_frames", 1) > 1:
                is_video = True
            else:
                is_video = False
    elif file_path.suffix.lower() in ALL_STILL_INOUT_SUFFIXES:
        is_video = False
    elif file_path.suffix.lower() in ALL_VIDEO_INOUT_SUFFIXES:
        is_video = True
    else:
        raise ValueError(
            f"Unsupported file type. Only extensions {ALL_CONTENT_INOUT_SUFFIXES} are supported."
        )

    # 対応する RAW ファイル候補を列挙
    if is_video:
        raw_file_path_cands = [
            p
            for p in RAW_DIR_PATH.glob(f"**/{file_path.stem}.*")
            if p.suffix.lower() in RAW_VIDEO_INOUT_SUFFIXES
        ]
    else:
        raw_file_path_cands = [
            p
            for p in RAW_DIR_PATH.glob(f"**/{file_path.stem}.*")
            if p.suffix.lower() in RAW_STILL_INOUT_SUFFIXES
        ]

    # 対応する RAW ファイルを確定させる
    if len(raw_file_path_cands) >= 1:
        raw_file_path = sorted(raw_file_path_cands)[0]
    else:
        raw_file_path = None

    # 実際に読み込むべきファイルパスを解決する
    if raw_file_path is not None:
        actual_file_path = raw_file_path
    else:
        actual_file_path = file_path

    # 使用する NIEM 名・タイムスタンプを解決
    nime_name, time_stamp = parse_nime_file_stem(actual_file_path.stem)
    if time_stamp is None:
        time_stamp = current_time_stamp()

    # コンテンツをロード
    if is_video and actual_file_path.suffix.lower() == ".zip":
        # ZIP ファイルの場合、中身を連番静止画として読み込む
        # NOTE
        #   ZIP ファイルはこのアプリによって出力されたものであることを前提としている
        #   その中身は RAW_STILL_SUFFIX であることを前提としている

        # 動画ファイルからフレームレートをロード
        try:
            delays = []
            with Image.open(file_path) as img:
                while True:
                    delays.append(
                        img.info.get("duration", DFR_MAP.default_entry.duration_in_msec)
                    )
                    try:
                        img.seek(img.tell() + 1)
                    except EOFError:
                        break
            avg_delay = round(sum(delays) / len(delays))
        except Exception:
            avg_delay = None

        # ビデオモデルを構築
        content_model = VideoModel()
        with VideoModelEditSession(content_model) as edit:
            edit.set_nime_name(nime_name)
            edit.set_time_stamp(time_stamp)
            if avg_delay is not None:
                edit.set_duration_in_msec(avg_delay)
            with ZipFile(actual_file_path, "r") as zip_file:
                file_list = zip_file.namelist()
                for file_name in file_list:
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
                        enable = True
                    else:
                        enable_str = enable_match.group(1)
                        if enable_str == "d":
                            enable = False
                        else:
                            enable = True

                    # フレームを追加
                    edit.append_frames(
                        ImageModel(
                            AISImage(
                                Image.open(zip_file.open(file_name.name)).convert("RGB")
                            ),
                            nime_name,
                            time_stamp,
                            enable,
                        )
                    )
    elif is_video:
        # 動画ファイルの場合はそのまま読み込む
        content_model = VideoModel()
        with VideoModelEditSession(content_model) as edit:
            edit.set_nime_name(nime_name)
            edit.set_time_stamp(time_stamp)
            delays = []
            with Image.open(actual_file_path) as img:
                try:
                    while True:
                        pil_image = img.copy().convert("RGB")
                        edit.append_frames(
                            [ImageModel(AISImage(pil_image), nime_name, time_stamp)]
                        )
                        delays.append(
                            img.info.get(
                                "duration", DFR_MAP.default_entry.duration_in_msec
                            )
                        )
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass
            avg_delay = round(sum(delays) / len(delays))
            edit.set_duration_in_msec(avg_delay)
    else:
        # 画像ファイルの場合はそのまま読み込む
        pil_image = Image.open(actual_file_path).convert("RGB")
        content_model = ImageModel(AISImage(pil_image), nime_name, time_stamp)

    # 正常終了
    return content_model


def _remove_unmatched_nime_raw_file():
    """
    nime に無いけど raw にあるファイルを削除する。
    """
    # NIME 側を列挙
    nime_file_names = {
        p.name
        for p in NIME_DIR_PATH.glob("**/*.*")
        if p.suffix.lower() in NIME_CONTENT_INOUT_SUFFIXES
    }

    # RAW 側
    for raw_file_path in RAW_DIR_PATH.glob("**/**.*"):
        # 非ファイルはスキップ
        if not raw_file_path.is_file():
            continue

        # NIME 側の想定拡張子を解決
        # NOTE
        #   RAW として想定してない拡張子ならスキップ
        if raw_file_path.suffix.lower() in RAW_STILL_INOUT_SUFFIXES:
            nime_suffixes = NIME_STILL_INOUT_SUFFIXES
        elif raw_file_path.suffix.lower() in RAW_VIDEO_INOUT_SUFFIXES:
            nime_suffixes = NIME_VIDEO_INOUT_SUFFIXES
        else:
            continue

        # NIME 側に対応するファイルが居るならスキップ
        expected_nime_file_names = {
            raw_file_path.stem + expected_nime_suffix
            for expected_nime_suffix in nime_suffixes
        }
        if not nime_file_names.isdisjoint(expected_nime_file_names):
            continue

        # 対応する NIME ファイルなしってことなので、 RAW ファイルを削除
        raw_file_path.unlink(True)


def _archive_old_nime_files():
    """
    ある程度以上古い nime ファイルを `nime/older/YYYY_MM` に退避する。
    NOTE
        退避の対象は nime ファイルだけなので、 nime, raw 間で相対パスがズレるが、
        これは `_sync_nime_raw_relative_path` でまとめて修正されることを前提している。
    """
    # ファイルの stem から年月日を抽出する用の正規表現
    nime_stem_pattern = re.compile(r".+__(\d{4})-(\d{2})-(\d{2})_.+")

    # ファイルの stem から年月日を抽出する関数
    def make_year_month_date(nime_file_stem: str) -> int | None:
        m = nime_stem_pattern.match(nime_file_stem)
        if m is None:
            return None
        else:
            year = int(m.group(1)) * (10**4)
            month = int(m.group(2)) * (10**2)
            day = int(m.group(3))
            return year + month + day

    # 「パス --> タイムスタンプ」テーブル
    # NOTE
    #   NIME ディレクトリ直下のファイルが対象
    nime_file_path_to_time_stamp = {
        p: ts
        for p, ts in {
            p: make_year_month_date(p.stem)
            for p in NIME_DIR_PATH.glob("*.*")
            if p.is_file() and p.suffix.lower() in NIME_CONTENT_INOUT_SUFFIXES
        }.items()
        if ts is not None
    }

    # 残す対象のタイムスタンプを列挙
    # NOTE
    #   最新 1000 枚と「年月日」が一致するファイルを残す
    remainting_time_stamps = set(
        sorted(ts for ts in nime_file_path_to_time_stamp.values())[-1000:]
    )

    # すべての NIME ファイルに対して
    for nime_file_path, year_month_date in nime_file_path_to_time_stamp.items():
        # 残す対象ならスキップ
        if year_month_date in remainting_time_stamps:
            continue

        # 移動先パスを生成
        year_month_date_str = str(year_month_date)
        year_month_str = f"{year_month_date_str[0:4]}-{year_month_date_str[4:6]}"
        older_file_path = NIME_DIR_PATH / "older" / year_month_str / nime_file_path.name

        # older に移動
        older_file_path.parent.mkdir(parents=True, exist_ok=True)
        nime_file_path.rename(older_file_path)


def _sync_nime_raw_relative_path():
    """
    「nime 画像の nime フォルダからの相対パス」
    「raw 画像の raw フォルダからの相対パス」
    この２つを一致させる。
    不一致があった場合は raw 側を移動する。
    """
    # RAW ファイル名 --> ファイルパス
    # NOTE
    #   同名ファイルが複数階層に存在するパターンなぞ知らん
    raw_file_name_to_path = {
        p.name: p
        for p in RAW_DIR_PATH.glob("**/*.*")
        if p.is_file() and p.suffix.lower() in RAW_CONTENT_INOUT_SUFFIXES
    }

    # すべての NIME 画像に対して処理
    for nime_path in NIME_DIR_PATH.glob("**/*.*"):
        # 非ファイルはスキップ
        if not nime_path.is_file():
            continue

        # RAW 側の対応拡張子を解決、想定外の拡張子はスキップ
        if nime_path.suffix.lower() in NIME_STILL_INOUT_SUFFIXES:
            raw_suffixes = RAW_STILL_INOUT_SUFFIXES
        elif nime_path.suffix.lower() in NIME_VIDEO_INOUT_SUFFIXES:
            raw_suffixes = RAW_VIDEO_INOUT_SUFFIXES
        else:
            continue

        # 対応する RAW ファイルパスを解決
        actual_raw_file_path = None
        for raw_suffix in raw_suffixes:
            raw_file_name = nime_path.stem + raw_suffix
            actual_raw_file_path = raw_file_name_to_path.get(raw_file_name)
            if actual_raw_file_path is not None:
                break

        # 対応する RAW ファイルがなければスキップ
        if actual_raw_file_path is None:
            continue

        # RAW ファイルをあるべき場所に移動する
        nime_rel_path = nime_path.relative_to(NIME_DIR_PATH)
        raw_rel_path = nime_rel_path.with_suffix(actual_raw_file_path.suffix)
        expected_raw_file_abs_path = RAW_DIR_PATH / raw_rel_path
        if actual_raw_file_path != expected_raw_file_abs_path:
            expected_raw_file_abs_path.parent.mkdir(parents=True, exist_ok=True)
            actual_raw_file_path.rename(expected_raw_file_abs_path)


def standardize_nime_raw_dile():
    """
    nime, raw ディレクトリ下のファイル配置を「標準化」する。
    標準化とは、
    - 対応する NIME ファイルが存在しない RAW ファイルを削除する
    - nime, raw からの相対パスを一致させる
    - nime, raw 直下の古いファイルを `<nime or raw>/older/YYYY_MM` に退避する
    """
    with PerfLogger("_remove_unmatched_nime_raw_file"):
        _remove_unmatched_nime_raw_file()
    with PerfLogger("_archive_old_nime_files"):
        _archive_old_nime_files()
    with PerfLogger("_sync_nime_raw_relative_path"):
        _sync_nime_raw_relative_path()
