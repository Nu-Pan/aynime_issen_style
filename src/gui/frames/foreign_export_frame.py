# std
from typing import cast, Callable
from pathlib import Path


# Tk/CTk
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from tkinterdnd2.TkinterDnD import DnDEvent

# utils
from utils.image import (
    AspectRatio,
    AspectRatioPattern,
    PlaybackMode,
    Resolution,
    ResolutionPattern,
    ResizeDesc,
    ResizeMode,
)
from utils.image import ExportTarget
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
from utils.image import (
    apply_color_palette,
    ContentsMetadata,
    smart_pil_save,
    smart_pil_load,
    AISImage,
)

# gui
from gui.widgets.ais_frame import AISFrame
from gui.widgets.ais_slider import AISSlider
from gui.widgets.video_label import VideoLabel, VideoModelEditSession
from gui.model.aynime_issen_style import AynimeIssenStyleModel
from gui.model.contents_cache import (
    ImageLayer,
    ImageModel,
    ImageModelEditSession,
    VideoModel,
    VideoModelEditSession,
    load_content_model,
)


type NotifyHandler = Callable[[], None]


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
        _EXPORT_TARGETS = [
            ExportTarget.DISCORD_EMOJI,
            ExportTarget.DISCORD_STAMP,
            ExportTarget.X_TWITTER,
        ]
        self._radio_buttons: list[ctk.CTkRadioButton] = []
        for i, export_target in enumerate(_EXPORT_TARGETS):
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
            [i / 100 for i in range(5, 101)],
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
        # エイリアス
        export_target = self._export_target_radio.value

        # オーバーレイ有効・無効
        if export_target in [
            ExportTarget.DISCORD_EMOJI,
            ExportTarget.DISCORD_STAMP,
        ]:
            overlay_nime_name = False
        else:
            overlay_nime_name = True

        # 適切な切り出しパラメータ
        if export_target in [
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
        if export_target == ExportTarget.DISCORD_EMOJI:
            nime_resize_desc = ResizeDesc(
                AspectRatioPattern.E_1_1, ResolutionPattern.E_DISCORD_EMOJI
            )
        elif export_target == ExportTarget.DISCORD_STAMP:
            nime_resize_desc = ResizeDesc(
                AspectRatioPattern.E_1_1, ResolutionPattern.E_DISCORD_STAMP
            )
        elif export_target == ExportTarget.X_TWITTER:
            # NOTE
            #   X(Twitter) の上限は長辺 4096px
            nime_resize_desc = ResizeDesc(
                AspectRatioPattern.E_RAW, ResolutionPattern.E_X_TWITTER_STILL_LIMIT
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
        # エイリアス
        export_target = self._export_target_radio.value
        model = self._model.foreign

        # スチル・ビデオを解決、ロードされてなければなにもしない
        if model.num_total_frames < 1:
            return
        elif model.num_total_frames == 1:
            is_still = True
        else:
            is_still = False

        # エクスポートファイルの仕様を決定
        if export_target == ExportTarget.DISCORD_EMOJI:
            subdir_name = "discord_emoji"
            if is_still:
                file_suffix = ".png"
            else:
                file_suffix = ".avif"
        elif export_target == ExportTarget.DISCORD_STAMP:
            subdir_name = "discord_stamp"
            if is_still:
                file_suffix = ".png"
            else:
                file_suffix = ".gif"
        elif export_target == ExportTarget.X_TWITTER:
            subdir_name = "x_twitter"
            if is_still:
                file_suffix = ".jpg"
            else:
                file_suffix = ".gif"
        else:
            raise ValueError(export_target)

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

            # エンコード設定を解決
            if file_suffix == ".png":
                lossless = True
                quality_ratio = 1.0
                encode_speed_ratio = 0.0
            elif file_suffix == ".jpg":
                lossless = False
                quality_ratio = 92 / 95
                encode_speed_ratio = 0.0
            else:
                raise ValueError(f"Invalid still file_suffix ({file_suffix})")

            # メタデータを解決
            # NOTE
            #   スチルなので、ビデオ関係の情報は消去する
            metadata = self._model.foreign.contents_metadata
            metadata.set_playback_mode(None)
            metadata.erase_frame_enable()

            # PIL でファイル出力
            smart_pil_save(
                save_file_path,
                pil_image,
                duration_in_msec=None,
                metadata=metadata,
                lossless=lossless,
                quality_ratio=quality_ratio,
                encode_speed_ratio=encode_speed_ratio,
            )
        else:
            # 動画フレームを解決
            pil_frames = [
                f.pil_image
                for f in model.iter_frames(ImageLayer.NIME, enable_only=True)
                if f is not None
            ]

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

            # エンコード設定を解決
            if file_suffix in {".avif", ".gif"}:
                lossless = False
                quality_ratio = 0.6
                encode_speed_ratio = 0.2
            elif file_suffix == ".apng":
                lossless = True
                quality_ratio = 1.0
                encode_speed_ratio = 0.0
            else:
                raise ValueError(f"Invalid video file_suffix ({file_suffix})")

            # PIL でファイル出力
            smart_pil_save(
                save_file_path,
                pil_frames,
                duration_in_msec=model.duration_in_msec,
                metadata=model.contents_metadata,
                lossless=lossless,
                quality_ratio=quality_ratio,
                encode_speed_ratio=encode_speed_ratio,
            )

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
            new_model = load_content_model(Path(file_path))
        except Exception as e:
            show_error_dialog("ファイルロードに失敗。", e)
            return

        # NIME のアス比指定を RAW に適用する（ベイクする）
        # NOTE
        #   foreign の NIME のリサイズ機構はサイズ上限に収める（CONTAIN）に使いたい。
        #   ロードしたまんまだと、アス比をあわせるためのクロップ処理(COVER)になってるはず。
        #   転生タブで出力するのは NIME だけなので RAW に破壊的変更を加えても悪い副作用は起きない。
        #   よって、ちょっとお行儀が悪いけど、 RAW を編集してアスペクト比を適用(COVER)してしまう。
        new_nime_aspect_ratio = new_model.get_size(ImageLayer.NIME).aspect_ratio
        if new_nime_aspect_ratio != AspectRatio.from_pattern(AspectRatioPattern.E_RAW):
            if isinstance(new_model, ImageModel):
                # リサイズ済みの RAW 画像を生成
                new_raw_image = new_model.get_image(ImageLayer.RAW)
                if new_raw_image is not None:
                    new_raw_image = new_raw_image.resize_cover(
                        ResizeDesc(new_nime_aspect_ratio, ResolutionPattern.E_RAW)
                    )
                # モデルに反映
                with ImageModelEditSession(new_model) as edit:
                    edit.set_raw_image(new_raw_image)
            elif isinstance(new_model, VideoModel):
                # リサイズ済みの RAW フレーム列を生成
                new_raw_images: list[AISImage | None] = []
                for frame_index in range(new_model.num_total_frames):
                    new_raw_image = new_model.get_frame(ImageLayer.RAW, frame_index)
                    if new_raw_image is not None:
                        new_raw_image = new_raw_image.resize_cover(
                            ResizeDesc(new_nime_aspect_ratio, ResolutionPattern.E_RAW)
                        )
                    new_raw_images.append(new_raw_image)
                # モデルに反映
                with VideoModelEditSession(new_model) as edit:
                    for frame_index, new_raw_image in enumerate(new_raw_images):
                        edit.set_raw_image(
                            frame_index,
                            new_raw_image,
                            _does_notify=frame_index + 1 == len(new_raw_images),
                        )

        # 維持されるべきパラメータ
        preserved_overlay_nime_name = self._model.foreign.overlay_nime_name
        preserved_crop_params = self._model.foreign.crop_params
        preserved_size = self._model.foreign.get_size(ImageLayer.NIME)

        # モデルに反映
        with VideoModelEditSession(self._model.foreign) as edit:
            # 一度、全部設定
            edit.set_model(new_model)
            # 更新間隔を調整
            # NOTE
            #   スチル画像の場合はフレーム数１の動画になるので、
            #   一番低いフレームレートにしておく。
            if isinstance(new_model, ImageModel):
                edit.set_duration_in_msec(DFR_MAP.slowest_entry.duration_in_msec)
            # 一部パラメータを復元
            # NOTE
            #   転生タブの UI 由来で決まるパラメータは、関数呼び出し前から設定されていた値を維持する。
            edit.set_overlay_nime_name(preserved_overlay_nime_name)
            edit.set_crop_params(*preserved_crop_params)
            edit.set_size(ImageLayer.NIME, preserved_size)
            # リサイズ挙動は CONTAIN 固定
            # NOTE
            #   キャプチャタブでは NIME のリサイズ処理をアスペクト比適用（クロップ）のために使っていたが、
            #   転生タブではエクスポート先サービスのサイズ上限に収めるために使う。
            #   具体的には X(Twitter) の長辺 4096px 制限。
            #   なので、転生タブでは CONTAIN が正しい。
            edit.set_resize_mode(ImageLayer.NIME, ResizeMode.CONTAIN)
