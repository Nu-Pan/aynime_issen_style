import customtkinter as ctk
import win32gui
from CTkListbox import CTkListbox

from window_selection_frame import WindowSelectionFrame


# メインアプリ
class MainWindow(ctk.CTk):


    def __init__(self):
        super().__init__()
        self.title("えぃにめ一心流奥義　――スクショ――")
        self.geometry("1280x720")

        # フレーム作成・配置
        self.current_frame = WindowSelectionFrame(self)
        self.current_frame.pack(fill="both", expand=True)
