import tkinter as tk
from tkinter import ttk, messagebox
import os
import sqlite3
from Zoom.utils import DB_PATH
from Zoom.author_manager import AuthorManager
from Audio.book_browser import BookBrowser # <--- Importieren!


class AuthorBrowser:
    def __init__(self, root, selection_callback=None):
        self.root = root
        self.manager = AuthorManager()
        self.selection_callback = selection_callback  # Callback zum BookBrowser
        self.authors_data = []
        self.current_author_id = None

        # UI Setup
        self.setup_ui()
        self.load_top_30()

    # ----------------------------------------------------------------------
    # SETUP GUI
    # ----------------------------------------------------------------------
    def setup_ui(self):
        self.root.title("Autor-Master-Browser v1.4")
        self.root.geometry("1300x850")

        # --- Top Bar ---
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(side="top", fill="x")

        tk.Label(top_frame, text="Autor suchen:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.filter_list())
        ttk.Entry(top_frame, textvariable=self.search_var, width=30).pack(side="left", padx=5)

        ttk.Button(top_frame, text="Top 30", command=self.load_top_30).pack(side="left", padx=5)
        ttk.Button(top_frame, text="Bild-Refresh", command=self.update_image_display).pack(side="right", padx=5)

        # --- Main Layout (Dreiteilung) ---
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 1. Linke Spalte: Autorenliste
        cols = ("Name", "Total", "DE", "EN", "ES", "FR", "IT")
        self.tree = ttk.Treeview(paned, columns=cols, show="headings", selectmode="browse")
        for col in cols:
            self.tree.heading(col, text=col, command=lambda _c=col: self.sort_table(_c, False))
            self.tree.column(col, width=250 if col == "Name" else 45, anchor="w" if col == "Name" else "center")
        self.tree.bind("<<TreeviewSelect>>", self.load_selected_author)
        paned.add(self.tree, weight=2)

        # 2. Mittlere Spalte: Details & Bild
        self.edit_frame = ttk.Frame(paned, padding=10)
        paned.add(self.edit_frame, weight=1)

        self.img_label = tk.Label(self.edit_frame, text="Bild-Vorschau", bg="#eee", width=40, height=15, relief="ridge")
        self.img_label.pack(pady=5, fill="x")

        form_frame = ttk.Frame(self.edit_frame)
        form_frame.pack(fill="x")

        self.fields = {}
        for i, (lbl, key) in enumerate([("Anzeige-Name:", "display_name"), ("Haupt-Sprache:", "main_language"),
                                        ("Biblio-Link:", "info_link"), ("Slug (Bild):", "name_slug")]):
            row = ttk.Frame(form_frame)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=lbl, width=15, anchor="w").pack(side="left")
            ent = ttk.Entry(row)
            ent.pack(side="right", fill="x", expand=True)
            self.fields[key] = ent

        tk.Label(self.edit_frame, text="Vita:").pack(anchor="w", pady=(10, 0))
        self.txt_vita = tk.Text(self.edit_frame, height=10, width=40)
        self.txt_vita.pack(fill="both", expand=True)

        ttk.Button(self.edit_frame, text="💾 Autor speichern", command=self.save_current).pack(fill="x", pady=5)

        # 3. Rechte Spalte: Werke (Der Drilldown)
        work_frame = ttk.Frame(paned, padding=10)
        paned.add(work_frame, weight=2)

        tk.Label(work_frame, text="Werke des Autors:", font=("Arial", 10, "bold")).pack(anchor="w")

        work_cols = ("ID", "Titel", "Serie", "Nr", "Jahr")
        self.work_tree = ttk.Treeview(work_frame, columns=work_cols, show="headings")
        self.work_tree.column("ID", width=40)
        self.work_tree.column("Titel", width=250)
        self.work_tree.column("Serie", width=150)
        self.work_tree.column("Nr", width=40)
        self.work_tree.column("Jahr", width=60)

        for c in work_cols: self.work_tree.heading(c, text=c)
        self.work_tree.pack(fill="both", expand=True)

        # Button zum Übergeben an den Book-Browser
        ttk.Button(work_frame, text="📖 Im Book-Browser anzeigen", command=self.open_in_browser).pack(fill="x", pady=5)

    # ----------------------------------------------------------------------
    # LINKE SEITE: AUTOREN LISTE
    # ----------------------------------------------------------------------
    def load_top_30(self):
        self.authors_data = self.manager.get_top_30_authors()
        self.refresh_tree(self.authors_data)

    def filter_list(self):
        search = self.search_var.get().strip()
        if len(search) == 0:
            # Wenn leer, wieder die Top 30 zeigen
            self.load_top_30()
            return
        if len(search) < 3:
            # Zu kurz für eine globale Suche (optional)
            return
        # ECHTE Suche in der Datenbank über den Manager
        results = self.manager.search_authors(search)
        self.refresh_tree(results)

    def sort_table(self, col, reverse):
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            l.sort(key=lambda t: t[0].lower(), reverse=reverse)
        for index, (val, k) in enumerate(l):
            self.tree.move(k, "", index)
        self.tree.heading(col, command=lambda: self.sort_table(col, not reverse))

    # ----------------------------------------------------------------------
    # MITTE: AUTOREN
    # ----------------------------------------------------------------------
    def load_selected_author(self, event):
        selection = self.tree.selection()
        if not selection: return
        self.current_author_id = selection[0]

        # Nur noch Manager-Aufrufe
        author = self.manager.get_author(int(self.current_author_id))
        if author:
            self.set_field_value("display_name", author.display_name)
            self.set_field_value("main_language", author.main_language or "")
            self.set_field_value("info_link", author.info_link)
            self.set_field_value("name_slug", author.slug)
            self.txt_vita.delete("1.0", tk.END)
            self.txt_vita.insert("1.0", author.vita or "")

            self.update_image_display(author.slug)

            # Drilldown via Manager
            works = self.manager.get_works_by_author(author.id)
            for item in self.work_tree.get_children(): self.work_tree.delete(item)
            for w in works: self.work_tree.insert("", tk.END,
                                                  values=(w['id'], w['title'], w['series_name'], w['series_number']))

    def update_image_display(self, slug=None):
        """
        Aktualisiert das Autoren-Bild.
        Nutzt korrekt self.img_label und den richtigen Treeview-Namen.
        """
        # 1. Fallback: Wenn kein Slug übergeben, aus dem Treeview (self.tree) holen
        if not slug:
            selected = self.tree.selection()  # Korrektur: self.tree statt self.author_tree
            if not selected:
                return
            vals = self.tree.item(selected[0])['values']
            if len(vals) >= 1:
                # Wir holen den Slug aus dem Feld (Annahme: Slug steht in self.fields)
                slug = self.fields["name_slug"].get().strip()

                # Falls das Feld leer ist, slugify aus dem Namen
                if not slug:
                    from Gemini.file_utils import slugify
                    slug = slugify(vals[0])  # vals[0] ist der "Name"
        if not slug:
            return

        # 2. Pfad ermitteln
        img_path = self.manager.get_author_image_path(slug)

        # 3. Bild laden (PIL Logik) mit korrektem Attributnamen self.img_label
        if os.path.exists(img_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(img_path)
                img.thumbnail((250, 350))
                photo = ImageTk.PhotoImage(img)

                # Korrektur: self.img_label (wie in setup_ui definiert)
                self.img_label.config(image=photo, text="", width=0, height=0)
                self.img_label.image = photo
            except Exception as e:
                print(f"Fehler beim Bild-Rendering: {e}")
                self.img_label.config(image='', text="Bildfehler")
        else:
            # Falls kein Bild da ist, zeigen wir den Namen als Text
            self.img_label.config(image='', text=f"Kein Bild für\n'{slug}'", width=40, height=15)


    def save_current(self):
        if not self.current_author_id: return
        author = self.manager.get_author(int(self.current_author_id))

        full_name = self.fields["display_name"].get().strip()
        # Vorname/Nachname Splitting
        if " " in full_name:
            author.firstname, author.lastname = full_name.rsplit(" ", 1)
        else:
            author.firstname, author.lastname = "", full_name

        author.slug = self.fields["name_slug"].get()
        author.vita = self.txt_vita.get("1.0", tk.END).strip()
        author.info_link = self.fields["info_link"].get()

        # Das intelligente Speichern erledigt den Rest
        new_id = self.manager.smart_save(author)
        messagebox.showinfo("Erfolg", "Daten wurden verarbeitet.")
        self.load_top_30()

    # ----------------------------------------------------------------------
    # RECHTE SEITE: WERKE ZU AUTOREN
    # ----------------------------------------------------------------------
    def load_works_for_author(self, author_id):
        """Holt die Werke über den Manager und füllt den Tree."""
        # 1. Tree leeren
        for item in self.work_tree.get_children():
            self.work_tree.delete(item)
        if not author_id:
            return

        # 2. Daten vom Manager holen (der jetzt die Work-ID 77499 liefert)
        works = self.manager.get_works_by_author(author_id)
        # 3. Tree befüllen
        for w in works:
            self.work_tree.insert("", tk.END, values=(
                w['id'],  # Die Work-ID (z.B. 77499)
                w['title'],
                w['series_name'] or "-",
                w['series_number'] or "",
                w.get('year', '')  # Das Jahr
            ))

    # ----------------------------------------------------------------------
    # HILFSFUNKTIONEN
    # ----------------------------------------------------------------------
    def set_field_value(self, field_name, value):
        self.fields[field_name].delete(0, tk.END)
        self.fields[field_name].insert(0, str(value) if value else "")

    def refresh_tree(self, data):
        """Aktualisiert die linke Autorenliste und stellt sicher, dass IDs und Werte matchen."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in data:
            # Falls r noch ein sqlite3.Row ist, machen wir es hier sicherheitshalber zum Dict
            if not isinstance(r, dict):
                r = dict(r)
            # Wir setzen die iid auf die ID, damit self.tree.selection() die ID liefert
            # In den values zeigen wir die Spalten an, die in setup_ui definiert wurden
            self.tree.insert("", tk.END, iid=r['id'], values=(
                r.get('display_name', 'Unbekannt'),
                r.get('total', 0),
                r.get('de', 0),
                r.get('en', 0),
                r.get('es', 0),
                r.get('fr', 0),
                r.get('it', 0)
            ))

    def open_in_browser(self):
        """Holt die ID aus dem Werk-Baum und übergibt sie an den BookBrowser."""
        sel = self.work_tree.selection()
        if not sel:
            return

        # ID des Werks aus dem Treeview holen
        item_data = self.work_tree.item(sel[0])
        work_id = item_data['values'][0]

        # Die zugehörige Buch-ID in der DB finden
        with sqlite3.connect(DB_PATH) as conn:
            # Wir brauchen die ID aus der Tabelle 'books'
            res = conn.execute("SELECT id FROM books WHERE work_id = ?", (work_id,)).fetchone()

            if res and self.selection_callback:
                book_id = res[0]
                # Hier rufen wir jetzt die saubere Schnittstelle 'load_from_apps' auf
                #self.selection_callback(book_id)
                new_win = tk.Toplevel(self.root)
                BookBrowser(new_win, initial_list=[{'ID': book_id}])
            elif not res:
                messagebox.showinfo("Info", "Kein Buch zu diesem Werk in der Datenbank gefunden.")

if __name__ == "__main__":
    root = tk.Tk()
    # Dummy Callback für Test
    app = AuthorBrowser(root, selection_callback=lambda x: print(f"BookID gewählt: {x}"))
    root.mainloop()