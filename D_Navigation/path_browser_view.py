# path_browser_view.py
import tkinter as tk
from tkinter import ttk
import os
import subprocess


class PathBrowserView:
    def __init__(self, parent, paths):
        self.top = tk.Toplevel(parent)
        self.top.title(f"Pfad-Checker: {len(paths)} Dateien gefunden")
        self.top.geometry("1000x500")

        lbl = tk.Label(self.top, text="Doppelklick öffnet den Ordner im Explorer", font=("Arial", 10, "italic"))
        lbl.pack(pady=5)

        # Treeview für die Pfade
        self.tree = ttk.Treeview(self.top, columns=("path",), show="headings")
        self.tree.heading("path", text="Vollständiger Dateipfad")
        self.tree.column("path", width=950, anchor="w")

        # Scrollbar
        scroll = ttk.Scrollbar(self.top, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Daten einfügen
        for p in paths:
            self.tree.insert("", "end", values=(p,))

        # Event-Binding
        self.tree.bind("<Double-1>", self._on_double_click)

    def _on_double_click(self, event):
        item = self.tree.selection()[0]
        path = self.tree.item(item, "values")[0]

        if os.path.exists(path):
            # Öffnet den Explorer und selektiert die Datei direkt (/select,)
            subprocess.run(['explorer', '/select,', os.path.normpath(path)])
        else:
            print(f"Pfad nicht gefunden: {path}")