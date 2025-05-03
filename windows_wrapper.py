import io
from dataclasses import dataclass
from typing import (
    Optional,
    Generator,
    List,
    Union
)
import re

from PIL import Image

import win32con, win32clipboard
import dxcam_cpp as dxcam


@dataclass
class DXGIOutputInfo:
    '''
    DXGI のアウトプット（モニター）情報を保持するクラス
    '''


    adapter_index: int
    output_index: int
    width: int
    height: int
    primary: bool


    def __str__(self) -> str:
        '''
        DXGI アウトプットの情報を文字列として返す
        :return: DXGI アウトプットの情報の文字列
        '''
        # 必ず表示するベース部分
        sub_strs = [
            f'GPU{self.adapter_index}',
            f'Monitor{self.output_index}',
            f'{self.width}x{self.height}'
        ]

        # プライマリモニターの場合
        if self.primary:
            sub_strs += ['Primary']

        # 正常終了
        return ' '.join(sub_strs)
        

def enumerate_dxgi_outputs() -> Generator[DXGIOutputInfo, None, None]:
    '''
    DXGI のアウトプット（モニター）情報を列挙する
    :return: DXGI アウトプットの情報のリスト
    '''
    # DXGI のアウトプット情報を取得
    for output_str in dxcam.output_info().splitlines():
        # GPU 番号をパース
        m = re.search(r'Device\[(\d)+\]', output_str)
        if m is None:
            raise RuntimeError("Failed to parse DXGI output info(Device).")
        else:
            adapter_index = int(m.group(1))

        # モニター番号をパース
        m = re.search(r'Output\[(\d)+\]', output_str)
        if m is None:
            raise RuntimeError("Failed to parse DXGI output info(Output).")
        else:
            output_index = int(m.group(1))

        # 解像度をパース
        m = re.search(r'Res:\((\d+), (\d+)\)', output_str)
        if m is None:
            raise RuntimeError("Failed to parse DXGI output info(Res).")
        else:
            width = int(m.group(1))
            height = int(m.group(2))

        # プライマリモニターかどうかをパース
        m = re.search(r'Primary:(\w+)', output_str)
        if m is None:
            raise RuntimeError("Failed to parse DXGI output info(Primary).")
        else:
            if m.group(1) == 'True':
                primary = True
            elif m.group(1) == 'False':
                primary = False
            else:
                raise RuntimeError("Failed to parse DXGI output info(Primary).")

        # 構造体に固めて返す
        yield DXGIOutputInfo(
            adapter_index=adapter_index,
            output_index=output_index,
            width=width,
            height=height,
            primary=primary
        )


def image_to_clipboard(image: Image.Image) -> None:
    '''
    画像をクリップボードにコピーする
    :param image: PILのImageオブジェクト
    :return: None
    '''
    # 画像をRGBモードに変換
    image = image.convert("RGB")
    
    # 画像をクリップボードにコピー
    with io.BytesIO() as bmp_io:
        image.save(bmp_io, format="BMP")
        bmp_data = bmp_io.getvalue()

    # BMPヘッダを除去
    data = bmp_data[14:]

    # クリップボードに CF_DIB 形式でデータをセット
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32con.CF_DIB, data)
    win32clipboard.CloseClipboard()
