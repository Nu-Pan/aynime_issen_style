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
)
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile, ZIP_STORED
from io import BytesIO
import re
from abc import ABC, abstractmethod
from enum import Enum

# PIL
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageOps, ImageStat

# utils
from utils.image import (
    AspectRatioPattern,
    ResizeDesc,
    ResizeMode,
    AISImage,
    GIF_DURATION_MAP,
)
from utils.constants import NIME_DIR_PATH, RAW_DIR_PATH, DEFAULT_FONT_PATH
from utils.std import replace_multi


_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"


def current_time_stamp() -> str:
    """
    現在時刻からタイムスタンプ文字列を生成

    Returns:
        str: タイムスタンプ文字列
    """
    return datetime.now().strftime(_TIMESTAMP_FORMAT)


def is_time_stamp(text: str) -> bool:
    """
    text がタイムスタンプ文字列であるなら True を返す
    """
    # datetime でパース
    try:
        dt = datetime.strptime(text, _TIMESTAMP_FORMAT)
    except ValueError:
        return False

    # パース結果をまた文字列化して一致するか確認
    return dt.strftime(_TIMESTAMP_FORMAT) == text


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
    draw = ImageDraw.Draw(dark_image)
    font = ImageFont.truetype("arial.ttf", size=h // 8)
    tw, th = get_text_bbox_size(draw, text, font)
    center_w = (w - tw) / 2
    center_h = (h - th) / 2
    center_pos = (center_w, center_h)
    draw.text(center_pos, text, font=font, fill=(255, 255, 255, 230))

    # 正常終了
    return AISImage(dark_image.convert("RGB"))


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

    # オーバーレイ画像
    overlay_image = Image.new("RGBA", source_image.pil_image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay_image)

    # 画像内に収まるようにテキストの中央を切り詰める
    # NOTE
    #   末尾には話数が入っている可能性があるので、そこは避ける。
    nime_name_first = nime_name[: len(nime_name) // 2]
    nime_name_second = nime_name[len(nime_name) // 2 :]
    actual_nime_name = nime_name
    while True:
        font = ImageFont.truetype(DEFAULT_FONT_PATH, size=font_size)
        text_width, text_height = get_text_bbox_size(draw, actual_nime_name, font)
        if text_width <= source_image.width:
            break
        else:
            nime_name_first = nime_name_first[:-1]
            nime_name_second = nime_name_second[1:]
            actual_nime_name = nime_name_first + "…" + nime_name_second

    # テキスト背景の塗りつぶし強度を解決
    # NOTE
    #   小領域に分割し、小領域事に平均輝度を計算する。
    #   最も明るい小領域に合わせて塗りつぶし強度を決める。
    text_left = 0
    text_top = source_image.height - text_height
    text_region = source_image.pil_image.crop(
        (text_left, text_top, text_left + text_width, text_top + text_height)
    )
    text_region_brightness = 0
    num_text_sub_region = round(text_width / text_height)
    for text_sub_regoin_index in range(num_text_sub_region):
        left = round(
            text_region.width * (text_sub_regoin_index + 0) / num_text_sub_region
        )
        right = round(
            text_region.width * (text_sub_regoin_index + 1) / num_text_sub_region
        )
        text_sub_region = text_region.crop((left, 0, right, text_region.height))
        text_sub_region_brighness = sum(ImageStat.Stat(text_sub_region).mean[:3]) / 3
        if text_sub_region_brighness > text_region_brightness:
            text_region_brightness = text_sub_region_brighness
    text_bg_strength = min(1.0, text_region_brightness / 255)
    text_bg_alpha = round(159 * text_bg_strength)

    # テキスト背景描画
    draw.rectangle(
        (text_left, text_top, text_left + text_width, text_top + text_height),
        fill=(0, 0, 0, text_bg_alpha),
    )

    # テキスト描画
    draw.text(
        (text_left, text_top),
        actual_nime_name,
        font=font,
        fill=(255, 255, 255, 255),
        anchor="lt",
    )

    # 元画像とテキストをオーバーレイ
    result_pil_image = Image.alpha_composite(
        source_image.pil_image.convert("RGBA"), overlay_image
    ).convert("RGB")

    # 正常終了
    return AISImage(result_pil_image)


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
