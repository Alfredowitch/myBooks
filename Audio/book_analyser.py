import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from Zoom.utils import DB_PATH


class BookAnalyser:
    def __init__(self, master):
        self.master = master
        self.db_path = DB_PATH
        self.master.title("Library Analyzer v1.5.0 - Serien-Fokus")
        self.master.geometry("1400x950")

        self.langs = {
            "de": tk.BooleanVar(value=True),
            "en": tk.BooleanVar(value=True),
            "fr": tk.BooleanVar(value=True),
            "es": tk.BooleanVar(value=True),
            "it": tk.BooleanVar(value=True)
        }

        self.browser_instance = None
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
        self.pandas_text.insert("1.0", f"# Pandas Logik:\n{code_text}")

    def _sort_treeview(self, column_id, reverse):
        data = [(self.tree.set(child, column_id), child) for child in self.tree.get_children("")]

        def sort_key(x):
            cell_value = x[0]  # Umbenannt von 'val' zu 'cell_value'
            if cell_value == "-" or cell_value == "":
                return -1.0 if not reverse else 1.0
            try:
                return float(cell_value)
            except ValueError:
                return cell_value.lower()

        data.sort(key=sort_key, reverse=reverse)
        for index, (val, child) in enumerate(data):
            self.tree.move(child, "", index)
        self.tree.heading(column_id, command=lambda: self._sort_treeview(column_id, not reverse))

    def setup_ui(self):
        nav_frame = ttk.Frame(self.master, width=220, padding=10)
        nav_frame.pack(side="left", fill="y")

        tk.Label(nav_frame, text="NAVIGATION", font=("Arial", 11, "bold"), anchor="w").pack(fill="x", pady=(0, 10))

        # Korrigiertes Alignment: "🎞️ Serien" zu "🎬 Serien" gewechselt für besseres Spacing
        buttons = [
            ("🏠 Übersicht", self.show_dashboard),
            ("📚 Bücher", lambda: self.load_view("books")),
            ("📂 Werke", lambda: self.load_view("works")),
            ("🎬 Serien", self.load_top_series),
            ("👤 Autoren", self.load_top_authors),
            ("⚠️ Titel-Doubletten", lambda: self.load_missing("title_duplicates")),
            ("⚠️ Serien o. Werke", lambda: self.load_missing("series_no_works")),
            ("⚠️ Bücher o. Serien", lambda: self.load_missing("books_no_series")),
            ("⚠️ Autoren o. Serien", lambda: self.load_missing("authors_no_series")),
            ("⚠️ Autoren o. Werke", lambda: self.load_missing("authors_no_works")),
            ("⚠️ Autoren o. Bücher", lambda: self.load_missing("authors_no_books")),
            ("⚠️ Werke o. Autoren", lambda: self.load_missing("works_no_authors")),
            ("⚠️ Bücher o. Autoren", lambda: self.load_missing("books_no_authors")),
            ("⚠️ Bücher o. Werke", lambda: self.load_missing("books_no_works")),
        ]

        style = ttk.Style()
        style.configure("Nav.TButton", anchor="w")
        for text, cmd in buttons:
            btn = ttk.Button(nav_frame, text=text, command=cmd, style="Nav.TButton")
            btn.pack(fill="x", pady=2)

        tk.Label(nav_frame, text="\nSPRACHFILTER", font=("Arial", 10, "bold"), anchor="w").pack(fill="x", pady=5)
        for lang, var in self.langs.items():
            ttk.Checkbutton(nav_frame, text=lang.upper(), variable=var).pack(anchor="w")

        ttk.Button(nav_frame, text="Filter anwenden", command=self.show_dashboard).pack(fill="x", pady=10)

        self.main_frame = ttk.Frame(self.master, padding=10)
        self.main_frame.pack(side="right", fill="both", expand=True)

        toolbar = ttk.Frame(self.main_frame)
        toolbar.pack(fill="x", pady=5)
        ttk.Button(toolbar, text="📖 Im Book-Browser öffnen", command=self.open_in_browser).pack(side="left")

        self.tree_container = ttk.Frame(self.main_frame)
        self.tree_container.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(self.tree_container, show="headings")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        sb = ttk.Scrollbar(self.tree_container, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        tk.Label(self.main_frame, text="Pandas Learning Console:", font=("Consolas", 11, "bold")).pack(anchor="w",
                                                                                                       pady=(15, 0))
        self.pandas_text = tk.Text(self.main_frame, height=8, bg="#1e1e1e", fg="#dcdcdc", font=("Consolas", 12),
                                   padx=10, pady=10)
        self.pandas_text.pack(fill="x", pady=5)

    def show_dashboard(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        cols = ("Kategorie", "Gesamt", "DE", "EN", "FR", "ES", "IT")
        self.tree["columns"] = cols
        for col in cols:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_treeview(c, False))
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

    def load_top_series(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        cols = ("Serienname", "Werke", "Gesamt", "DE", "EN", "FR", "ES", "IT")
        self.tree["columns"] = cols

        self.tree.column("Serienname", width=350, anchor="w")
        self.tree.column("Werke", width=80, anchor="center")
        for col in cols[2:]:
            self.tree.column(col, width=60, anchor="center")

        for col in cols:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_treeview(c, False))

        langs = self.get_selected_langs()
        lang_filter = f"AND LOWER(language) IN ({','.join(['?'] * len(langs))})"

        query = f"""
            SELECT series_name, 
                   COUNT(DISTINCT work_id) as w_cnt,
                   COUNT(id) as b_total,
                   COUNT(CASE WHEN LOWER(language)='de' THEN 1 END) as de,
                   COUNT(CASE WHEN LOWER(language)='en' THEN 1 END) as en,
                   COUNT(CASE WHEN LOWER(language)='fr' THEN 1 END) as fr,
                   COUNT(CASE WHEN LOWER(language)='es' THEN 1 END) as es,
                   COUNT(CASE WHEN LOWER(language)='it' THEN 1 END) as it
            FROM books 
            WHERE series_name IS NOT NULL AND series_name != ''
            {lang_filter}
            GROUP BY series_name 
            ORDER BY w_cnt DESC LIMIT 200
        """
        with self._get_conn() as conn:
            rows = conn.execute(query, langs).fetchall()
            for r in rows:
                self.tree.insert("", "end", values=list(r))

        self.update_pandas_info("df.groupby('series_name').agg({'work_id': 'nunique', 'id': 'count'})")

    def on_tree_double_click(self, event=None):
        item = self.tree.selection()
        if not item: return

        # Sicherstellen, dass wir Werte haben
        item_data = self.tree.item(item[0])
        vals = item_data.get('values', [])
        cols = list(self.tree["columns"])

        if not vals: return

        # Nur reagieren, wenn wir in der Serien-Ansicht sind
        if "Serienname" in cols:
            series_name = vals[cols.index("Serienname")]
            # Falls auf die leere Zeile oder Header geklickt wurde
            if series_name and series_name != "None":
                self.open_series_detail(series_name)

    def open_series_detail(self, series_name):
        top = tk.Toplevel(self.master)
        top.title(f"Serien-Details: {series_name}")
        top.geometry("1100x700")

        # Definition der Spalten - "Nr" zeigt jetzt den series_index
        cols = ("Nr", "Werk-Titel", "DE", "EN", "FR", "ES", "IT")

        # HIER FEHLTE DIE ZUWEISUNG: Wir erstellen das tree-Widget
        tree = ttk.Treeview(top, columns=cols, show="headings")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for col in cols:
            tree.heading(col, text=col)
            # Layout: Schmale Spalten für Index/Sprachen, breit für Titel
            w = 50 if col == "Nr" else 500 if "Titel" in col else 70
            tree.column(col, width=w, anchor="center" if col != "Werk-Titel" else "w")

        # SQL-Abfrage mit series_index und korrekter Sortierung
        query = """
            SELECT series_index, 
                   (SELECT title FROM works WHERE id = b.work_id) as work_title,
                   COUNT(CASE WHEN LOWER(language)='de' THEN 1 END),
                   COUNT(CASE WHEN LOWER(language)='en' THEN 1 END),
                   COUNT(CASE WHEN LOWER(language)='fr' THEN 1 END),
                   COUNT(CASE WHEN LOWER(language)='es' THEN 1 END),
                   COUNT(CASE WHEN LOWER(language)='it' THEN 1 END)
            FROM books b
            WHERE series_name = ?
            GROUP BY series_index, work_id
            ORDER BY series_index ASC
        """

        with self._get_conn() as conn:
            rows = conn.execute(query, (series_name,)).fetchall()
            for r in rows:
                vals = list(r)
                # Schönere Darstellung: 1.0 -> 1, 1.5 -> 1.5
                if vals[0] is not None:
                    idx = vals[0]
                    vals[0] = int(idx) if idx == int(idx) else idx
                else:
                    vals[0] = "-"

                # Jetzt ist 'tree' bekannt und der Insert funktioniert
                tree.insert("", "end", values=vals)

    def load_view(self, table):
        for i in self.tree.get_children(): self.tree.delete(i)
        query = None  # Sicherheits-Initialisierung
        if table == "books":
            cols = ("ID", "Titel", "Sprache", "Format")
            self.tree["columns"] = cols
            for col in cols: self.tree.heading(col, text=col, command=lambda c=col: self._sort_treeview(c, False))
            query = "SELECT id, title, language, ext FROM books LIMIT 1000"
        elif table == "works":
            cols = ("ID", "Werk-Titel", "Autoren", "DE", "EN", "FR", "ES", "IT")
            self.tree["columns"] = cols
            for col in cols: self.tree.heading(col, text=col, command=lambda c=col: self._sort_treeview(c, False))
            query = """
                            SELECT w.id, w.title, COUNT(DISTINCT wta.author_id), 
                                   COUNT(CASE WHEN LOWER(b.language)='de' THEN 1 END), 
                                   COUNT(CASE WHEN LOWER(b.language)='en' THEN 1 END), 
                                   COUNT(CASE WHEN LOWER(b.language)='fr' THEN 1 END), 
                                   COUNT(CASE WHEN LOWER(b.language)='es' THEN 1 END), 
                                   COUNT(CASE WHEN LOWER(b.language)='it' THEN 1 END) 
                            FROM works w 
                            LEFT JOIN books b ON w.id = b.work_id 
                            LEFT JOIN work_to_author wta ON w.id = wta.work_id 
                            GROUP BY w.id LIMIT 500
                        """
        # 2. Nur ausführen, wenn query wirklich gesetzt wurde
        if query:
            with self._get_conn() as conn:
                rows = conn.execute(query).fetchall()
                for r in rows:
                    self.tree.insert("", "end", values=list(r))
        else:
            print(f"⚠️ Warnung: Keine Query für Tabelle '{table}' definiert.")

    def load_top_authors(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        # "Spr." als neue Spalte hinzugefügt
        cols = ("ID", "Autor", "Spr.", "Serien", "Werke")
        self.tree["columns"] = cols
        for col in cols:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_treeview(c, False))

        self.tree.column("ID", width=60, anchor="center")
        self.tree.column("Spr.", width=60, anchor="center")
        self.tree.column("Autor", width=300, anchor="w")

        langs = self.get_selected_langs()
        # Abfrage um a.language erweitert
        query = f"""
            SELECT a.id, 
                   (COALESCE(a.firstname, '') || ' ' || COALESCE(a.lastname, '')) as name,
                   UPPER(a.language),
                   COUNT(DISTINCT b.series_name), 
                   COUNT(DISTINCT wta.work_id)
            FROM authors a 
            JOIN work_to_author wta ON a.id = wta.author_id
            JOIN books b ON wta.work_id = b.work_id
            WHERE LOWER(b.language) IN ({','.join(['?'] * len(langs))})
            GROUP BY a.id 
            ORDER BY 5 DESC LIMIT 100
        """
        with self._get_conn() as conn:
            rows = conn.execute(query, langs).fetchall()
            for r in rows:
                self.tree.insert("", "end", values=list(r))

        self.update_pandas_info("df_authors.sort_values('works_count', ascending=False)")

    def load_missing(self, mode):
        for i in self.tree.get_children(): self.tree.delete(i)
        queries = {
            "series_no_works": ("Serienname",
                                "SELECT DISTINCT series_name FROM books WHERE series_name IS NOT NULL AND series_name != '' AND work_id IS NULL"),
            "books_no_series": ("ID", "Titel", "Path",
                                "SELECT id, title, path FROM books WHERE (series_name IS NULL OR series_name = '')"),
            "authors_no_series": ("ID", "Autor",
                                  "SELECT id, (firstname || ' ' || lastname) FROM authors WHERE id NOT IN (SELECT author_id FROM work_to_author wta JOIN books b ON wta.work_id=b.work_id WHERE b.series_name IS NOT NULL AND b.series_name != '')"),
            "authors_no_works": ("ID", "Autor",
                                 "SELECT id, (firstname || ' ' || lastname) FROM authors WHERE id NOT IN (SELECT author_id FROM work_to_author)"),
            "authors_no_books": ("ID", "Autor",
                                 "SELECT id, (firstname || ' ' || lastname) FROM authors WHERE id NOT IN (SELECT author_id FROM work_to_author)"),
            "works_no_authors": ("ID", "Werk-Titel",
                                 "SELECT id, title FROM works WHERE id NOT IN (SELECT work_id FROM work_to_author)"),
            "books_no_authors": ("ID", "Buchtitel", "Path",
                                 "SELECT id, title, path FROM books WHERE work_id IS NULL OR work_id NOT IN (SELECT work_id FROM work_to_author)"),
            "books_no_works": ("ID", "Buchtitel", "Path", "SELECT id, title, path FROM books WHERE work_id IS NULL"),
            "books_no_index": ("ID", "Titel", "Serie", "Path",
                               "SELECT id, title, series_name, path FROM books WHERE series_name IS NOT NULL AND (series_index IS NULL OR series_index = 0)"),
            "title_duplicates": ("Buchtitel", "Bücher", "Werke",
                                 "SELECT title, COUNT(id) as b_cnt, COUNT(DISTINCT work_id) as w_cnt FROM books GROUP BY title HAVING b_cnt > 1 AND b_cnt > w_cnt ORDER BY b_cnt DESC")
        }
        conf = queries.get(mode)
        if not conf: return
        col_names, query = conf[:-1], conf[-1]
        self.tree["columns"] = col_names
        for col in col_names: self.tree.heading(col, text=col, command=lambda c=col: self._sort_treeview(c, False))
        with self._get_conn() as conn:
            rows = conn.execute(query).fetchall()
            for r in rows: self.tree.insert("", "end", values=list(r))

    def open_in_browser(self):
        items = self.tree.selection()
        if not items: items = self.tree.get_children()
        if not items: return
        cols = list(self.tree["columns"])
        id_list = []
        with self._get_conn() as conn:
            for i in items:
                vals = self.tree.item(i)['values']
                if "Buchtitel" in cols and "Bücher" in cols:
                    res = conn.execute("SELECT id FROM books WHERE title = ?",
                                       (vals[cols.index("Buchtitel")],)).fetchall()
                    id_list.extend([r[0] for r in res])
                elif "ID" in cols:
                    obj_id = vals[cols.index("ID")]
                    if "Autor" in cols:
                        res = conn.execute(
                            "SELECT b.id FROM books b JOIN work_to_author wta ON b.work_id=wta.work_id WHERE wta.author_id=?",
                            (obj_id,)).fetchall()
                        id_list.extend([r[0] for r in res])
                    elif "Werk-Titel" in cols:
                        res = conn.execute("SELECT id FROM books WHERE work_id=?", (obj_id,)).fetchall()
                        id_list.extend([r[0] for r in res])
                    else:
                        id_list.append(obj_id)
                elif "Serienname" in cols:
                    res = conn.execute("SELECT id FROM books WHERE series_name=?",
                                       (vals[cols.index("Serienname")],)).fetchall()
                    id_list.extend([r[0] for r in res])
            unique_ids = list(dict.fromkeys(id_list))
            if unique_ids:
                from Audio.book_browser import BookBrowser
                if self.browser_instance is not None and tk.Toplevel.winfo_exists(self.browser_instance.win):
                    self.browser_instance.load_from_report(unique_ids)
                else:
                    top = tk.Toplevel(self.master)
                    self.browser_instance = BookBrowser(top, initial_list=[{'ID': int(bid)} for bid in unique_ids])
            else:
                messagebox.showinfo("Info", "Keine Bücher zum Öffnen gefunden.")


if __name__ == "__main__":
    root = tk.Tk()
    app = BookAnalyser(root)
    root.mainloop()