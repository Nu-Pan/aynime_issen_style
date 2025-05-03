import customtkinter as ctk

from aynime_issen_style_app import AynimeIssenStyleApp


if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    app = AynimeIssenStyleApp()
    app.mainloop()
