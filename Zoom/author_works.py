import tkinter as tk
from tkinter import ttk, messagebox


class AuthorWorkEditor(tk.Toplevel):
    def __init__(self, parent, manager, work_id, author_id, series_number):
        super().__init__(parent)
        self.manager = manager
        self.work_id = int(work_id)
        self.author_id = int(author_id)
        # self.series_number = int(series_number)
        try:
            self.series_number = int(series_number) if series_number and str(series_number).strip() else 0
        except (ValueError, TypeError):
            self.series_number = 0

        self.title(f"Bücher zu Werk (ID: {self.work_id}) zuordnen")
        self.geometry("1250x950")
        self.grab_set()

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header_label = tk.Label(main_frame,
                                text="Wähle die physischen Bücher aus, die zu diesem Werk gehören:",
                                font=("Arial", 10, "bold"))
        header_label.pack(anchor="w", pady=(0, 10))

        # Treeview für Bücher
        cols = ("State", "ID", "Titel", "Pfad")
        self.tree = ttk.Treeview(main_frame, columns=cols, show="headings", selectmode="extended")

        self.tree.heading("State", text="Status")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Titel", text="Buchtitel")
        self.tree.heading("Pfad", text="Dateipfad")

        self.tree.column("State", width=30, anchor="center")
        self.tree.column("ID", width=40, anchor="center")
        self.tree.column("Titel", width=200)
        self.tree.column("Pfad", width=600)

        self.tree.pack(fill=tk.BOTH, expand=True)

        # Events
        self.tree.bind("<Double-1>", self.toggle_check)
        self.tree.bind("<space>", self.toggle_check)
        # Rechtsklick oder spezielle Taste für BookBrowser-Übergabe
        self.tree.bind("<Control-b>", lambda e: self.open_in_book_browser())

        # Info & Extra Buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill="x", pady=10)

        tk.Label(action_frame, text="Tipp: Leertaste zum Markieren | Strg+B zum Öffnen im Book-Browser",
                 font=("Arial", 8, "italic")).pack(side="left")

        btn_delete = ttk.Button(action_frame, text="🗑️ Buch-Eintrag löschen", command=self.delete_selected_books)
        btn_delete.pack(side="left", padx=5)
        ttk.Button(action_frame, text="🔍 Gewähltes Buch im Book-Browser prüfen",
                   command=self.open_in_book_browser).pack(side="right", padx=5)

        # Haupt-Buttons ganz unten
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", side="bottom", pady=(10, 0))

        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="💾 Zuordnung speichern", command=self.save_mapping).pack(side="right", padx=5)

    def load_data(self):
        """Holt potenzielle Bücher über den Manager."""
        books = self.manager.get_potential_books_for_work(self.work_id, self.author_id,
            self.series_number)

        for item in self.tree.get_children():
            self.tree.delete(item)

        for b in books:
            state = "[ X ]" if b['assigned'] else "[   ]"
            self.tree.insert("", tk.END, iid=b['id'], values=(
                state, b['id'], b['title'], b['path']
            ))

    def toggle_check(self, event):
        sel = self.tree.selection()
        if not sel: return
        item_id = sel[0]
        curr_vals = list(self.tree.item(item_id)['values'])
        curr_vals[0] = "[   ]" if curr_vals[0] == "[ X ]" else "[ X ]"
        self.tree.item(item_id, values=curr_vals)

    def open_in_book_browser(self):
        """Übergibt das aktuell gewählte Buch an den BookBrowser und kehrt danach zurück."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Achtung", "Bitte erst ein Buch auswählen.", parent=self)
            return

        book_id = int(sel[0])

        from Audio.book_browser import BookBrowser
        browser_win = tk.Toplevel(self)
        browser_win.title("Book-Browser Check")

        # Den Browser initialisieren
        browser = BookBrowser(browser_win)

        try:
            browser.load_from_list([book_id])

            # WICHTIG: Warte, bis das Browser-Fenster geschlossen wird
            self.wait_window(browser_win)

            # Sobald der Browser zu ist, holen wir uns den Fokus zurück
            self.focus_force()
            self.grab_set()  # Stellt sicher, dass der Editor wieder modal ist

            # Optional: Daten neu laden, falls im Browser etwas gelöscht/geändert wurde
            self.load_data()

        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Öffnen: {e}", parent=self)

    def save_mapping(self):
        selected_ids = []
        for item_id in self.tree.get_children():
            if self.tree.item(item_id)['values'][0] == "[ X ]":
                selected_ids.append(int(item_id))

        if self.manager.update_work_mapping(self.work_id, selected_ids):
            messagebox.showinfo("Erfolg", "Zuordnung gespeichert.")
            self.destroy()
        else:
            messagebox.showerror("Fehler", "Speichern fehlgeschlagen.")

    def delete_selected_books(self):
        items = self.tree.selection()
        if not items:
            return
        cols = list(self.tree["columns"])
        idx_id = cols.index("ID")
        idx_title = cols.index("Titel")  # Stelle sicher, dass die Spalte genau so heißt

        titles = []
        ids = []
        for item in items:
            vals = self.tree.item(item, "values")
            ids.append(vals[idx_id])
            titles.append(vals[idx_title])
        # Text für die Bestätigung zusammenbauen
        count = len(titles)
        if count == 1:
            msg = f"Möchtest du dieses Buch wirklich aus der Datenbank löschen?\n\n'{titles[0]}'"
        else:
            msg = f"Möchtest du diese {count} Bücher wirklich löschen?\n\n1. {titles[0]}\n... und {count - 1} weitere."
        # Sicherheitsabfrage mit Titeln
        if not messagebox.askyesno("Löschen bestätigen", msg):
            return
        # Löschvorgang über den Manager
        for b_id in ids:
            self.manager.delete_book_by_id(b_id)
        # UI aktualisieren
        self.load_data()