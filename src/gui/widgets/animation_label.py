# std
from typing import List, Optional

# Tk/CTk
import customtkinter as ctk

# utils
from utils.ctk import configure_presence
from utils.image import ResizeDesc, AspectRatioPattern, AISImage

# gui
from gui.model.aynime_issen_style import AynimeIssenStyleModel
from gui.model.contents_cache import ImageLayer, PlaybackMode, VideoModelEditSession


class AnimationLabel(ctk.CTkLabel):
    """
    連番静止画をアニメーション再生する用のラベル
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        model: AynimeIssenStyleModel,
        blank_text: Optional[str] = None,
        **kwargs,
    ):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # 現在表示している画像
        # NOTE
        #   現在表示している画像のインスタンスをウィジェットから取ることはできない。
        #   そのため、この階層でキャッシュ情報を保持しておく
        self._current_frame = None

        # REFLECT モード時の再生方向
        self._reflect_seek_direction = 1

        # 内部状態を適当に初期化
        self._model = model
        self._frame_index = None
        if blank_text is None:
            self._blank_text = "Animation Preview"
        else:
            self._blank_text = blank_text

        # リサイズハンドラ
        self.bind("<Configure>", self._on_resize)

        # 更新処理をキック
        self._next_frame_handler()

    def _next_frame_handler(self):
        """
        表示状態を次のフレームに進めるハンドラ
        """
        # 表示フレーム番号を解決
        if self._model.video.num_enable_frames == 0:
            # 表示すべきフレームが無い場合は None
            self._frame_index = None

        elif self._model.video.num_enable_frames == 1:
            # １フレームだけの場合、唯一の有効フレームを特定
            for i in range(self._model.video.num_total_frames):
                if self._model.video.get_enable(i):
                    self._frame_index = i
                    break

        elif self._model.video.num_enable_frames > 1:
            # ２フレーム以上なら、通常のフレーム進行

            # フレーム番号が None なら 0 初期化
            if self._frame_index is None:
                self._frame_index = 0

            # 次の有効フレームまでシーク
            while True:
                # １フレームだけシーク
                match self._model.playback_mode:
                    case PlaybackMode.FORWARD:
                        self._frame_index += 1
                        if self._frame_index >= self._model.video.num_total_frames:
                            self._frame_index = 0
                    case PlaybackMode.BACKWARD:
                        self._frame_index -= 1
                        if self._frame_index < 0:
                            self._frame_index = self._model.video.num_total_frames - 1
                    case PlaybackMode.REFLECT:
                        self._frame_index += self._reflect_seek_direction
                        if self._frame_index < 0:
                            self._frame_index = 1
                            self._reflect_seek_direction = 1
                        elif self._frame_index >= self._model.video.num_total_frames:
                            self._frame_index = self._model.video.num_total_frames - 2
                            self._reflect_seek_direction = -1
                        else:
                            pass

                # 有効フレームなら、ここで決定
                if self._model.video.get_enable(self._frame_index):
                    break

        # プレビュー画像を取得・表示
        if self._frame_index is None:
            configure_presence(self, self._blank_text)
        elif isinstance(self._frame_index, int):
            new_frame = self._model.video.get_frame(
                ImageLayer.PREVIEW, self._frame_index
            )
            if new_frame != self._current_frame:
                if isinstance(new_frame, AISImage):
                    configure_presence(self, new_frame.photo_image)
                    self._current_frame = new_frame
                else:
                    configure_presence(self, self._blank_text)
                    self._current_frame = None
        else:
            raise TypeError(f"Invalid Type {self._frame_index}")

        # 次の更新処理をキック
        self.after(self._model.video.duration_in_msec, self._next_frame_handler)

    def _on_resize(self, _):
        """
        リサイズハンドラ
        """
        # 適切なサイズを解決
        actual_width = self.winfo_width()
        actual_height = self.winfo_height()
        with VideoModelEditSession(self._model.video) as edit:
            edit.set_size(
                ImageLayer.PREVIEW,
                ResizeDesc(AspectRatioPattern.E_RAW, actual_width, actual_height),
            )
