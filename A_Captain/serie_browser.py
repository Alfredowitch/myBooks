import tkinter as tk
from D_Navigation.serie_view import SeriesView
from Bridge.serie_bridge import SeriesBridge


class SeriesBrowserApp:
    def __init__(self):
        self.root = tk.Tk()
        # Die Brücke ist das Bindeglied zur Atomic-Engine
        self.bridge = SeriesBridge()

        # Die View bekommt die Root und die Brücke
        self.view = SeriesView(self.root, self.bridge)
        self.bridge.view = self.view
        self.bridge.load_initial_data()
        self.root.mainloop()


if __name__ == "__main__":
    SeriesBrowserApp()