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
from PIL import Image

# Tk/CTk
from PIL.ImageTk import PhotoImage

# utils
from utils.pil import (
    AspectRatioPattern,
    ResizeDesc,
    ResizeMode,
    resize,
    make_disabled_image,
)
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


type AuxProcess = Callable[[Image.Image], Image.Image]
type NotifyHandler = Callable[[], None]
Content = TypeVar("Content", Image.Image, PhotoImage)
ParentContent = TypeVar("ParentContent", Image.Image, PhotoImage)


class CachedContent(Generic[Content, ParentContent], ABC):
    """
    キャッシュツリーの基底クラス
    """

    def __init__(self, parent: Optional["CachedContent[ParentContent, Any]"]):
        """
        コンストラクタ
        """
        # メンバ初期化
        self._parent = parent
        self._known_parent_output: Any = None

    def check_parent(self) -> Tuple[bool, Optional[ParentContent]]:
        """
        自身の記憶（上の親の出力はこうだったはず）と実際の親の出力とを比較した上で、自身の記憶を更新する。
        親の出力が変わった場合は True を返す。
        また、実際の親の出力も返す。
        """
        # 親がいない場合は False
        if self._parent is None:
            raise ValueError("No parent content available.")

        # 親の出力を取得
        parent_output = self._parent.output

        # 変化があった場合、更新して True を返す
        if parent_output != self._known_parent_output:
            self._known_parent_output = parent_output
            return True, parent_output

        # 変化がなかった場合は False を返す
        return False, parent_output

    @abstractmethod
    def resolve_dirty(self) -> Self:
        """
        ダーティー状態を解消する
        """
        pass

    @property
    @abstractmethod
    def output(self) -> Optional[Content]:
        """
        出力を取得する
        apply は暗黙に呼び出される
        """
        pass


class CachedSourceImage(CachedContent[Image.Image, Any]):
    """
    キャッシュツリーに画像を流し込むための「源泉」に当たるクラス。
    """

    type Output = Image.Image

    def __init__(self):
        """
        コンストラクタ
        """
        super().__init__(None)
        self._source = None

    def set_source(self, source: Optional[Image.Image]) -> Self:
        """
        ソース画像を設定する
        """
        self._source = source
        return self

    def resolve_dirty(self) -> Self:
        """
        ダーティー状態を解消する
        """
        # NOTE ソースを素通しなのですることがない
        return self

    @property
    def output(self) -> Optional[Image.Image]:
        """
        出力を取得する
        apply は暗黙に呼び出される
        """
        return self._source


class CachedScalableImage(
    Generic[ParentContent], CachedContent[Image.Image, ParentContent]
):
    """
    拡大縮小とそのキャッシュ機能を持つ画像クラス
    """

    type Output = Image.Image

    def __init__(
        self,
        parent: CachedContent[ParentContent, Any],
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
        self._is_dirty = False
        self._size = ResizeDesc.from_pattern(
            AspectRatioPattern.E_RAW, ResizeDesc.Pattern.E_RAW
        )
        self._output = None

    def set_size(self, size: ResizeDesc) -> Self:
        self._is_dirty |= self._size != size
        self._size = size
        return self

    def resolve_dirty(self) -> Self:
        """
        ダーティー状態を解消する
        """
        # 親の出力を取り込んでダーティフラグに反映
        # NOTE
        #   check_parent は再帰的に実行されるので、
        #   ルートまで変更の有無を見に行くことになる。
        is_parent_changed, parent_content = self.check_parent()
        self._is_dirty |= is_parent_changed

        # ダーティーじゃない場合、何もしない
        if not self._is_dirty:
            return self

        # 必要なものが…
        if parent_content is not None and self._size is not None:
            # 揃っている場合、更新
            if isinstance(parent_content, Image.Image):
                self._output = resize(parent_content, self._size, self._mode)
            else:
                raise TypeError(type(parent_content))
            if self._aux_process is not None:
                self._output = self._aux_process(self._output)
            self._is_dirty = False
        else:
            # 揃っていない場合、単にクリア
            self._output = None
            self._is_dirty = False

        # 正常終了
        return self

    @property
    def size(self) -> Optional[ResizeDesc]:
        """
        目標サイズ
        """
        return self._size

    @property
    def output(self) -> Optional[Image.Image]:
        """
        スケーリング済み画像
        """
        self.resolve_dirty()
        return self._output


class CachedPhotoImage(
    Generic[ParentContent], CachedContent[PhotoImage, ParentContent]
):
    """
    PIL.Image.Image を PIL.ImageTk.PhotoImage に変換してキャッシュするクラス
    """

    type Output = PhotoImage

    def __init__(self, parent: CachedContent[ParentContent, Any]):
        """
        コンストラクタ
        """
        # 基底クラス初期化
        super().__init__(parent)

        # 遅延変数
        self._is_dirty = False
        self._output = None

    def resolve_dirty(self) -> Self:
        """
        ダーティー状態を解消する
        """
        # 親の出力を取り込んでダーティフラグに反映
        # NOTE
        #   check_parent は再帰的に実行されるので、
        #   ルートまで変更の有無を見に行くことになる。
        is_parent_changed, parent_content = self.check_parent()
        self._is_dirty |= is_parent_changed

        # ダーティーじゃない場合、何もしない
        if not self._is_dirty:
            return self

        # 必要なものが…
        if isinstance(parent_content, Image.Image):
            # 揃っている場合、更新
            self._output = PhotoImage(parent_content)
            self._is_dirty = False
        elif parent_content is None:
            # 揃っていない場合、単にクリア
            self._output = None
            self._is_dirty = False
        else:
            # 型が違う場合はエラー
            raise TypeError(type(parent_content))

        # 正常終了
        return self

    @property
    def output(self) -> Optional[PhotoImage]:
        """
        PIL.ImageTk.PhotoImage
        """
        self.resolve_dirty()
        return self._output


class ImageLayer(Enum):
    """
    ImageModel のレイヤー列挙値
    """

    RAW = "RAW"
    NIME = "NIME"
    PREVIEW = "PREVIEW"
    THUMBNAIL = "THUMBNAIL"


class ImageModel:
    """
    画像を表すクラス
    View-Model 的な意味でのモデル
    """

    def __init__(
        self, raw_image: Optional[Image.Image] = None, time_stamp: Optional[str] = None
    ):
        """
        コンストラクタ

        Args:
            raw_image (Image.Image): 元画像
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
        self._preview_photo_image = CachedPhotoImage(self._preview_pil_image)
        self._thumbnail_pil_image_enable = CachedScalableImage(
            self._nime_image, ResizeMode.CONTAIN
        )
        self._thumbnail_photo_image_enable = CachedPhotoImage(
            self._thumbnail_pil_image_enable
        )
        self._thumbnail_pil_image_disable = CachedScalableImage(
            self._nime_image, ResizeMode.CONTAIN, aux_process=make_disabled_image
        )
        self._thumbnail_photo_image_disable = CachedPhotoImage(
            self._thumbnail_pil_image_disable
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
        self._enable = enable
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
        self, raw_image: Optional[Image.Image], time_stamp: Optional[str]
    ) -> Self:
        """
        RAW 画像を設定する。
        それまでの全ては吹き飛ぶ。

        Args:
            raw_image (Image.Image): 新しい RAW 画像
            time_stamp (Optional[str]): 新しいタイムスタンプ

        Returns:
            ImageModel: 自分自身
        """
        # RAW 画像に反映
        self._raw_image.set_source(raw_image)

        # タイムスタンプを決定
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
        指定 layer の画像のサイズを変更する。
        """
        # layer 分岐
        if layer == ImageLayer.RAW:
            raise ValueError("RAW set_size NOT supported.")
        elif layer == ImageLayer.NIME:
            self._nime_image.set_size(size)
        elif layer == ImageLayer.PREVIEW:
            self._preview_pil_image.set_size(size)
        elif layer == ImageLayer.THUMBNAIL:
            self._thumbnail_pil_image_enable.set_size(size)
            self._thumbnail_pil_image_disable.set_size(size)
        else:
            raise ValueError(layer)

        # 正常終了
        return self

    def get_image(self, layer: ImageLayer) -> Union[Image.Image, PhotoImage, None]:
        """
        指定 layer の画像を取得する。
        """
        if layer == ImageLayer.RAW:
            return self._raw_image.output
        elif layer == ImageLayer.NIME:
            return self._nime_image.output
        elif layer == ImageLayer.PREVIEW:
            return self._preview_photo_image.output
        elif layer == ImageLayer.THUMBNAIL:
            if self._enable:
                return self._thumbnail_photo_image_enable.output
            else:
                return self._thumbnail_photo_image_disable.output
        else:
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

    def notify(self, layer: ImageLayer) -> Self:
        """
        あらかじめ登録しておいた通知ハンドラが呼び出される。
        layer と、その影響受けるすべてのレイヤーの通知ハンドラが呼び出される。
        画像がダーティー化した時の通知に使われることを想定。
        """

        # レイヤー１つの処理を関数化
        def notify_single(force: bool, target: ImageLayer) -> bool:
            is_target_layer = layer == target
            if force or is_target_layer:
                for handler in self._notify_handlers[target]:
                    handler()
                return is_target_layer
            else:
                return False

        # 上流側から順番に処理
        # NOTE
        #   要するに、上流でヒットしたら、その下流もヒット扱いにするということ。
        force = False
        force |= notify_single(force, ImageLayer.RAW)
        force |= notify_single(force, ImageLayer.NIME)
        force |= notify_single(force, ImageLayer.PREVIEW)
        force |= notify_single(force, ImageLayer.THUMBNAIL)

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
        self._time_stamp = None
        self._size: Dict[ImageLayer, ResizeDesc] = {
            layer: ResizeDesc.from_pattern(
                AspectRatioPattern.E_RAW, ResizeDesc.Pattern.E_RAW
            )
            for layer in ImageLayer
        }
        self._frames: List[ImageModel] = []
        self._frame_rate = DEFAULT_FRAME_RATE
        self._notify_handlers: List[NotifyHandler] = []

    def set_enable(self, frame_index: int, enable: bool) -> Self:
        """
        指定フレームの有効・無効を設定する
        """
        self._frames[frame_index].set_enable(enable)
        for handler in self._notify_handlers:
            handler()
        return self

    def get_enable(self, frame_index: int) -> bool:
        """
        指定フレームの有効・無効を取得する
        """
        return self._frames[frame_index].enable

    def set_time_stamp(self, time_stamp: Optional[str]) -> Self:
        """
        動画のタイムスタンプを設定する。

        Args:
            time_stamp (Optional[str]): 新しいタイムスタンプ

        Returns:
            VideoModel: 自分自身
        """
        if isinstance(time_stamp, str):
            if is_time_stamp(time_stamp):
                self._time_stamp = time_stamp
            else:
                raise ValueError(time_stamp)
        elif time_stamp is None:
            self._time_stamp = current_time_stamp()
        else:
            TypeError(time_stamp)

        return self

    @property
    def time_stamp(self) -> Optional[str]:
        """
        この画像の撮影日時を表すタイムスタンプ
        """
        return self._time_stamp

    def set_size(self, layer: ImageLayer, size: ResizeDesc) -> Self:
        """
        各フレームサイズを設定する
        """
        self._size[layer] = size
        for f in self._frames:
            f.set_size(layer, size)
        for handler in self._notify_handlers:
            handler()
        return self

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
        for f in new_frames:
            for l in ImageLayer:
                if l != ImageLayer.RAW:
                    f.set_size(l, self._size[l])

        # タイムスタンプを統一
        # NOTE
        #   完全にコピーしたいので、メンバを直接書き換える。
        for f in new_frames:
            f._time_stamp = self._time_stamp

        # フレームリストに挿入
        self._frames = self._frames[:position] + new_frames + self._frames[position:]

        # 通知
        for handler in self._notify_handlers:
            handler()

        # 正常終了
        return self

    def delete_frame(self, position: int) -> Self:
        """
        指定インデックスのフレームを削除する
        """
        self._frames.pop(position)
        for handler in self._notify_handlers:
            handler()
        return self

    def clear_frames(self) -> Self:
        """
        全フレームを削除する
        """
        self._frames.clear()
        for handler in self._notify_handlers:
            handler()
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
    ) -> Generator[Union[Image.Image, PhotoImage, None], None, None]:
        """
        全てのフレームをイテレートする
        """
        for f in self._frames:
            if not enable_only or f.enable:
                yield f.get_image(layer)

    def get_frame(
        self, layer: ImageLayer, frame_index: int
    ) -> Union[Image.Image, PhotoImage, None]:
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

    def register_notify_handler(self, handler: NotifyHandler):
        """
        通知ハンドラーを登録する
        """
        self._notify_handlers.append(handler)


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
        if not isinstance(raw_image, Image.Image):
            raise ValueError("Invalid RAW Image")

        # nime 画像は必須
        nime_image = model.get_image(ImageLayer.NIME)
        if not isinstance(nime_image, Image.Image):
            raise ValueError("Invalid NIME Image")

        # raw png ファイルの保存が必要か判定
        # NOTE
        #   スチル画像の場合は raw 画像に後から変更が入ることはありえない。
        #   よって、ローカルにファイルが無い場合だけ保存する。
        png_file_path = RAW_DIR_PATH / (model.time_stamp + ".png")
        save_png = not png_file_path.exists()

        # raw ディレクトリに png 画像を保存
        if save_png:
            raw_image.convert("RGB").save(
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
        nime_image.convert("RGB").save(
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
                if not isinstance(img, Image.Image):
                    continue
                # png ファイルメモリに書き出し
                buf = BytesIO()
                img.save(buf, format="PNG", optimize=True)
                buf.seek(0)
                # png メモリイメージを zip ファイルに書き出し
                png_file_name = f"{model.time_stamp}_{idx:03d}.png"
                zip_file.writestr(png_file_name, buf.read())

        # nime ディレクトリに gif アニメーションを保存
        gif_file_path = NIME_DIR_PATH / (model.time_stamp + ".gif")
        nime_frames = [
            f for f in model.iter_frames(ImageLayer.NIME) if isinstance(f, Image.Image)
        ]
        nime_frames[0].save(
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

    # 使用するタイムスタンプを解決
    if is_time_stamp(actual_file_path.stem):
        time_stamp = actual_file_path.stem
    else:
        time_stamp = current_time_stamp()

    # 画像・動画を読み込む
    if actual_file_path.suffix.lower() in IMAGE_EXTENSIONS:
        # 画像ファイルの場合はそのまま読み込む
        pil_image = Image.open(actual_file_path).convert("RGB")
        image_model = ImageModel(pil_image, time_stamp)
        return image_model
    elif actual_file_path.suffix.lower() in MOVIE_EXTENSIONS:
        # 動画ファイルの場合はフレームを全て読み込む
        video_model = VideoModel().set_time_stamp(time_stamp)
        delays = []
        with Image.open(actual_file_path) as img:
            try:
                while True:
                    pil_image = img.copy().convert("RGB")
                    video_model.insert_frames([ImageModel(pil_image, time_stamp)])
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
                        Image.open(zip_file.open(file_name)).convert("RGB"), time_stamp
                    )
                    for file_name in file_list
                ]
            )
            return video_model
    else:
        raise ValueError("Logic Error")
