
from PIL import Image


def isotropic_scale_image_in_rectangle(
    image: Image.Image,
    rectangle_width: int,
    rectangle_height: int
) -> Image.Image:
    '''
    画像を指定された矩形に収まるように等比縮小する
    :param image: PILのImageオブジェクト
    :param rectangle_width: 矩形の幅
    :param rectangle_height: 矩形の高さ
    :return: 矩形に収まるように縮小された画像
    '''
    # 矩形のアスペクト比を計算
    rectangle_aspect_ratio = rectangle_width / rectangle_height

    # 画像のアスペクト比を計算
    image_aspect_ratio = image.width / image.height

    # 縮小率を計算
    if image_aspect_ratio > rectangle_aspect_ratio:
        scale = rectangle_width / image.width
    else:
        scale = rectangle_height / image.height

    # 画像を縮小
    new_size = (int(image.width * scale), int(image.height * scale))
    return image.resize(new_size, Image.Resampling.BILINEAR)
