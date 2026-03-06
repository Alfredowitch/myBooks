import tkinter as tk
from tkinter import ttk, messagebox


class AuthorSeriesEditor(tk.Toplevel):
    def __init__(self, parent, manager, series_id, author_id):
        super().__init__(parent)
        self.manager = manager
        self.series_id = int(series_id)
        self.author_id = int(author_id)

        # Fenster-Eigenschaften
        self.title(f"Serien-Editor (ID: {self.series_id})")
        self.geometry("700x500")
        self.grab_set()  # Modal machen

        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        # Hauptcontainer mit Padding
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header Info
        self.lbl_info = tk.Label(main_frame, text="Werke in dieser Serie sortieren", font=("Arial", 10, "bold"))
        self.lbl_info.pack(anchor="w", pady=(0, 10))

        # Tabelle für die Werke
        cols = ("ID", "Titel", "Nr")
        self.tree = ttk.Treeview(main_frame, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Titel", text="Titel des Werks")
        self.tree.heading("Nr", text="Serien-Nr")

        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("Titel", width=400, anchor="w")
        self.tree.column("Nr", width=80, anchor="center")

        self.tree.pack(fill=tk.BOTH, expand=True)

        # Editier-Bereich für die Nummer
        edit_frame = ttk.LabelFrame(main_frame, text="Gewähltes Werk bearbeiten", padding=5)
        edit_frame.pack(fill="x", pady=10)

        tk.Label(edit_frame, text="Serien-Nummer:").pack(side="left", padx=5)
        self.ent_nr = ttk.Entry(edit_frame, width=10)
        self.ent_nr.pack(side="left", padx=5)

        ttk.Button(edit_frame, text="Nummer lokal merken", command=self.update_local_item).pack(side="left", padx=5)

        # Button-Leiste unten
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", side="bottom", pady=(10, 0))
        btn_dissolve = ttk.Button(
            btn_frame,
            text="💥 Serie auflösen & Bereinigen",
            command=self.handle_dissolve_series
        )
        btn_dissolve.pack(side="right", padx=10)
        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="💾 Alle Änderungen speichern", command=self.save_all).pack(side="right", padx=5)

        # Event: Wenn Zeile gewählt, Nummer in Entry laden
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def load_data(self):
        """Lädt alle Werke der Serie mit formatierter Nummernanzeige."""
        works = self.manager.get_works_by_serie(self.series_id, self.author_id)
        for item in self.tree.get_children():
            self.tree.delete(item)

        for w in works:
            raw_nr = w['series_index']
            formatted_nr = ""

            if raw_nr is not None:
                try:
                    num = float(raw_nr)
                    # Prüfen, ob es eine ganze Zahl ist (z.B. 7.0 -> "007")
                    if num.is_integer():
                        formatted_nr = f"{int(num):03d}"
                    else:
                        # Bei Nachkommastellen (z.B. 7.5 -> "007.5")
                        # Wir füllen den Vorkommateil mit Nullen auf
                        parts = str(num).split('.')
                        vorkomma = int(parts[0])
                        nachkomma = parts[1]
                        formatted_nr = f"{vorkomma:03d}.{nachkomma}"
                except ValueError:
                    formatted_nr = str(raw_nr)

            self.tree.insert("", tk.END, iid=w['id'], values=(
                w['id'],
                w['title'],
                formatted_nr  # Die hübsch formatierte Nummer
            ))

    def on_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        val = self.tree.item(sel[0])['values'][2]
        self.ent_nr.delete(0, tk.END)
        self.ent_nr.insert(0, str(val))

    def update_local_item(self):
        """Aktualisiert den Wert nur in der Treeview-Liste (noch nicht DB)."""
        sel = self.tree.selection()
        if not sel: return
        new_nr = self.ent_nr.get().strip()

        # Update im Treeview
        item_id = sel[0]
        curr_vals = list(self.tree.item(item_id)['values'])
        curr_vals[2] = new_nr
        self.tree.item(item_id, values=curr_vals)

    def save_all(self):
        """Schreibt alle Nummern aus der Liste zurück in die Datenbank."""
        updates = []
        for item_id in self.tree.get_children():
            vals = self.tree.item(item_id)['values']
            work_id = vals[0]
            try:
                nr = float(vals[2]) if vals[2] != "" else None
            except ValueError:
                nr = None
            updates.append((work_id, nr))

        if self.manager.update_series_indices(updates):
            messagebox.showinfo("Erfolg", "Serien-Reihenfolge wurde aktualisiert.")
            self.destroy()
        else:
            messagebox.showerror("Fehler", "Speichern fehlgeschlagen.")

    def handle_dissolve_series(self):
        # Wir brauchen die ID und den Namen für die Abfrage
        s_id = self.series_id
        if not s_id:
            return

        # Sicherheitsabfrage mit klaren Details
        msg = (f"Möchtest du die Serie ID {s_id} wirklich auflösen?\n\n"
               "Das wird:\n"
               "1. Alle Bücher dieser Serie bereinigen (Name/Nummer auf leer/0)\n"
               "2. Alle Werke dieser Serie entkoppeln\n"
               "3. Den Serieneintrag permanent löschen.\n\n"
               "Dieser Vorgang kann nicht rückgängig gemacht werden!")

        if not messagebox.askyesno("⚠️ Serie permanent auflösen", msg):
            return

        # Aufruf der präzisen Manager-Funktion
        try:
            self.manager.dissolve_series(s_id)
            # Hauptfenster (AuthorBrowser) aktualisieren
            if hasattr(self.parent, 'refresh_series_list'):
                self.parent.refresh_series_list(self.author_id)
            messagebox.showinfo("Erfolg", f"Serie wurde vollständig aufgelöst.")
            self.destroy()  # Fenster schließen, da die Serie weg ist
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Auflösen: {str(e)}")