import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from Zoom.utils import DB_PATH


class BookAnalyser:
    def __init__(self, master):
        self.master = master
        self.db_path = DB_PATH
        self.master.title("Library Analyzer v1.4.9 - Atom Struktur & Browser Link")
        self.master.geometry("1400x950")

        self.langs = {
            "de": tk.BooleanVar(value=True),
            "en": tk.BooleanVar(value=True),
            "fr": tk.BooleanVar(value=True),
            "es": tk.BooleanVar(value=True),
            "it": tk.BooleanVar(value=True)
        }

        self.browser_instance = None  # Speicher für das Browser-Fenster
        self.setup_ui()
        self.show_dashboard()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_selected_langs(self):
        return [l for l, v in self.langs.items() if v.get()]

    def update_pandas_info(self, code_text):
        self.pandas_text.delete("1.0", tk.END)
        self.pandas_text.insert("1.0", f"# Pandas Logik für diese Ansicht:\n{code_text}")

    def setup_ui(self):
        # --- Linke Navigation (Linksbündig) ---
        nav_frame = ttk.Frame(self.master, width=220, padding=10)
        nav_frame.pack(side="left", fill="y")

        tk.Label(nav_frame, text="NAVIGATION", font=("Arial", 11, "bold"), anchor="w").pack(fill="x", pady=(0, 10))

        buttons = [
            ("🏠 Übersicht", self.show_dashboard),
            ("📚 Bücher", lambda: self.load_view("books")),
            ("📂 Werke", lambda: self.load_view("works")),
            ("🎞️ Serien", self.load_top_series),
            ("👤 Autoren", self.load_top_authors),
            ("⚠️ Serien o. Werke", lambda: self.load_missing("series_no_works")),
            ("⚠️ Bücher o. Serien", lambda: self.load_missing("books_no_series")),
            ("⚠️ Autoren o. Serien", lambda: self.load_missing("authors_no_series")),
            ("⚠️ Bücher o. Werke", lambda: self.load_missing("books_no_works")),
            ("⚠️ Autoren o. Bücher", lambda: self.load_missing("authors_no_books")),
        ]

        # Style definieren
        style = ttk.Style()
        style.configure("Nav.TButton", anchor="w")  # "w" steht für West = Links
        # Buttons mit diesem Style erstellen
        for text, cmd in buttons:
            btn = ttk.Button(nav_frame, text=text, command=cmd, style="Nav.TButton")
            btn.pack(fill="x", pady=2)

        # --- Sprachfilter ---
        tk.Label(nav_frame, text="\nSPRACHFILTER", font=("Arial", 10, "bold"), anchor="w").pack(fill="x", pady=5)
        for lang, var in self.langs.items():
            ttk.Checkbutton(nav_frame, text=lang.upper(), variable=var).pack(anchor="w")

        ttk.Button(nav_frame, text="Filter anwenden", command=self.show_dashboard).pack(fill="x", pady=10)

        # --- Rechter Bereich ---
        self.main_frame = ttk.Frame(self.master, padding=10)
        self.main_frame.pack(side="right", fill="both", expand=True)

        toolbar = ttk.Frame(self.main_frame)
        toolbar.pack(fill="x", pady=5)
        ttk.Button(toolbar, text="📖 Im Book-Browser öffnen", command=self.open_in_browser).pack(side="left")

        # Treeview Bereich
        self.tree_container = ttk.Frame(self.main_frame)
        self.tree_container.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(self.tree_container, show="headings")
        self.tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(self.tree_container, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        # --- Pandas Learning Console ---
        tk.Label(self.main_frame, text="Pandas Learning Console:", font=("Consolas", 11, "bold")).pack(anchor="w",
                                                                                                       pady=(15, 0))
        self.pandas_text = tk.Text(self.main_frame, height=8, bg="#1e1e1e", fg="#dcdcdc", font=("Consolas", 12),
                                   padx=10, pady=10)
        self.pandas_text.pack(fill="x", pady=5)

    def show_dashboard(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.tree["columns"] = ("Kategorie", "Gesamt", "DE", "EN", "FR", "ES", "IT")
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center")
        self.tree.column("Kategorie", width=250, anchor="w")

        with self._get_conn() as conn:
            categories = [("Bücher", "books", "id"), ("Werke", "works", "id"),
                          ("Serien", "books", "series_name"), ("Autoren", "authors", "id")]
            for label, table, col in categories:
                where = "WHERE series_name IS NOT NULL AND series_name != ''" if label == "Serien" else ""
                total = conn.execute(f"SELECT COUNT(DISTINCT {col}) FROM {table} {where}").fetchone()[0]
                row = [label, total]
                for l in ["de", "en", "fr", "es", "it"]:
                    if table == "books":
                        sql = f"SELECT COUNT(DISTINCT {col}) FROM books WHERE LOWER(language)=? {where.replace('WHERE', 'AND')}"
                        row.append(conn.execute(sql, (l,)).fetchone()[0])
                    else:
                        row.append("-")
                self.tree.insert("", "end", values=row)

            self.tree.insert("", "end", values=("--- Fehler / Fehlende Verknüpfungen ---", "", "", "", "", "", ""))
            error_stats = [
                ("Bücher ohne Werk", "SELECT COUNT(*) FROM books WHERE id NOT IN (SELECT book_id FROM work_to_book)"),
                ("Serien ohne Werk",
                 "SELECT COUNT(DISTINCT series_name) FROM books WHERE series_name IS NOT NULL AND id NOT IN (SELECT book_id FROM work_to_book)"),
                ("Bücher ohne Serie", "SELECT COUNT(*) FROM books WHERE series_name IS NULL OR series_name = ''"),
                ("Autoren ohne Bücher",
                 "SELECT COUNT(*) FROM authors WHERE id NOT IN (SELECT author_id FROM work_to_author)")
            ]
            for label, sql in error_stats:
                val = conn.execute(sql).fetchone()[0]
                self.tree.insert("", "end", values=(label, val, "", "", "", "", ""))

        self.update_pandas_info("df.isnull().sum() # Zeigt fehlende Werte")

    def load_top_series(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.tree["columns"] = ("Serienname", "Bücher", "Haupt-Autor")
        for col in self.tree["columns"]: self.tree.heading(col, text=col)
        self.tree.column("Serienname", width=500)
        self.tree.column("Bücher", width=80, anchor="center")

        langs = self.get_selected_langs()
        query = f"""
            SELECT series_name, COUNT(*) as cnt
            FROM books 
            WHERE series_name IS NOT NULL AND series_name != ''
            AND LOWER(language) IN ({','.join(['?'] * len(langs))})
            GROUP BY series_name ORDER BY cnt DESC LIMIT 100
        """
        with self._get_conn() as conn:
            rows = conn.execute(query, langs).fetchall()
            for r in rows:
                self.tree.insert("", "end", values=(r[0], r[1], "Doppelklick für Info"))

        self.update_pandas_info("df.groupby('series_name').size().nlargest(100)")

    def load_view(self, table):
        for i in self.tree.get_children(): self.tree.delete(i)
        if table == "books":
            self.tree["columns"] = ("ID", "Titel", "Sprache", "Format")
            for col in self.tree["columns"]: self.tree.heading(col, text=col)
            self.tree.column("ID", width=60, anchor="center")
            query = "SELECT id, title, language, ext FROM books LIMIT 1000"
        elif table == "works":
            self.tree["columns"] = ("ID", "Werk-Titel", "DE", "EN", "FR", "ES", "IT")
            for col in self.tree["columns"]: self.tree.heading(col, text=col)
            self.tree.column("ID", width=60, anchor="center")
            query = """
                SELECT w.id, w.title,
                COUNT(CASE WHEN LOWER(b.language)='de' THEN 1 END),
                COUNT(CASE WHEN LOWER(b.language)='en' THEN 1 END),
                COUNT(CASE WHEN LOWER(b.language)='fr' THEN 1 END),
                COUNT(CASE WHEN LOWER(b.language)='es' THEN 1 END),
                COUNT(CASE WHEN LOWER(b.language)='it' THEN 1 END)
                FROM works w LEFT JOIN work_to_book wtb ON w.id = wtb.work_id
                LEFT JOIN books b ON wtb.book_id = b.id GROUP BY w.id LIMIT 500
            """
        with self._get_conn() as conn:
            rows = conn.execute(query).fetchall()
            for r in rows: self.tree.insert("", "end", values=list(r))

    def load_top_authors(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.tree["columns"] = ("ID", "Autor", "Serien", "Werke")
        for col in self.tree["columns"]: self.tree.heading(col, text=col)
        self.tree.column("ID", width=60, anchor="center")

        langs = self.get_selected_langs()
        query = f"""
            SELECT a.id, (COALESCE(a.firstname, '') || ' ' || COALESCE(a.lastname, '')) as name,
                   COUNT(DISTINCT b.series_name), COUNT(DISTINCT wta.work_id)
            FROM authors a JOIN work_to_author wta ON a.id = wta.author_id
            JOIN work_to_book wtb ON wta.work_id = wtb.work_id JOIN books b ON wtb.book_id = b.id
            WHERE LOWER(b.language) IN ({','.join(['?'] * len(langs))})
            GROUP BY a.id ORDER BY 4 DESC LIMIT 100
        """
        with self._get_conn() as conn:
            rows = conn.execute(query, langs).fetchall()
            for r in rows: self.tree.insert("", "end", values=list(r))

    def load_missing(self, mode):
        for i in self.tree.get_children(): self.tree.delete(i)
        queries = {
            "series_no_works": ("Serienname",
                                "SELECT DISTINCT series_name FROM books WHERE series_name IS NOT NULL AND id NOT IN (SELECT book_id FROM work_to_book)"),
            "books_no_series": ("ID", "Titel", "Path",
                                "SELECT id, title, path FROM books WHERE (series_name IS NULL OR series_name = '')"),
            "authors_no_series": ("ID", "Autor",
                                  "SELECT id, (firstname || ' ' || lastname) FROM authors WHERE id NOT IN (SELECT author_id FROM work_to_author wta JOIN work_to_book wtb ON wta.work_id=wtb.work_id JOIN books b ON wtb.book_id=b.id WHERE b.series_name IS NOT NULL)"),
            "books_no_works": ("ID", "Titel", "Path",
                               "SELECT id, title, path FROM books WHERE id NOT IN (SELECT book_id FROM work_to_book)"),
            "authors_no_books": ("ID", "Autor",
                                 "SELECT id, (firstname || ' ' || lastname) FROM authors WHERE id NOT IN (SELECT author_id FROM work_to_author)")
        }
        conf = queries.get(mode)
        col_names, query = conf[:-1], conf[-1]
        self.tree["columns"] = col_names
        for col in col_names: self.tree.heading(col, text=col)
        if "ID" in col_names: self.tree.column("ID", width=60, anchor="center")
        if "Path" in col_names: self.tree.column("Path", width=800)
        with self._get_conn() as conn:
            rows = conn.execute(query).fetchall()
            for r in rows: self.tree.insert("", "end", values=list(r))

    def open_in_browser(self):
        """Sammelt IDs aus der Auswahl und übergibt sie als getypte Liste an den BookBrowser."""
        items = self.tree.selection()
        if not items:
            items = self.tree.get_children()  # Fallback: Alle nehmen

        if not items: return

        cols = list(self.tree["columns"])
        id_list = []

        with self._get_conn() as conn:
            for i in items:
                vals = self.tree.item(i)['values']

                # FALL 1: Wir haben direkt eine ID (Bücher, Werke, Autoren)
                if "ID" in cols:
                    idx = cols.index("ID")
                    obj_id = vals[idx]

                    if "Autor" in cols:  # Es ist ein Autor -> Alle seine Bücher holen
                        res = conn.execute(
                            "SELECT b.id FROM books b JOIN work_to_book wtb ON b.id=wtb.book_id JOIN work_to_author wta ON wtb.work_id=wta.work_id WHERE wta.author_id=?",
                            (obj_id,)).fetchall()
                        id_list.extend([r[0] for r in res])
                    elif "Werk-Titel" in cols:  # Es ist ein Werk -> Alle Bücher des Werks holen
                        res = conn.execute("SELECT book_id FROM work_to_book WHERE work_id=?", (obj_id,)).fetchall()
                        id_list.extend([r[0] for r in res])
                    else:  # Es ist direkt ein Buch
                        id_list.append(obj_id)

                # FALL 2: Wir haben einen Seriennamen (Serien-Ansicht)
                elif "Serienname" in cols:
                    idx = cols.index("Serienname")
                    s_name = vals[idx]
                    res = conn.execute("SELECT id FROM books WHERE series_name=?", (s_name,)).fetchall()
                    id_list.extend([r[0] for r in res])

            # Dubletten entfernen (Liste von reinen IDs)
            unique_ids = list(dict.fromkeys(id_list))

            if unique_ids:
                from Audio.book_browser import BookBrowser

                # Prüfen, ob Browser offen ist
                if self.browser_instance is not None and tk.Toplevel.winfo_exists(self.browser_instance.win):
                    # Nutzt jetzt den neuen Namen 'load_from_report'
                    # Wir übergeben nur die reine ID-Liste, B macht den Rest
                    self.browser_instance.load_from_report(unique_ids)
                else:
                    top = tk.Toplevel(self.master)
                    # Für den initialen Start erstellen wir die getypte Liste einmalig hier
                    initial_nav = [('ID', int(bid)) for bid in unique_ids]
                    self.browser_instance = BookBrowser(top, initial_list=initial_nav)
            else:
                messagebox.showinfo("Info", "Keine Bücher zum Öffnen gefunden.")

if __name__ == "__main__":
    root = tk.Tk()
    app = BookAnalyser(root)
    root.mainloop()