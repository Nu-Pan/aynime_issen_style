# std
from typing import (
    Optional,
    Union,
    List,
    Callable,
    Generator,
    Self,
    TypeVar,
    Generic,
    Any,
    Tuple,
    Type,
    cast,
    Dict,
)
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile
from io import BytesIO
from statistics import mode
import re
from abc import ABC, abstractmethod
from enum import Enum

# PIL
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# utils
from utils.image import AspectRatioPattern, ResizeDesc, ResizeMode, AISImage
from utils.constants import NIME_DIR_PATH, RAW_DIR_PATH, DEFAULT_FRAME_RATE


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

    def set_dirty(self, does_set: bool = True) -> Self:
        """
        ダーティフラグを立てる
        立てるかどうかを source_state で指定可能
        """
        self._is_dirty |= does_set
        return self

    def reset_dirty(self) -> Self:
        """
        ダーティフラグを下げる
        """
        self._is_dirty = False
        return self

    @property
    def is_dirty(self) -> bool:
        """
        ダーティー状態なら True を返す
        """
        # 親の変化の有無を自身のダーティフラグに反映
        if self._parent is not None:
            parent_output = self.parent_output
            if parent_output != self._known_parent_output:
                self._known_parent_output = parent_output
                self.set_dirty()

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
            self.set_dirty()
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
        self.reset_dirty()
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
            self.set_dirty()
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
                self.reset_dirty()
            else:
                # 揃っていない場合、単にクリア
                self._output = None
                self.reset_dirty()

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
) -> "AISImage":
    """
    self を元に「無効っぽい見た目の画像」を生成する

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


class ImageModel:
    """
    画像を表すクラス
    View-Model 的な意味でのモデル
    """

    def __init__(
        self, raw_image: Optional[AISImage] = None, time_stamp: Optional[str] = None
    ):
        """
        コンストラクタ

        Args:
            raw_image (AISImage): 元画像
        """
        # メタデータ
        self._enable = True
        self._time_stamp = None

        # 各画像メンバ
        self._raw_image = CachedSourceImage()
        self._nime_image = CachedScalableImage(self._raw_image, ResizeMode.COVER)
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

        # 初期設定呼び出し
        self.set_raw_image(raw_image, time_stamp)

    def set_enable(self, enable: bool) -> "ImageModel":
        """
        モデルの有効・無効を切り替える
        """
        if self._enable != enable:
            self._enable = enable
            self._thumbnail_pil_image_enable.set_dirty()
            self._thumbnail_pil_image_disable.set_dirty()
            self._notify(ImageLayer.THUMBNAIL)
        return self

    @property
    def enable(self) -> bool:
        """
        モデルの有効・無効を取得する
        """
        return self._enable

    @property
    def time_stamp(self) -> Optional[str]:
        """
        この画像の撮影日時を表すタイムスタンプ
        """
        return self._time_stamp

    def set_raw_image(
        self, raw_image: Optional[AISImage], time_stamp: Optional[str]
    ) -> Self:
        """
        RAW 画像を設定する。
        それまでの全ては吹き飛ぶ。
        タイムスタンプも強制的に更新される。

        Args:
            raw_image (AISImage): 新しい RAW 画像
            time_stamp (Optional[str]): 新しいタイムスタンプ

        Returns:
            ImageModel: 自分自身
        """
        # RAW 画像に反映
        self._raw_image.set_source(raw_image)

        # タイムスタンプを更新
        self.set_time_stamp(time_stamp)

        # 通知
        self._notify(ImageLayer.RAW)

        # 正常終了
        return self

    def set_time_stamp(self, time_stamp: Optional[str]) -> Self:
        """
        タイムスタンプを設定する
        RAW 画像は更新されない。
        """
        # タイムスタンプ更新
        if isinstance(time_stamp, str):
            if is_time_stamp(time_stamp):
                self._time_stamp = time_stamp
            else:
                raise ValueError(time_stamp)
        elif time_stamp is None:
            self._time_stamp = current_time_stamp()
        else:
            TypeError(time_stamp)

        # 正常終了
        return self

    def set_size(self, layer: ImageLayer, size: ResizeDesc) -> Self:
        """
        指定 layer のリサイズ挙動を設定する。
        """
        # layer 分岐
        match layer:
            case ImageLayer.RAW:
                raise ValueError("RAW set_size NOT supported.")
            case ImageLayer.NIME:
                self._nime_image.set_size(size)
            case ImageLayer.PREVIEW:
                self._preview_pil_image.set_size(size)
            case ImageLayer.THUMBNAIL:
                self._thumbnail_pil_image_enable.set_size(size)
            case _:
                raise ValueError(layer)

        # 通知
        self._notify(layer)

        # 正常終了
        return self

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

    def _notify(self, layer: ImageLayer) -> Self:
        """
        あらかじめ登録しておいた通知ハンドラを呼び出す。
        layer と、その影響受けるすべてのレイヤーの通知ハンドラが呼び出される。
        画像がダーティー化した時の通知に使われることを想定。
        """
        # ダーティフラグを解決
        match layer:
            case ImageLayer.RAW:
                is_dirty = self._raw_image.is_dirty
            case ImageLayer.NIME:
                is_dirty = self._nime_image.is_dirty
            case ImageLayer.PREVIEW:
                is_dirty = self._preview_pil_image.is_dirty
            case ImageLayer.THUMBNAIL:
                is_dirty = (
                    self._thumbnail_pil_image_enable.is_dirty
                    or self._thumbnail_pil_image_disable
                )
            case _:
                raise ValueError(f"Invalid ImageLayer(={layer})")

        # ダーティ状態ならハンドラを呼び出す
        if is_dirty:
            for handler in self._notify_handlers[layer]:
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
        self._frame_rate = DEFAULT_FRAME_RATE

    def set_enable(self, frame_index: int, enable: bool) -> Self:
        """
        指定フレームの有効・無効を設定する
        """
        # フレームに有効・無効を反映
        frame = self._frames[frame_index]
        does_change = frame.enable != enable
        if does_change:
            frame.set_enable(enable)

        # 全体通知を呼び出す
        # NOTE
        #   原則として、１フレームでも変更があれば動画全体として通知が飛ぶ
        #   よって、グローバルモデルに対して変化を発生させる
        #   グローバルモデルの enable の値そのものは整合する必要がなくて、変化させることが重要
        if does_change:
            self._global_model.set_enable(not self._global_model.enable)

        # 正常終了
        return self

    def get_enable(self, frame_index: int) -> bool:
        """
        指定フレームの有効・無効を取得する
        """
        return self._frames[frame_index].enable

    def set_time_stamp(self, time_stamp: Optional[str]) -> Self:
        """
        動画のタイムスタンプを設定する。
        """
        # NOTE
        #   タイムスタンプはグローバルモデルで一元管理
        #   個別のフレームは触らない
        self._global_model.set_time_stamp(time_stamp)
        return self

    @property
    def time_stamp(self) -> Optional[str]:
        """
        この動画の撮影日時を表すタイムスタンプ
        """
        return self._global_model.time_stamp

    def set_size(self, layer: ImageLayer, size: ResizeDesc) -> Self:
        """
        フレームサイズを設定する
        """
        # 個別のフレームにサイズを設定
        for f in self._frames:
            f.set_size(layer, size)

        # グローバルモデルにサイズを設定
        # NOTE
        #   通知を最後に回したいので _global_model の処理が後
        self._global_model.set_size(layer, size)
        return self

    def get_size(self, layer: ImageLayer) -> ResizeDesc:
        """
        フレームサイズを取得する
        """
        return self._global_model.get_size(layer)

    def insert_frames(
        self, new_frames: Union[ImageModel, List[ImageModel]], position: int = -1
    ) -> Self:
        """
        動画のフレームを挿入する

        Args:
            frames (List[ImageModel]): 挿入するフレーム
            position (int, optional): 挿入位置。-1 の場合は末尾に挿入

        Returns:
            VideoModel: 自分自身
        """
        # リストで統一
        if isinstance(new_frames, ImageModel):
            new_frames = [new_frames]

        # サイズ情報を統一
        for new_frame in new_frames:
            for layer in ImageLayer:
                if layer != ImageLayer.RAW:
                    new_frame.set_size(layer, self._global_model.get_size(layer))

        # タイムスタンプを統一
        for new_frame in new_frames:
            new_frame.set_time_stamp(self._global_model.time_stamp)

        # フレームリストに挿入
        self._frames = self._frames[:position] + new_frames + self._frames[position:]

        # 全体通知を呼び出す
        # NOTE
        #   原則、１フレームでも変更があれば動画全体として通知が飛ぶ
        #   フレームの追加・削除については RAW レイヤーでの変更とみなす
        #   よってグローバルモデルに新規生成した画像を渡して強制的に通知を発生させる
        self._global_model.set_raw_image(
            AISImage.empty("RGB", 8, 8), self._global_model.time_stamp
        )

        # 正常終了
        return self

    def delete_frame(self, position: int) -> Self:
        """
        指定インデックスのフレームを削除する
        """
        # 指定フレームを削除
        self._frames.pop(position)

        # 全体通知を呼び出す
        self._global_model.set_raw_image(
            AISImage.empty("RGB", 8, 8), self._global_model.time_stamp
        )

        # 正常終了
        return self

    def clear_frames(self) -> Self:
        """
        全フレームを削除する
        """
        # 全フレームを削除
        self._frames.clear()

        # 全体通知を呼び出す
        self._global_model.set_raw_image(
            AISImage.empty("RGB", 8, 8), self._global_model.time_stamp
        )

        # 正常終了
        return self

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

    def set_frame_rate(self, frame_rate: int) -> Self:
        """
        再生フレームレートを設定する
        """
        self._frame_rate = frame_rate
        return self

    @property
    def frame_rate(self) -> int:
        """
        再生フレームレート
        """
        return self._frame_rate

    def register_notify_handler(self, layer: ImageLayer, handler: NotifyHandler):
        """
        通知ハンドラーを登録する
        """
        self._global_model.register_notify_handler(layer, handler)


def save_content_model(model: Union[ImageModel, VideoModel]) -> Path:
    """
    model をファイル保存する。
    画像・動画の両方に対応している。

    Args:
        model (Union[IntegratedImage, IntegratedVideo]): 保存したいモデル
        interval_in_ms (int, optional): gif アニメーションのフレーム間隔（ミリ秒）

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
        # raw 画像は必須
        raw_image = model.get_image(ImageLayer.RAW)
        if not isinstance(raw_image, AISImage):
            raise ValueError("Invalid RAW Image")

        # nime 画像は必須
        nime_image = model.get_image(ImageLayer.NIME)
        if not isinstance(nime_image, AISImage):
            raise ValueError("Invalid NIME Image")

        # raw png ファイルの保存が必要か判定
        # NOTE
        #   スチル画像の場合は raw 画像に後から変更が入ることはありえない。
        #   よって、ローカルにファイルが無い場合だけ保存する。
        png_file_path = RAW_DIR_PATH / (model.time_stamp + ".png")
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
        jpeg_file_path = NIME_DIR_PATH / (model.time_stamp + ".jpg")
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
        # raw ディレクトリに zip ファイルを保存
        # NOTE
        #   raw zip ファイルの差分確認は処理的にも対応コスト的に重い。
        #   なので、妥協して毎回保存する。
        # NOTE
        #   raw フレームは enable かどうかを問わずに保存する。
        zip_file_path = RAW_DIR_PATH / (model.time_stamp + ".zip")
        with ZipFile(zip_file_path, "w") as zip_file:
            for idx, img in enumerate(model.iter_frames(ImageLayer.RAW, False)):
                # 無効なフレームはスキップ
                if not isinstance(img, AISImage):
                    continue
                # png ファイルメモリに書き出し
                buf = BytesIO()
                img.pil_image.save(buf, format="PNG", optimize=True)
                buf.seek(0)
                # png メモリイメージを zip ファイルに書き出し
                png_file_name = f"{model.time_stamp}_{idx:03d}.png"
                zip_file.writestr(png_file_name, buf.read())

        # nime ディレクトリに gif アニメーションを保存
        gif_file_path = NIME_DIR_PATH / (model.time_stamp + ".gif")
        nime_frames = [
            f for f in model.iter_frames(ImageLayer.NIME) if isinstance(f, AISImage)
        ]
        nime_frames[0].pil_image.save(
            str(gif_file_path),
            save_all=True,
            append_images=[f for f in nime_frames[1:]],
            duration=1000 // model.frame_rate,
            loop=0,
            disposal=2,
            optimize=True,
        )

        # 正常終了
        return gif_file_path

    else:
        raise TypeError(type(model))


def load_content_model(
    file_path: Path, default_duration_in_sec: int = DEFAULT_FRAME_RATE
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

    # 使用するタイムスタンプを解決
    if is_time_stamp(actual_file_path.stem):
        time_stamp = actual_file_path.stem
    else:
        time_stamp = current_time_stamp()

    # 画像・動画を読み込む
    if actual_file_path.suffix.lower() in IMAGE_EXTENSIONS:
        # 画像ファイルの場合はそのまま読み込む
        pil_image = Image.open(actual_file_path).convert("RGB")
        image_model = ImageModel(AISImage(pil_image), time_stamp)
        return image_model
    elif actual_file_path.suffix.lower() in MOVIE_EXTENSIONS:
        # 動画ファイルの場合はフレームを全て読み込む
        video_model = VideoModel().set_time_stamp(time_stamp)
        delays = []
        with Image.open(actual_file_path) as img:
            try:
                while True:
                    pil_image = img.copy().convert("RGB")
                    video_model.insert_frames(
                        [ImageModel(AISImage(pil_image), time_stamp)]
                    )
                    delays.append(img.info.get("duration", default_duration_in_sec))
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
        avg_delay = sum(delays) / len(delays)
        video_model.set_frame_rate(int(1000 / avg_delay))
        return video_model
    elif actual_file_path.suffix.lower() == ".zip":
        # ZIP ファイルの場合は中身を読み込む
        # NOTE
        #   ZIP ファイルはこのアプリによって出力されたものであることを前提としている
        #   その中身は .png であることを前提としている
        video_model = VideoModel().set_time_stamp(time_stamp)
        with ZipFile(actual_file_path, "r") as zip_file:
            file_list = zip_file.namelist()
            video_model.insert_frames(
                [
                    ImageModel(
                        AISImage(Image.open(zip_file.open(file_name)).convert("RGB")),
                        time_stamp,
                    )
                    for file_name in file_list
                ]
            )
            return video_model
    else:
        raise ValueError("Logic Error")
