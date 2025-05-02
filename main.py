import customtkinter as ctk

from main_window import MainWindow


if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("dark-blue")
    app = MainWindow()
    app.mainloop()
