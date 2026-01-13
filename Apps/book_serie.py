import tkinter as tk
from tkinter import ttk


class SeriesLinkerWindow(tk.Toplevel):
    def __init__(self, parent, db_manager):
        super().__init__(parent)
        self.title("Serien-Zusammenführung & Analyse")
        self.geometry("1200x800")
        self.db = db_manager

        self._setup_ui()
        self.load_top_series()

    def _setup_ui(self):
        # Linke Seite: Top 30 Liste
        self.list_frame = tk.Frame(self, width=300)
        self.list_frame.pack(side="left", fill="y", padx=10, pady=10)

        tk.Label(self.list_frame, text="Top 30 Serien", font=("Arial", 12, "bold")).pack()
        self.series_listbox = tk.Listbox(self.list_frame, font=("Arial", 10))
        self.series_listbox.pack(fill="both", expand=True)
        self.series_listbox.bind("<Double-Button-1>", self.on_series_select)

        # Rechte Seite: Spalten-Ansicht
        self.grid_frame = tk.Frame(self)
        self.grid_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Hier generieren wir dynamisch Spalten pro Sprache
        self.columns = {}  # Sprache -> Frame

    def on_series_select(self, event):
        selection = self.series_listbox.get(self.series_listbox.curselection())
        series_name = selection.split(" (")[0]
        self.show_language_comparison(series_name)

    def show_language_comparison(self, series_name):
        """Erstellt die Spalten-Ansicht für die gewählte Serie."""
        # 1. Finde den Hauptautor der Serie
        author = self.db.get_main_author_for_series(series_name)

        # 2. Hole alle Bücher dieses Autors, die IRGENDEINE Serie haben
        all_series_of_author = self.db.get_all_series_by_author(author)

        # 3. Zeichne Spalten pro Sprache
        for lang in ['de', 'en', 'fr']:  # Erweitern nach Bedarf
            # Spalte für Sprache 'lang' füllen:
            # Zeige Seriennamen und die Nummern-Liste: "Band 1, 2, 4"
            pass



if __name__ == "__main__":
    root = tk.Tk()
    app = SeriesLinkerWindow(root)
    root.mainloop()