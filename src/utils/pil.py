from pathlib import Path
from PIL import Image


def isotropic_downscale_image_in_rectangle(
    image: Image.Image, rectangle_width: int, rectangle_height: int
) -> Image.Image:
    """
    image を rectangle_width, rectangle_height に収まるように縮小する
    収縮前後でアスペクト比は維持される
    image のほうが小さい場合、拡大は行われない

    Args:
        image (Image.Image): 入力画像
        rectangle_width (int): 縮小後サイズ（横）
        rectangle_height (int): 縮小後サイズ（縦）

    Returns:
        Image.Image: 縮小された画像
    """
    # 矩形のアスペクト比を計算
    rectangle_aspect_ratio = rectangle_width / rectangle_height

    # 画像のアスペクト比を計算
    image_aspect_ratio = image.width / image.height

    # 縮小率を計算
    if image_aspect_ratio > rectangle_aspect_ratio:
        scale = rectangle_width / image.width
    else:
        scale = rectangle_height / image.height

    # ダウンスケール不要な場合は入力をそのまま返す
    if scale >= 1.0:
        return image

    # 画像を縮小
    new_size = (int(image.width * scale), int(image.height * scale))
    return image.resize(new_size, Image.Resampling.BILINEAR)


def save_pil_image_to_jpeg_file(image: Image.Image, file_path: Path) -> None:
    """
    image を jpeg 圧縮して file_path に保存する。

    Args:
        image (Image.Image): 保存したい画像
        file_path (Path): 保存先ファイルパス
    """
    # 親ディレクトリがなければ生成
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 圧縮・ファイル保存
    image.convert("RGB").save(
        str(file_path), format="JPEG", quality=92, optimize=True, progressive=True
    )
