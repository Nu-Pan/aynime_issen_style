from pathlib import Path
from typing import List

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


def crop_to_aspect_ratio(image: Image.Image, h_ratio: int, v_ratio: int) -> Image.Image:
    """
    image が h_ratio:v_ratio になるように端っこを切り落とす。

    Args:
        image (Image.Image): 入力画像
        h_ratio (int): 所望のアスペクト比（水平）
        v_ratio (int): 所望のアスペクト比（垂直）

    Returns:
        Image.Image: 所望のアスペクト比になった画像
    """
    expected_width_by_height = image.height * h_ratio // v_ratio
    expected_height_by_width = image.width * v_ratio // h_ratio
    if image.width > expected_width_by_height:
        # 左右を切り落とす
        half_expected_width_by_height = expected_width_by_height // 2
        center = image.width // 2
        return image.crop(
            (
                center - half_expected_width_by_height,
                0,
                center + half_expected_width_by_height,
                image.height,
            )
        )
    elif image.height > expected_height_by_width:
        # 上下を切り落とす
        half_expected_height_by_height = expected_height_by_width // 2
        center = image.height // 2
        return image.crop(
            (
                0,
                center - half_expected_height_by_height,
                image.width,
                center + half_expected_height_by_height,
            )
        )
    else:
        # アスペクト比ぴったりの場合はそのまま返す
        return image


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


def save_pil_images_to_gif_file(
    frames: List[Image.Image], interval_in_ms: int, file_path: Path
) -> None:
    """
    frames を gif アニメーションとして file_path に保存する

    Args:
        frames (List[Image.Image]): 連番静止画像
        file_path (Path): 保存先ファイルパス
    """
    # 親ディレクトリがなければ生成
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # 高さが一番小さいやつに揃うように縮小する
    # NOTE
    #   高さは最大 720 で制限（大きすぎるとファイルサイズがヤバい）
    max_width = max([f.width for f in frames])
    min_height = min([f.height for f in frames] + [720])
    frames = [
        isotropic_downscale_image_in_rectangle(f, max_width, min_height) for f in frames
    ]

    # 幅が一番小さいやつに揃うように切り取る
    min_width = min([f.width for f in frames])
    frames = [crop_to_aspect_ratio(f, min_width, min_height) for f in frames]

    # gif ファイル保存
    frames[0].save(
        file_path,
        save_all=True,
        append_images=frames[1:],
        duration=interval_in_ms,
        loop=0,
        disposal=2,
        optimize=True,
    )
