# std
from typing import Optional, cast, Union, List, Callable
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile
from io import BytesIO
from statistics import mode

# PIL
from PIL import Image

# utils
from .pil import (
    AspectRatio,
    Resolution,
    resize_cover_pattern_size,
    resize_contain_free_size,
    make_disabled_image,
)
from .constants import NIME_DIR_PATH, RAW_DIR_PATH


class IntegratedImage:
    """
    「統合」された画像を表すデータクラス
    - nime_image: NIME 用の画像（JPEG）
    - raw_image: 元画像（PNG）
    """

    def __init__(self, raw_image: Image.Image, time_stamp: Optional[str]):
        """
        コンストラクタ

        Args:
            raw_image (Image.Image): 元画像
        """
        # RAW
        # NOTE
        #   あれこれ編集を加える前の画像
        #   キャプチャしたまんまの画像
        self._raw_image = raw_image

        # NIME
        # NOTE
        #   ファイル保存用にリサイズされた画像
        self._nime_image = None
        self._nime_aspect_ratio = AspectRatio.E_RAW
        self._nime_resolution = Resolution.E_RAW

        # プレビュー
        # NOTE
        #   UI 上でプレビューする用にリサイズされた画像
        self._preview_image = None
        self._preview_width = None
        self._preview_height = None

        # サムネ
        # NOTE
        #   UI 上でサムネ表示する用にリサイズされた画像
        #   無効状態を表す
        self._thumbnail_image_enabled = None
        self._thumbnail_image_disabled = None
        self._thumbnail_width = None
        self._thumbnail_height = None

        # タイムスタンプ
        # NOTE
        #   キャプチャの同一性を判定するための ID としてタイムスタンプを使う
        if time_stamp is None:
            self._time_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        else:
            self._time_stamp = time_stamp

        # NIME 画像変更ハンドラ
        self._on_nime_changed_handlers = []

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
        # キャッシュ画像が存在するか
        cache_available = self._nime_image is not None

        # アスペクト比に変更があるか
        if aspect_ratio is None:
            if self._nime_aspect_ratio is None:
                raise ValueError("No aspect ratio info")
            else:
                aspect_ratio_changed = False
        else:
            if self._nime_aspect_ratio is None:
                aspect_ratio_changed = True
            else:
                aspect_ratio_changed = aspect_ratio != self._nime_aspect_ratio

        # 解像度に変更があるか
        if resolution is None:
            if self._nime_resolution is None:
                raise ValueError("No aspect ratio info")
            else:
                resolution_changed = False
        else:
            if self._nime_resolution is None:
                resolution_changed = True
            else:
                resolution_changed = resolution != self._nime_resolution

        # 再生成が不要な場合はキャッシュから返す
        use_cache = (
            cache_available and not aspect_ratio_changed and not resolution_changed
        )
        if use_cache:
            return cast(Image.Image, self._nime_image)

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

        # 変更を通知
        for handler in self._on_nime_changed_handlers:
            handler()

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
        # キャッシュ画像が存在するか
        cache_available = self._preview_image is not None

        # width に変更があるか
        if width is None:
            if self._preview_width is None:
                raise ValueError("No preview width info")
            else:
                width_changed = False
        else:
            if self._preview_width is None:
                width_changed = True
            else:
                width_changed = width != self._preview_width

        # height に変更があるか
        if height is None:
            if self._preview_height is None:
                raise ValueError("No preview height info")
            else:
                height_changed = False
        else:
            if self._preview_height is None:
                height_changed = True
            else:
                height_changed = height != self._preview_height

        # 再生成が不要な場合はキャッシュから返す
        use_cache = cache_available and not width_changed and not height_changed
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
        # キャッシュ画像が存在するか
        cache_available = (
            self._thumbnail_image_enabled is not None
            and self._thumbnail_image_disabled is not None
        )

        # width に変更があるか
        if width is None:
            if self._thumbnail_width is None:
                raise ValueError("No thumbnail width info")
            else:
                width_changed = False
        else:
            if self._thumbnail_width is None:
                width_changed = True
            else:
                width_changed = width != self._thumbnail_width

        # height に変更があるか
        if height is None:
            if self._thumbnail_height is None:
                raise ValueError("No thumbnail height info")
            else:
                height_changed = False
        else:
            if self._thumbnail_height is None:
                height_changed = True
            else:
                height_changed = height != self._thumbnail_height

        # 再生成が不要な場合はキャッシュから返す
        use_cache = cache_available and not width_changed and not height_changed
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

    @property
    def time_stamp(self) -> str:
        """
        この画像の撮影日時を表すタイムスタンプ
        """
        return self._time_stamp

    def register_on_nime_changed(self, handler: Callable):
        """
        NIME 画像に変更があったときに呼び出されるハンドラを登録する

        Args:
            handler (Callable): NIME 画像変更ハンドラ
        """
        self._on_nime_changed_handlers.append(handler)


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

    # 画像・動画を保存する
    if isinstance(image, IntegratedImage):
        # nime ディレクトリに jpeg 画像を保存
        jpeg_file_path = NIME_DIR_PATH / (image.time_stamp + ".jpg")
        image.nime().convert("RGB").save(
            str(jpeg_file_path),
            format="JPEG",
            quality=92,
            optimize=True,
            progressive=True,
        )

        # raw png ファイルの保存が必要か判定
        # NOTE
        #   スチル画像の場合は raw 画像に後から変更が入ることはありえない。
        #   よって、ローカルにファイルが無い場合だけ保存する。
        png_file_path = RAW_DIR_PATH / (image.time_stamp + ".png")
        save_png = not png_file_path.exists()

        # raw ディレクトリに png 画像を保存
        if save_png:
            image.raw().convert("RGB").save(
                str(png_file_path),
                format="PNG",
                optimize=True,
                compress_levvel=9,
                transparency=(0, 0, 0),
            )

        # 正常終了
        return jpeg_file_path

    elif isinstance(image, list):
        # タイムスタンプ文字列を解決
        # NOTE
        #   一番出現頻度の高いタイムスタンプ文字列を使う
        time_stamp = mode([i.time_stamp for i in image])

        # nime ディレクトリに gif アニメーションを保存
        gif_file_path = NIME_DIR_PATH / (time_stamp + ".gif")
        image[0].nime().save(
            str(gif_file_path),
            save_all=True,
            append_images=[img.nime() for img in image[1:]],
            duration=interval_in_ms,
            loop=0,
            disposal=2,
            optimize=True,
        )

        # raw zip ファイルの保存が必要か判定
        # NOTE
        #   アニメの場合、フレーム一覧に変更が発生している可能性があるので、
        #   中身をみて差分の有無を確認する。
        zip_file_path = RAW_DIR_PATH / (time_stamp + ".zip")
        if zip_file_path.exists():
            local_time_stamps = "".join([i.time_stamp for i in image])
            with ZipFile(zip_file_path, mode="r") as zip_file:
                zip_time_stamps = "".join(
                    [Path(info.filename).stem for info in zip_file.infolist()]
                )
            save_raw = local_time_stamps != zip_time_stamps
        else:
            save_raw = True

        # raw ディレクトリに zip ファイルを保存
        if save_raw:
            with ZipFile(zip_file_path, "w") as zip_file:
                for idx, img in enumerate(image):
                    # png ファイルメモリに書き出し
                    buf = BytesIO()
                    img.raw().save(buf, format="PNG", optimize=True)
                    buf.seek(0)
                    # png メモリイメージを zip ファイルに書き出し
                    png_file_name = f"{time_stamp}_{idx:03d}.png"
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
        return IntegratedImage(pil_image, actual_file_path.stem)
    elif actual_file_path.suffix.lower() in MOVIE_EXTENSIONS:
        # 動画ファイルの場合はフレームを全て読み込む
        frames: List[IntegratedImage] = []
        with Image.open(actual_file_path) as img:
            try:
                while True:
                    pil_image = img.copy().convert("RGB")
                    frames.append(IntegratedImage(pil_image, actual_file_path.stem))
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
                IntegratedImage(
                    Image.open(zip_file.open(file_name)).convert("RGB"),
                    actual_file_path.stem,
                )
                for file_name in file_list
            ]
            return frames
    else:
        raise ValueError("Logic Error")
