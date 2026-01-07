# std
import base64
from enum import Enum
import json
import re
import zlib
from typing import Any, Callable, Self, cast


# utils
from utils.ais_logging import write_log


class AspectRatioPattern(Enum):
    """
    典型的なアスペクト比の列挙値
    """

    E_16_9 = "16:9"
    E_4_3 = "4:3"
    E_1_1 = "1:1"
    E_RAW = "RAW"  # オリジナルのアスペクト比をそのまま使う


class PlaybackMode(Enum):
    FORWARD = "FORWARD"
    BACKWARD = "BACKWARD"
    REFLECT = "REFLECT"


class ResolutionPattern(Enum):
    """
    典型的な解像度を定義する列挙型
    横幅だけを定義する
    """

    E_DISCORD_EMOJI = "128"  # Dsicord 絵文字のサイズ
    E_DISCORD_STAMP = "320"  # Discord スタンプのサイズ
    E_480 = "480"  # 2000 年代 gif 職人的サイズ
    E_VGA = "640"
    E_QHD = "960"
    E_HD = "1280"
    E_FHD = "1920"
    E_3K = "2880"
    E_4K = "3840"
    E_X_TWITTER_STILL_LIMIT = "4096"  # X(Twitter) の静止画の上限サイズ（長辺側）
    E_RAW = "RAW"  # オリジナルの解像度をそのまま使う


class ContentsMetadata:
    """
    一閃流が出力するスチル・ビデオファイルに格納されるメタデータ
    シリアライズ・デシリアライズの挙動をこのクラスで記述する
    """

    _PREFIX = f"aismeta1:zlib+b64:"
    _XMP_NAME_SPACE = "ais"
    _XMP_PROPERTY_PATH = f"{_XMP_NAME_SPACE}:metadata_body"
    _XMP_PROPERTY_RE = re.compile(_XMP_PROPERTY_PATH + r'="([^"]*)"')

    def __init__(
        self,
        *,
        _overlay_nime_name: Any = None,
        _crop_params: Any = None,
        _resize_aspect_ratio_pattern: Any = None,
        _resize_resolution_pattern: Any = None,
        _playback_mode: Any = None,
        _disabled_frame_indices: Any = None,
        **_ignored: Any,
    ):
        """
        コンストラクタ

        NOTE
            ファイルから読み出されたメタデータ dict がそのまま渡されることを想定している
            キーが足りてなければ、デフォルト値にフォールバックする
            値が合法でなければ、デフォルト値にフォールバックする
        """
        # NIME 名オーバーレイ表示可否
        if isinstance(_overlay_nime_name, bool):
            self._overlay_nime_name = _overlay_nime_name
        else:
            self._overlay_nime_name = None

        # 正方形切り出し設定
        # NOTE
        #   pylance が型情報をうまく拾ってくれないので cast でダメ押し
        if (
            isinstance(_crop_params, list)
            and len(_crop_params) == 3
            and all(isinstance(x, float) or x is None for x in _crop_params)
        ):
            self._crop_params = cast(
                tuple[float | None, float | None, float | None], tuple(_crop_params)
            )
        else:
            self._crop_params = None

        # リサイズアス比
        try:
            self._resize_aspect_ratio_pattern = AspectRatioPattern(
                _resize_aspect_ratio_pattern
            )
        except:
            self._resize_aspect_ratio_pattern = None

        # リサイズ解像度
        try:
            self._resize_resolution_pattern = ResolutionPattern(
                _resize_resolution_pattern
            )
        except:
            self._resize_resolution_pattern = None

        # 再生モード
        try:
            self._playback_mode = PlaybackMode(_playback_mode)
        except:
            self._playback_mode = None

        # フレーム個別無効化
        if isinstance(_disabled_frame_indices, set) and all(
            isinstance(x, int) for x in _disabled_frame_indices
        ):
            self._disabled_frame_indices = _disabled_frame_indices
        else:
            self._disabled_frame_indices = None

        # TODO _ignored がある場合は警告出す

    @property
    def overlay_nime_name(self) -> bool | None:
        return self._overlay_nime_name

    def set_overlay_nime_name(self, overlay_nime_name: bool | None) -> Self:
        self._overlay_nime_name = overlay_nime_name
        return self

    @property
    def crop_params(self) -> tuple[float | None, float | None, float | None] | None:
        return self._crop_params

    def set_crop_params(
        self, crop_params: tuple[float | None, float | None, float | None] | None
    ) -> Self:
        self._crop_params = crop_params
        return self

    @property
    def resize_aspect_ratio_pattern(self) -> AspectRatioPattern | None:
        return self._resize_aspect_ratio_pattern

    def set_resize_aspect_ratio_pattern(
        self, resize_aspect_ratio_pattern: AspectRatioPattern | None
    ) -> Self:
        self._resize_aspect_ratio_pattern = resize_aspect_ratio_pattern
        return self

    @property
    def resize_resolution_pattern(self) -> ResolutionPattern | None:
        return self._resize_resolution_pattern

    def set_resize_resolution_pattern(
        self, resize_resolution_pattern: ResolutionPattern | None
    ) -> Self:
        self._resize_resolution_pattern = resize_resolution_pattern
        return self

    @property
    def playback_mode(self) -> PlaybackMode | None:
        return self._playback_mode

    def set_playback_mode(self, playback_mode: PlaybackMode | None) -> Self:
        self._playback_mode = playback_mode
        return self

    @property
    def disable_frame_indices_is_none(self) -> bool:
        return self._disabled_frame_indices is None

    def is_frame_enable(self, frame_index: int) -> bool:
        if self._disabled_frame_indices is None:
            return True
        else:
            return frame_index not in self._disabled_frame_indices

    def set_frame_enable(self, frame_index: int, frame_enable: bool) -> Self:
        # 無効化フレーム集合がある状態にする
        if self._disabled_frame_indices is None:
            self._disabled_frame_indices = set()
        # 集合を編集
        if frame_enable:
            if frame_index in self._disabled_frame_indices:
                self._disabled_frame_indices.remove(frame_index)
        else:
            self._disabled_frame_indices.add(frame_index)
        # 正常終了
        return self

    def erase_frame_enable(self):
        self._disabled_frame_indices = None

    @property
    def to_str(self) -> str:
        """
        str にシリアライズする
        """

        # 型変換ヘルパー
        def _sanitize_vars(
            d: dict[str, Any],
            k: str,
            c: Callable[
                [
                    Any,
                ],
                Any,
            ],
        ) -> None:
            if k in d and d[k] is not None:
                d[k] = c(d[k])

        # メンバーを dict 化
        # NOTE
        #   値は json シリアライズ可能な型に変換する
        metadata_dict = dict(vars(self))
        _sanitize_vars(metadata_dict, "_resize_aspect_ratio_pattern", lambda v: v.value)
        _sanitize_vars(metadata_dict, "_resize_resolution_pattern", lambda v: v.value)
        _sanitize_vars(metadata_dict, "_playback_mode", lambda v: v.value)
        _sanitize_vars(metadata_dict, "_disabled_frame_indices", lambda v: list(v))

        # 　シリアライズ
        # NOTE
        #   要件としては…
        #   - 文字コード関連のトラブルを避けたいので base64 エンコードしたい
        #   - ファイルサイズ増大を避けたいから zip 圧縮したい
        #   で、結果的に、
        #   dict --> str(json) --> bytes(zip) --> str(base64)
        #   という流れに落ち着いた。
        metadata_body = json.dumps(
            metadata_dict,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        metadata_body = metadata_body.encode("utf-8")
        metadata_body = zlib.compress(metadata_body, level=9)
        metadata_body = ContentsMetadata._PREFIX + base64.b64encode(
            metadata_body
        ).decode("ascii")
        # 正常終了
        return metadata_body

    @property
    def to_xmp(self) -> bytes:
        """
        xmp 用にシリアライズする
        """
        # NOTE
        #   namespace 内にプロパティが１つあるだけの簡単な構造
        #   プロパティの中身は to_str をそのまま使う
        #   to_str が返すのは base64 エンコード済みなので XMP エスケープは不要
        xmp_body = (
            f"""<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">"""
            f"""<rdf:Description xmlns:{ContentsMetadata._XMP_NAME_SPACE}="https://example.com/aynime/1.0/" {ContentsMetadata._XMP_PROPERTY_PATH}="{self.to_str}" />"""
            f"""</rdf:RDF>"""
        )
        return xmp_body.encode("utf-8")

    @classmethod
    def from_str(cls, body: str | bytes | bytearray) -> "ContentsMetadata":
        """
        str からデシリアライズする
        途中失敗した場合はデフォルト値でフォールバック
        """
        # 入力を str に統一
        if isinstance(body, str):
            body_str = body
        elif isinstance(body, (bytes, bytearray)):
            body_str = body.decode("ascii", errors="strict")
        else:
            raise TypeError(f"Invalid type of body ({type(body)})")

        # プリフィックスが想定通りかチェック
        actual_prefix = body_str[: len(ContentsMetadata._PREFIX)]
        if actual_prefix != ContentsMetadata._PREFIX:
            # NOTE
            #   外部画像をロードした場合、 一閃流と関係ないコメントが入ってくる可能性がある。
            #   普通にありえる話なので、正常系とみなしてログは出さない。
            return ContentsMetadata()

        # デシリアライズ
        try:
            result = body_str[len(ContentsMetadata._PREFIX) :]
            result = base64.b64decode(result)
            result = zlib.decompress(result).decode("utf-8")
            result = json.loads(result)
        except:
            write_log(
                "warning",
                f"Failed to deserialize contents metadata (body_str={body_str})",
            )
            return ContentsMetadata()

        # メンバー復元ヘルパー
        def _restore_vars(d: dict[str, Any], k: str, c: Callable[[Any], Any]) -> None:
            if k in d and d[k] is not None:
                d[k] = c(d[k])

        # json の都合で無毒化されているメンバを復元する
        _restore_vars(
            result, "_resize_aspect_ratio_pattern", lambda v: AspectRatioPattern(v)
        )
        _restore_vars(
            result, "_resize_resolution_pattern", lambda v: ResolutionPattern(v)
        )
        _restore_vars(result, "_playback_mode", lambda v: PlaybackMode(v))
        _restore_vars(result, "_disabled_frame_indices", lambda v: set(v))

        # 正常終了
        return ContentsMetadata(**result)

    @classmethod
    def from_xmp(cls, body: bytes | bytearray) -> "ContentsMetadata":
        """
        xmp からデシリアライズする
        """
        # str にデコード
        try:
            body_str = body.decode("utf-8", errors="replace")
        except:
            write_log("warning", f"Failed to decode contents metadata bytes")
            return ContentsMetadata()

        # 正規表現でパース
        property_match = ContentsMetadata._XMP_PROPERTY_RE.search(body_str)
        if not property_match:
            # NOTE
            #   外部画像をロードした場合、 一閃流と関係ない XMP が入ってくる可能性がある。
            #   普通にありえる話なので、正常系とみなしてログは出さない。
            return ContentsMetadata()

        # comment 版に転送
        return ContentsMetadata.from_str(property_match.group(1))
