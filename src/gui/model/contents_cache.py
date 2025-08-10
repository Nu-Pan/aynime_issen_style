# std
from typing import (
    Optional,
    Union,
    List,
    Callable,
    Generator,
    Self,
    Any,
    Tuple,
    cast,
    Iterable,
    Dict,
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
    ImageOps,
    ImageStat,
    ImageFilter,
    ImageChops,
)

# utils
from utils.image import (
    AspectRatioPattern,
    ResizeDesc,
    ResizeMode,
    AISImage,
    GIF_DURATION_MAP,
)
from utils.constants import NIME_DIR_PATH, RAW_DIR_PATH, OVERLAY_FONT_PATH
from utils.std import replace_multi


class FontCache:
    """
    フォントをキャッシュするクラス
    """

    _cache: Dict[float, ImageFont.FreeTypeFont] = dict()

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


type AuxProcess = Callable[[AISImage], AISImage]
type NotifyHandler = Callable[[], None]


class CachedContent(ABC):
    """
    キャッシュツリーの基底クラス
    """

    def __init__(self, parent: Optional["CachedContent"]):
        """
        コンストラクタ
        """
        # メンバ初期化
        self._parent = parent
        self._known_parent_output: Any = None
        self._is_dirty = False

    @property
    def parent_output(self) -> Optional[AISImage]:
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
    def output(self) -> Optional[AISImage]:
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

    def set_source(self, source: Optional[AISImage]) -> Self:
        """
        ソース画像を設定する
        """
        if self._source != source:
            self.mark_dirty()
            self._source = source
        return self

    @property
    def output(self) -> Optional[AISImage]:
        """
        出力を取得する
        ダーティー状態は暗黙に解決される。
        """
        # NOTE
        #   ソースを素通しなので画像処理は不要
        #   ダーティフラグを下げてソース画像をそのまま返す
        self.mark_resolved()
        return self._source


class CachedScalableImage(CachedContent):
    """
    拡大縮小とそのキャッシュ機能を持つ画像クラス
    """

    type Output = AISImage

    def __init__(
        self,
        parent: CachedContent,
        mode: ResizeMode,
        aux_process: Optional[AuxProcess] = None,
    ):
        """
        コンストラクタ
        """
        # 基底クラス初期化
        super().__init__(parent)

        # 定数
        self._mode = mode
        self._aux_process = aux_process

        # 遅延変数
        self._size = ResizeDesc.from_pattern(
            AspectRatioPattern.E_RAW, ResizeDesc.Pattern.E_RAW
        )
        self._output = None

    def set_size(self, size: ResizeDesc) -> Self:
        """
        スケーリング後のサイズを設定
        """
        if self._size != size:
            self.mark_dirty()
            self._size = size
        return self

    @property
    def size(self) -> ResizeDesc:
        """
        スケーリング後のサイズを取得
        """
        return self._size

    @property
    def output(self) -> Optional[AISImage]:
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
                    self._output = parent_output.resize(self._size, self._mode)
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
    image_size: Tuple[int, int], text: str, font: ImageFont.FreeTypeFont
) -> Tuple[int, int]:
    """
    指定された条件でのテキストバウンディングボックスのサイズを返す

    Args:
        draw (ImageDraw.ImageDraw): 描画コンテキスト
        text (str): テキスト
        font (ImageFont.FreeTypeFont): フォント

    Returns:
        Tuple[int, int]: バウンディングボックスの幅・高さ
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
        text (str, optional): オーバーレイする文字列
        darkness (float, optional): 画像の暗さ

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


def split_rgba(np_image: np.ndarray) -> Tuple[np.ndarray, Optional[np.ndarray]]:
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


def concat_rgba(
    np_image_rgb: np.ndarray, np_image_a: Optional[np.ndarray]
) -> np.ndarray:
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


def overlay_nime_name(source_image: AISImage, nime_name: Optional[str]) -> AISImage:
    """
    source_image に nime_name をオーバーレイする。
    """
    # 名前が無い場合は何もしない
    if nime_name is None:
        return AISImage(source_image.pil_image.copy())

    # <NIME> タグを削除
    nime_name = nime_name.replace("<NIME>", "")

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
        raw_image: Optional[AISImage] = None,
        nime_name: Optional[str] = None,
        time_stamp: Optional[str] = None,
        enable: bool = True,
    ):
        """
        コンストラクタ

        Args:
            raw_image (AISImage): 元画像
        """
        # 各画像メンバ
        self._raw_image = CachedSourceImage()
        self._nime_image = CachedScalableImage(
            self._raw_image, ResizeMode.COVER, aux_process=self._aux_process_nime
        )
        self._preview_pil_image = CachedScalableImage(
            self._nime_image, ResizeMode.CONTAIN
        )
        self._thumbnail_pil_image_enable = CachedScalableImage(
            self._nime_image, ResizeMode.COVER
        )
        self._thumbnail_pil_image_disable = CachedScalableImage(
            self._thumbnail_pil_image_enable,
            ResizeMode.COVER,
            aux_process=make_disabled_image,
        )

        # 通知ハンドラ
        self._notify_handlers = {
            image_layer: cast(List[NotifyHandler], []) for image_layer in ImageLayer
        }

        # 初期設定
        self._raw_image.set_source(raw_image)
        self._nime_name = nime_name
        self._time_stamp = time_stamp
        self._enable = enable

    @property
    def nime_name(self) -> Optional[str]:
        """
        アニメ名を取得する
        """
        return self._nime_name

    @property
    def time_stamp(self) -> Optional[str]:
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
                return self._preview_pil_image.size
            case ImageLayer.THUMBNAIL:
                return self._thumbnail_pil_image_enable.size
            case _:
                raise ValueError(layer)

    def get_image(self, layer: ImageLayer) -> Optional[AISImage]:
        """
        指定 layer の画像を取得する。
        """
        match layer:
            case ImageLayer.RAW:
                return self._raw_image.output
            case ImageLayer.NIME:
                return self._nime_image.output
            case ImageLayer.PREVIEW:
                return self._preview_pil_image.output
            case ImageLayer.THUMBNAIL:
                if self._enable:
                    return self._thumbnail_pil_image_enable.output
                else:
                    return self._thumbnail_pil_image_disable.output
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
        return overlay_nime_name(source_image, self._nime_name)


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
                is_dirty = model._preview_pil_image.is_dirty
            case ImageLayer.THUMBNAIL:
                is_dirty = (
                    model._thumbnail_pil_image_enable.is_dirty
                    or model._thumbnail_pil_image_disable
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

    def set_raw_image(self, raw_image: Optional[AISImage]) -> Self:
        """
        RAW 画像を設定する。
        タイムスタンプなどの関連要素は触らないので注意
        """
        # 設定
        self._model._raw_image.set_source(raw_image)

        # 正常終了
        return self

    def set_nime_name(self, nime_name: Optional[str]) -> Self:
        """
        アニメ名を設定する。
        NIME 画像が影響を受ける。
        """
        # アニメ名更新・通知
        model = self._model
        if model._nime_name != nime_name:
            model._nime_name = nime_name
            model._nime_image.mark_dirty()

        # 正常終了
        return self

    def set_time_stamp(self, time_stamp: Optional[str]) -> Self:
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
            model._thumbnail_pil_image_enable.mark_dirty()
            model._thumbnail_pil_image_disable.mark_dirty()
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
                model._preview_pil_image.set_size(size)
            case ImageLayer.THUMBNAIL:
                model._thumbnail_pil_image_enable.set_size(size)
            case _:
                raise ValueError(layer)

        # 正常終了
        return self


class VideoModel:
    """
    動画を表すクラス
    View-Model 的な意味でのモデル
    """

    def __init__(self):
        """
        コンストラクタ
        """
        # 各メンバを初期化
        # NOTE
        #   サイズとかの全フレーム共通の情報は self._global_model をマスターとして管理する
        #   フレーム個別の情報は self._frame で管理する
        self._global_model = ImageModel()
        self._frames: List[ImageModel] = []
        self._duration_in_msec = GIF_DURATION_MAP.default_entry.gif_duration_in_msec
        self._duration_is_dirty = False
        self._duration_change_handlers: List[NotifyHandler] = []

    @property
    def nime_name(self) -> Optional[str]:
        """
        アニメ名
        """
        return self._global_model.nime_name

    @property
    def time_stamp(self) -> Optional[str]:
        """
        この動画の撮影日時を表すタイムスタンプ
        """
        return self._global_model.time_stamp

    def get_enable(self, frame_index: int) -> bool:
        """
        指定フレームの有効・無効を取得する
        """
        return self._frames[frame_index].enable

    def get_size(self, layer: ImageLayer) -> ResizeDesc:
        """
        フレームサイズを取得する
        """
        return self._global_model.get_size(layer)

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
    ) -> Generator[Optional[AISImage], None, None]:
        """
        全てのフレームをイテレートする
        """
        for f in self._frames:
            if not enable_only or f.enable:
                yield f.get_image(layer)

    def get_frame(self, layer: ImageLayer, frame_index: int) -> Optional[AISImage]:
        """
        指定レイヤー・インデックスのフレームを取得する。
        インデックスは有効・無効を考慮しないトータルの番号。
        """
        return self._frames[frame_index].get_image(layer)

    @property
    def duration_in_msec(self) -> int:
        """
        再生フレームレート
        """
        return self._duration_in_msec

    def register_notify_handler(self, layer: ImageLayer, handler: NotifyHandler):
        """
        通知ハンドラーを登録する
        各画像に変更があった時にコールバックされる
        """
        self._global_model.register_notify_handler(layer, handler)

    def register_duration_change_handler(self, handler: NotifyHandler):
        """
        フレームレート変更ハンドラーを登録する
        """
        self._duration_change_handlers.append(handler)


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

    def set_nime_name(self, nime_name: Optional[str]) -> Self:
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

    def set_time_stamp(self, time_stamp: Optional[str]) -> Self:
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

    def set_enable(
        self, frame_indices: Union[int, List[int], None], enable: bool
    ) -> Self:
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

    def set_enable_batch(self, entries: List[Tuple[int, bool]]) -> Self:
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

    def append_frames(
        self,
        new_obj: Union[
            AISImage,
            Iterable[AISImage],
            ImageModel,
            Iterable[ImageModel],
            "VideoModel",
            Iterable["VideoModel"],
        ],
        *,
        _does_notify: bool = True,
    ) -> Self:
        """
        動画フレームを末尾に追加する

        Args:
            frames (List[ImageModel]): 挿入するフレーム

        Returns:
            VideoModel: 自分自身
        """
        # エイリアス
        model = self._model

        # 追加フレームが…
        if isinstance(new_obj, ImageModel):
            # ImageModel の場合、通常の追加フロー

            with ImageModelEditSession(new_obj, _does_notify=False) as e:
                # サイズを統一
                for layer in ImageLayer:
                    if layer != ImageLayer.RAW:
                        e.set_size(layer, model._global_model.get_size(layer))

                # タイムスタンプを統一
                e.set_time_stamp(model._global_model.time_stamp)

                # アニメ名を統一
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
                e.set_raw_image(AISImage.empty("RGB", 8, 8))

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
            e.set_raw_image(AISImage.empty("RGB", 8, 8))

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
            e.set_raw_image(AISImage.empty("RGB", 8, 8))

        # 正常終了
        return self

    def set_duration_in_msec(self, duration_in_msec: int) -> Self:
        """
        再生フレームレートを設定する
        """
        model = self._model
        if model._duration_in_msec != duration_in_msec:
            model._duration_in_msec = duration_in_msec
            model._duration_is_dirty |= True
        return self


def encode_valid_nime_name(text: Optional[str]) -> str:
    """
    text を合法なアニメ名にエンコードする
    """
    if text is None:
        # 名前なしの場合、 UNKNOWN に置き換え
        return "UNKNOWN"
    elif text.startswith("<NIME>"):
        # 先頭が NIME の場合、適切に抽出されたアニメ名が続いているはずなのでそれを採用
        # ただし空白文字は _ で置き換えて無害化
        return text.replace("<NIME>", "").replace(" ", "_")
    else:
        # それ以外の場合、 UNKNOWN を返す
        return "UNKNOWN"


def decode_valid_nime_name(text: str) -> Optional[str]:
    """
    text からアニメ名をデコードする
    """
    if text == "UNKNOWN":
        return None
    else:
        return "<NIME>" + text.replace("_", " ")


class PlaybackMode(Enum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    REFLECT = "REFLECT"


def save_content_model(
    model: Union[ImageModel, VideoModel],
    playback_mode: PlaybackMode = PlaybackMode.FORWARD,
) -> Path:
    """
    model をファイル保存する。
    画像・動画の両方に対応している。

    Args:
        model (Union[IntegratedImage, IntegratedVideo]): 保存したいモデル
        palyback_mode (PlaybackMode):

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

        # 合法なアニメ名を生成
        valid_nime_name = encode_valid_nime_name(model.nime_name)

        # raw png ファイルの保存が必要か判定
        # NOTE
        #   スチル画像の場合は raw 画像に後から変更が入ることはありえない。
        #   よって、ローカルにファイルが無い場合だけ保存する。
        png_file_path = RAW_DIR_PATH / f"{valid_nime_name}__{model.time_stamp}.png"
        save_png = not png_file_path.exists()

        # raw ディレクトリに png 画像を保存
        if save_png:
            raw_image.pil_image.convert("RGB").save(
                str(png_file_path),
                format="PNG",
                optimize=True,
                compress_levvel=9,
                transparency=(0, 0, 0),
            )

        # nime ディレクトリに jpeg 画像を保存
        # NOTE
        #   NIME 画像はサイズ変更がかかっている可能性があるので、必ず保存処理を通す。
        jpeg_file_path = NIME_DIR_PATH / f"{valid_nime_name}__{model.time_stamp}.jpg"
        nime_image.pil_image.convert("RGB").save(
            str(jpeg_file_path),
            format="JPEG",
            quality=92,
            optimize=True,
            progressive=True,
        )

        # 正常終了
        return jpeg_file_path

    elif isinstance(model, VideoModel):
        # VideoModel

        # 合法なアニメ名を生成
        valid_nime_name = encode_valid_nime_name(model.nime_name)

        # raw ディレクトリに zip ファイルを保存
        # NOTE
        #   raw zip ファイルの差分確認は処理的にも対応コスト的に重い。
        #   なので、妥協して毎回保存する。
        # NOTE
        #   raw フレームは enable かどうかを問わずに保存する。
        # NOTE
        #   ここがかなり重たいので最適化を入れている
        #   特に zip 圧縮が重いので ZIP_STORED にするのが大事
        #   png 圧縮率は大した影響はない
        zip_file_path = RAW_DIR_PATH / f"{valid_nime_name}__{model.time_stamp}.zip"
        with ZipFile(zip_file_path, "w", compression=ZIP_STORED) as zip_file:
            for idx, img in enumerate(model.iter_frames(ImageLayer.RAW, False)):
                # 無効なフレームはスキップ
                if not isinstance(img, AISImage):
                    continue
                # png ファイルメモリに書き出し
                buf = BytesIO()
                img.pil_image.save(buf, format="PNG", optimize=False, compress_level=6)
                # png メモリイメージを zip ファイルに書き出し
                enable_suffix = "e" if model.get_enable(idx) else "d"
                png_file_name = f"{model.time_stamp}_{idx:03d}_{enable_suffix}.png"
                zip_file.writestr(png_file_name, buf.getvalue())

        # NIME フレームを展開
        nime_frames = [
            f.pil_image
            for f in model.iter_frames(ImageLayer.NIME)
            if isinstance(f, AISImage)
        ]

        # フレームの横幅を解決
        frame_width = {f.width for f in nime_frames}
        if len(frame_width) == 1:
            frame_width = frame_width.pop()
        else:
            raise ValueError("Multiple frame width contaminated.")

        # フレームの高さを解決
        frame_height = {f.height for f in nime_frames}
        if len(frame_height) == 1:
            frame_height = frame_height.pop()
        else:
            raise ValueError("Multiple frame height contaminated.")

        # すべての NIME フレームを１つの atlas 画像に結合
        nime_atlas = Image.new(
            "RGB", (frame_width, frame_height * len(nime_frames)), color=None
        )
        for frame_index, nime_frame in enumerate(nime_frames):
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
        for frame_index in range(len(nime_frames)):
            nime_frames[frame_index] = nime_atlas.crop(
                (
                    0,
                    frame_index * frame_height,
                    frame_width,
                    (frame_index + 1) * frame_height,
                )
            )
            nime_frames[frame_index].putpalette(atlas_palette)

        # 再生モードを反映
        match playback_mode:
            case PlaybackMode.FORWARD:
                pass
            case PlaybackMode.BACKWARD:
                nime_frames.reverse()
            case PlaybackMode.REFLECT:
                if len(nime_frames) >= 3:
                    nime_frames = nime_frames + [f for f in reversed(nime_frames)][1:-1]
            case _:
                raise RuntimeError()

        # nime ディレクトリに gif ファイルを保存
        gif_file_path = NIME_DIR_PATH / f"{valid_nime_name}__{model.time_stamp}.gif"
        nime_frames[0].save(
            str(gif_file_path),
            save_all=True,
            append_images=nime_frames[1:],
            duration=model.duration_in_msec,
            loop=0,
            disposal=2,
            optimize=False,
        )

        # 正常終了
        return gif_file_path

    else:
        raise TypeError(type(model))


def load_content_model(
    file_path: Path,
    default_duration_in_msec: int = GIF_DURATION_MAP[-1].gif_duration_in_msec,
) -> Union[ImageModel, VideoModel]:
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
    # 実際に読み込むべきファイルパスを解決する
    IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")
    MOVIE_EXTENSIONS = (".gif",)
    RAW_ZIP_EXTENSIONS = (".zip",)
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        raw_png_file_path = RAW_DIR_PATH / (file_path.stem + ".png")
        if raw_png_file_path.exists():
            actual_file_path = raw_png_file_path
            gif_file_path = None
        elif file_path.exists():
            actual_file_path = file_path
            gif_file_path = None
        else:
            raise FileNotFoundError(f"{raw_png_file_path} or {file_path}")
    elif file_path.suffix.lower() in MOVIE_EXTENSIONS:
        raw_zip_file_path = RAW_DIR_PATH / (file_path.stem + ".zip")
        if raw_zip_file_path.exists():
            actual_file_path = raw_zip_file_path
            gif_file_path = file_path
        elif file_path.exists():
            actual_file_path = file_path
            gif_file_path = file_path
        else:
            raise FileNotFoundError(f"{raw_zip_file_path} or {file_path}")
    elif file_path.suffix.lower() in RAW_ZIP_EXTENSIONS:
        if file_path.exists():
            actual_file_path = file_path
            gif_file_path = None
        else:
            raise FileNotFoundError(f"{file_path}")
    else:
        raise ValueError(
            f"Unsuported file type. Only extensions {IMAGE_EXTENSIONS + MOVIE_EXTENSIONS} are supported."
        )

    # 使用するアニメ名・タイムスタンプを解決
    file_stem_match = re.match("(.+)__(.+)", actual_file_path.stem)
    if file_stem_match is None:
        nime_name = None
        if is_time_stamp(actual_file_path.stem):
            time_stamp = actual_file_path.stem
        else:
            time_stamp = current_time_stamp()
    else:
        nime_name = decode_valid_nime_name(file_stem_match.group(1))
        if is_time_stamp(file_stem_match.group(2)):
            time_stamp = file_stem_match.group(2)
        else:
            time_stamp = current_time_stamp()

    # 画像・動画を読み込む
    if actual_file_path.suffix.lower() in IMAGE_EXTENSIONS:
        # 画像ファイルの場合はそのまま読み込む
        pil_image = Image.open(actual_file_path).convert("RGB")
        image_model = ImageModel(AISImage(pil_image), nime_name, time_stamp)
        return image_model
    elif actual_file_path.suffix.lower() in MOVIE_EXTENSIONS:
        # 動画ファイルの場合はフレームを全て読み込む
        video_model = VideoModel()
        with VideoModelEditSession(video_model) as edit:
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
                            img.info.get("duration", default_duration_in_msec)
                        )
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass
            avg_delay = round(sum(delays) / len(delays))
            edit.set_duration_in_msec(avg_delay)
        return video_model
    elif actual_file_path.suffix.lower() in RAW_ZIP_EXTENSIONS:
        # ZIP ファイルの場合、中身を連番静止画として読み込む
        # NOTE
        #   ZIP ファイルはこのアプリによって出力されたものであることを前提としている
        #   その中身は .png であることを前提としている

        # 対応する gif ファイルからフレームレートをロード
        if gif_file_path is None:
            avg_delay = default_duration_in_msec
        elif isinstance(gif_file_path, Path):
            delays = []
            with Image.open(gif_file_path) as img:
                try:
                    while True:
                        delays.append(
                            img.info.get("duration", default_duration_in_msec)
                        )
                        img.seek(img.tell() + 1)
                except EOFError:
                    pass
            avg_delay = round(sum(delays) / len(delays))
        else:
            raise TypeError(f"Invalid type {type(gif_file_path)}")

        # ビデオモデルを構築
        video_model = VideoModel()
        with VideoModelEditSession(video_model) as edit:
            edit.set_nime_name(nime_name)
            edit.set_time_stamp(time_stamp)
            edit.set_duration_in_msec(avg_delay)
            with ZipFile(actual_file_path, "r") as zip_file:
                file_list = zip_file.namelist()
                for file_name in file_list:
                    # フレームの有効・無効を解決する
                    # NOTE
                    #   ファイル名から解決する
                    #   なんかおかしい時は何も言わずに有効扱いする
                    enable_match = re.search(r"_([de])\.png$", file_name)
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
                                Image.open(zip_file.open(file_name)).convert("RGB")
                            ),
                            nime_name,
                            time_stamp,
                            enable,
                        )
                    )

        # 正常終了
        return video_model
    else:
        raise ValueError("Logic Error")
