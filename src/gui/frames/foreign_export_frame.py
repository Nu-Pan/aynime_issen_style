# std
from typing import cast, Callable
from pathlib import Path
from enum import Enum


# Tk/CTk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent

# utils
from utils.image import AspectRatioPattern, Resolution, ResolutionPattern, ResizeDesc
from utils.windows import file_to_clipboard
from utils.ctk import show_notify_label, show_error_dialog
from utils.capture import *
from utils.constants import (
    DEFAULT_FONT_FAMILY,
    WIDGET_MIN_WIDTH,
    TENSEI_DIR_PATH,
)
from utils.duration_and_frame_rate import (
    DFR_MAP,
)
from utils.image import apply_color_palette

# gui
from gui.widgets.ais_frame import AISFrame
from gui.widgets.ais_slider import AISSlider
from gui.widgets.video_label import VideoLabel, VideoModelEditSession
from gui.model.aynime_issen_style import AynimeIssenStyleModel
from gui.model.contents_cache import (
    ImageLayer,
    PlaybackMode,
    ImageModel,
    VideoModel,
    load_content_model,
)


type NotifyHandler = Callable[[], None]


class ExportTarget(Enum):
    DISCORD_EMOJI = "Discord Emoji"
    DISCORD_STAMP = "Discord Stamp"
    X_TWITTER = "X(Twitter)"


class ExportTargetRadioFrame(AISFrame):
    """
    エクスポート先を選択する用のラジオボタンを格納するフレーム
    """

    def __init__(self, master: ctk.CTkBaseClass, **kwargs):
        """
        コンストラクタ
        """
        super().__init__(master, **kwargs)

        # フォントを生成
        default_font = ctk.CTkFont(DEFAULT_FONT_FAMILY)

        # レイアウト設定
        self.ais.rowconfigure(0, weight=1)

        # 再生モード変数
        self._export_targe_var = ctk.StringVar(value=ExportTarget.X_TWITTER.value)

        # 再生モードラジオボタン
        self._radio_buttons: list[ctk.CTkRadioButton] = []
        for i, export_target in enumerate(ExportTarget):
            radio_button = ctk.CTkRadioButton(
                self,
                text=export_target.value,
                variable=self._export_targe_var,
                value=export_target.value,
                command=self._on_radio_button_changed,
                font=default_font,
            )
            self.ais.grid_child(radio_button, 0, i, sticky="ns")
            self.ais.columnconfigure(i, weight=1)
            self._radio_buttons.append(radio_button)

        # ハンドラリスト
        self._handlers: list[NotifyHandler] = []

    @property
    def value(self) -> ExportTarget:
        """
        現在選択されている値を取得
        """
        return ExportTarget(self._export_targe_var.get())

    def register_on_radio_button_changed(self, handler: NotifyHandler):
        """
        再生モードラジオボタンに変化があった時に呼び出されるハンドラを登録する
        """
        self._handlers.append(handler)

    def _on_radio_button_changed(self):
        """
        再生モードラジオボタンに変化があった時に呼び出されるハンドラ
        """
        for handler in self._handlers:
            handler()


class ForeignExportFrame(AISFrame, TkinterDnD.DnDWrapper):
    """
    いろんなサービス（Foreign）向けのエクスポート操作をサポートする CTk フレーム
    """

    UI_TAB_NAME = "転生"

    def __init__(self, master, model: AynimeIssenStyleModel, **kwargs):
        """
        コンストラクタ

        Args:
            master (_type_): 親ウィジェット
            model (AynimeIssenStyleModel): モデル
        """
        super().__init__(master, **kwargs)

        # メンバー保存
        self._model = model

        # レイアウト設定
        self.ais.columnconfigure(0, weight=1)

        # 切り取り結果プレビュー
        self._preview_label = VideoLabel(self, model.foreign, "Drop NIME File HERE")
        self.ais.grid_child(self._preview_label, 0, 0, 1, 2)
        self.ais.rowconfigure(0, weight=1)

        # エクスポート先ラジオボタン
        self._export_target_radio = ExportTargetRadioFrame(self)
        self.ais.grid_child(self._export_target_radio, 1, 0)
        self._export_target_radio.register_on_radio_button_changed(
            self._on_widget_parameter_changed
        )

        # 切り出し正方形サイズスライダー
        self._crop_square_size_slider = AISSlider(
            self,
            "SIZE",
            [min(1.0, max(0.0, i / 100)) for i in range(0, 101)],
            lambda lho, rho: abs(lho - rho),
            lambda x: f"{round(x * 100):3d}",
            "%",
        )
        self.ais.grid_child(self._crop_square_size_slider, 2, 0)
        self._crop_square_size_slider.set_value(1.0)
        self._crop_square_size_slider.register_handler(
            lambda _: self._on_widget_parameter_changed()
        )

        # 切り出し正方形 X 位置スライダー
        self._crop_square_x_slider = AISSlider(
            self,
            "X",
            [i / 100 for i in range(0, 101)],
            lambda lho, rho: abs(lho - rho),
            lambda x: f"{x * 100:5.1f}",
            "%",
        )
        self.ais.grid_child(self._crop_square_x_slider, 3, 0)
        self._crop_square_x_slider.set_value(0.5)
        self._crop_square_x_slider.register_handler(
            lambda _: self._on_widget_parameter_changed()
        )

        # 切り出し正方形 Y 位置スライダー
        self._crop_square_y_slider = AISSlider(
            self,
            "Y",
            [i / 100 for i in range(0, 101)],
            lambda lho, rho: abs(lho - rho),
            lambda x: f"{x * 100:5.1f}",
            "%",
        )
        self.ais.grid_child(self._crop_square_y_slider, 4, 0)
        self._crop_square_y_slider.set_value(0.5)
        self._crop_square_y_slider.register_handler(
            lambda _: self._on_widget_parameter_changed()
        )

        # モデル側切り出しパラメータ変更ハンドラ
        self._model.foreign.register_duration_change_handler(
            self._on_crop_square_param_changed
        )

        # セーブボタン
        self._save_button = ctk.CTkButton(
            self,
            text="SAVE",
            width=2 * WIDGET_MIN_WIDTH,
            command=self._on_save_button_clicked,
        )
        self.ais.grid_child(self._save_button, 1, 1, 4, 1)

        # ファイルドロップ関係
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop_file)

        # UI 初期設定
        # NOTE
        #   シンプルにハンドラを直接呼び出す
        self._on_widget_parameter_changed()

    def _on_widget_parameter_changed(self):
        """
        UI 上のパラメータが変更された時に呼び出されるハンドラ
        """
        # オーバーレイ有効・無効
        if self._export_target_radio.value in [
            ExportTarget.DISCORD_EMOJI,
            ExportTarget.DISCORD_STAMP,
        ]:
            overlay_nime_name = False
        else:
            overlay_nime_name = True

        # 適切な切り出しパラメータ
        if self._export_target_radio.value in [
            ExportTarget.DISCORD_EMOJI,
            ExportTarget.DISCORD_STAMP,
        ]:
            crop_params = (
                self._crop_square_size_slider.value,
                self._crop_square_x_slider.value,
                self._crop_square_y_slider.value,
            )
        else:
            crop_params = (None, None, None)

        # リサイズパラメータ
        if self._export_target_radio.value == ExportTarget.DISCORD_EMOJI:
            nime_resize_desc = ResizeDesc(
                AspectRatioPattern.E_1_1, ResolutionPattern.E_DISCORD_EMOJI
            )
        elif self._export_target_radio.value == ExportTarget.DISCORD_STAMP:
            nime_resize_desc = ResizeDesc(
                AspectRatioPattern.E_1_1, ResolutionPattern.E_DISCORD_STAMP
            )
        elif self._export_target_radio.value == ExportTarget.X_TWITTER:
            # NOTE
            #   X(Twitter) の上限は長辺 4096px
            nime_resize_desc = ResizeDesc(
                AspectRatioPattern.E_RAW,
                Resolution(4096, 4096, "X(Twitter) Limitation"),
            )
        else:
            raise ValueError("Invalid ExportTarget")

        # モデルに切り出し・リサイズを設定
        with VideoModelEditSession(self._model.foreign) as edit:
            edit.set_overlay_nime_name(overlay_nime_name)
            edit.set_crop_params(*crop_params)
            edit.set_size(ImageLayer.NIME, nime_resize_desc)

    def _on_crop_square_param_changed(self):
        """
        モデル側の切り出し正方形の変更ハンドラ
        """
        size_ratio, x_ratio, y_ratio = self._model.foreign.crop_params
        if size_ratio is not None and self._crop_square_size_slider.value != size_ratio:
            self._crop_square_size_slider.set_value(size_ratio)
        if x_ratio is not None and self._crop_square_x_slider.value != x_ratio:
            self._crop_square_x_slider.set_value(x_ratio)
        if y_ratio is not None and self._crop_square_y_slider.value != y_ratio:
            self._crop_square_y_slider.set_value(y_ratio)

    def _on_save_button_clicked(self):
        """
        エクスポートボタンクリックハンドラ
        """
        # スチル・ビデオを解決、ロードされてなければなにもしない
        model = self._model.foreign
        if model.num_total_frames < 1:
            return
        elif model.num_total_frames == 1:
            is_still = True
        else:
            is_still = False

        # エクスポートファイルの仕様を決定
        if self._export_target_radio.value == ExportTarget.DISCORD_EMOJI:
            subdir_name = "discord_emoji"
            if is_still:
                file_suffix = ".png"
            else:
                file_suffix = ".avif"
        elif self._export_target_radio.value == ExportTarget.DISCORD_STAMP:
            subdir_name = "discord_stamp"
            if is_still:
                file_suffix = ".png"
            else:
                file_suffix = ".gif"
        elif self._export_target_radio.value == ExportTarget.X_TWITTER:
            subdir_name = "x_twitter"
            if is_still:
                file_suffix = ".jpg"
            else:
                file_suffix = ".gif"
        else:
            raise ValueError(self._export_target_radio.value)

        # 出力ファイルパスを構築
        save_file_path = (
            TENSEI_DIR_PATH
            / subdir_name
            / f"{model.nime_name}__{model.time_stamp}{file_suffix}"
        )

        # エクスポート処理実行
        # NOTE
        #   エクスポートは NIME, RAW とは事情が異なるので、
        #   save_content_model を使わず、
        #   ここで直接ファイル出力を書く。
        save_file_path.parent.mkdir(parents=True, exist_ok=True)
        if is_still:
            # スチルを解決
            ais_image = model.get_frame(ImageLayer.NIME, 0)
            if ais_image is None:
                raise ValueError("Frame 0 is None")
            else:
                pil_image = ais_image.pil_image

            # PIL でファイル出力
            if file_suffix == ".png":
                pil_image.save(
                    str(save_file_path), format="PNG", optimize=True, compress_level=9
                )
            elif file_suffix == ".jpg":
                ais_image.pil_image.save(
                    str(save_file_path),
                    format="JPEG",
                    quality=92,
                    subsampling=0,
                    optimize=True,
                    progressive=True,
                )
            else:
                raise ValueError(f"Invalid still file_suffix ({file_suffix})")
        else:
            # 動画フレームを解決
            pil_frames = [
                f.pil_image for f in model.iter_frames(ImageLayer.NIME) if f is not None
            ]

            # gif なら 256 色カラーパレット化
            if file_suffix == ".gif":
                pil_frames = apply_color_palette(pil_frames)

            # 再生モードを反映
            match model.playback_mode:
                case PlaybackMode.FORWARD:
                    pass
                case PlaybackMode.BACKWARD:
                    pil_frames.reverse()
                case PlaybackMode.REFLECT:
                    if len(pil_frames) >= 3:
                        pil_frames = (
                            pil_frames + [f for f in reversed(pil_frames)][1:-1]
                        )
                case _:
                    raise ValueError(f"Invalid PlaybaclMode ({model.playback_mode})")

            # PIL でファイル出力
            if file_suffix == ".avif":
                pil_frames[0].save(
                    str(save_file_path),
                    save_all=True,
                    append_images=pil_frames[1:],
                    duration=model.duration_in_msec,
                    quality=60,
                    subsampling="4:2:0",
                    speed=2,
                    range="full",
                    codec="auto",
                )
            elif file_suffix == ".gif":
                duration_in_msec = max(1, 10 * round(model.duration_in_msec / 10))
                pil_frames[0].save(
                    str(save_file_path),
                    save_all=True,
                    append_images=pil_frames[1:],
                    duration=duration_in_msec,  # 10 msec 分解能にスナップ
                    loop=0,
                    disposal=0,
                    optimize=False,
                )
            elif file_suffix == ".apng":
                pil_frames[0].save(
                    str(save_file_path),
                    save_all=True,
                    append_images=pil_frames[1:],
                    duration=model.duration_in_msec,
                    loop=0,
                    disposal=0,
                    blend=0,
                    optimize=True,
                    compress_level=9,
                )
            else:
                raise ValueError(f"Invalid video file_suffix ({file_suffix})")

        # クリップボードに転送
        file_to_clipboard(save_file_path)

        # クリップボード転送完了通知
        show_notify_label(self, "info", "転生\nクリップボード転送完了")

    def _on_drop_file(self, event: DnDEvent):
        """
        ファイルドロップハンドラ

        Args:
            event (Event): イベント
        """
        # イベントからデータを取り出し
        event_data = vars(event)["data"]
        if not isinstance(event_data, str):
            return

        # 読み込み対象を解決
        file_paths = cast(tuple[str], self.tk.splitlist(event_data))
        if len(file_paths) > 1:
            show_error_dialog("ファイルは１つだけドロップしてね。")
            return
        else:
            file_path = file_paths[0]

        # モデルロード
        try:
            load_result = load_content_model(Path(file_path))
        except Exception as e:
            show_error_dialog("ファイルロードに失敗。", e)
            return

        # モデルに反映
        # NOTE
        #   スチル画像の場合はフレーム数１の動画としてロードする。
        #   スチル・ビデオで処理分けると実装がダルくなるので、それを避けるための措置。
        with VideoModelEditSession(self._model.foreign) as edit:
            if isinstance(load_result, ImageModel):
                (
                    edit.clear_frames()
                    .set_nime_name(load_result.nime_name)
                    .set_time_stamp(load_result.time_stamp)
                    .set_duration_in_msec(DFR_MAP.default_entry.duration_in_msec)
                    .append_frames(load_result)
                )
            elif isinstance(load_result, VideoModel):
                (
                    edit.clear_frames()
                    .set_nime_name(load_result.nime_name)
                    .set_time_stamp(load_result.time_stamp)
                    .set_duration_in_msec(load_result.duration_in_msec)
                    .append_frames(load_result)
                )
