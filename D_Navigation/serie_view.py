"""
DATEI: D_Navigation/series_view.py
BESCHREIBUNG der Navigation:
    - Treeview, Notebook, Buttons, Entry.get().	Sie kümmert sich nur um die Pixel und Benutzer-Interaktion.
"""
import tkinter as tk
from tkinter import ttk

class SeriesView:
    def __init__(self, root, bridge):
        self.root = root
        self.bridge = bridge
        self.fields = {}  # Speicher für die Entry-Felder (Editor)
        self._setup_ui()
        # Initiales Laden der Daten über die Brücke
        self.bridge.load_initial_data()

    def _setup_ui(self):
        self.root.title("Series-Master-Browser v3.0 (Atomic-Engine)")
        self.root.geometry("1600x850")

        # --- TOP FRAME (SUCHE) ---
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        tk.Label(top_frame, text="Serie / Autor suchen:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.bridge.filter_series(self.search_var.get()))
        ttk.Entry(top_frame, textvariable=self.search_var, width=40).pack(side=tk.LEFT, padx=10)

        # --- HAUPT-LAYOUT (PANED WINDOW) ---
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 1. LINKS: SERIEN-LISTE
        f_left = ttk.LabelFrame(self.paned, text=" Serien-Übersicht ", padding=5)
        self.paned.add(f_left, weight=3)

        # Container für Tree + Scrollbar
        tree_container = ttk.Frame(f_left)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.cols = ("id", "name", "author", "count_w", "count_b", "count_a")
        self.tree = ttk.Treeview(tree_container, columns=self.cols, show="headings")

        # SCROLLBAR hinzufügen
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Pack-Reihenfolge ist wichtig
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Spalten-Header anpassen (inklusive der neuen Σ(B) Spalte)
        cap = {"id": "ID", "name": "Serie", "author": "Haupt-Autor",
               "count_w": "Σ(W)", "count_b": "Σ(B)", "count_a": "Σ(A)"}
        for c in self.cols:
            # Sortier-Kommando binden
            self.tree.heading(c, text=cap[c], command=lambda _c=c: self._sort_column(_c, False))

            # Breiten anpassen
            if c == "id": w = 50
            elif c in ["count_w", "count_a"]: w = 45
            elif c == "name": w = 250
            else: w = 180  # Autor
            self.tree.column(c, width=w, anchor="center" if "count" in c or c=="id" else "w")

        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_series_selected)

        # 2. MITTE: EDITOR
        f_mid = ttk.LabelFrame(self.paned, text=" Master-Editor ", padding=10)
        self.paned.add(f_mid, weight=1)

        # Buttons oben
        ttk.Button(f_mid, text="🗑️ Serie auflösen", command=self._on_delete_clicked).pack(fill=tk.X, pady=5)

        # Eingabefelder
        for lbl, key in [("Serien-Name:", "name"), ("Padding:", "padding")]:
            tk.Label(f_mid, text=lbl, anchor="w").pack(fill=tk.X, pady=(5, 0))
            self.fields[key] = ttk.Entry(f_mid)
            self.fields[key].pack(fill=tk.X, pady=2)

        ttk.Button(f_mid, text="💾 Änderungen speichern", command=self._on_save_clicked).pack(fill=tk.X, pady=10)

        # Merge Bereich
        ttk.Separator(f_mid, orient='horizontal').pack(fill=tk.X, pady=15)
        tk.Label(f_mid, text="Zusammenführen mit:", anchor="w").pack(fill=tk.X)
        self.merge_combo = ttk.Combobox(f_mid)
        self.merge_combo.pack(fill=tk.X, pady=5)
        ttk.Button(f_mid, text="🔗 Merge ausführen", command=self._on_merge_clicked).pack(fill=tk.X, pady=5)

        # 3. RECHTS: NOTEBOOK (TABS)
        f_right = ttk.LabelFrame(self.paned, text=" Details & Management ", padding=5)
        self.paned.add(f_right, weight=4)

        self.notebook = ttk.Notebook(f_right)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab A: Bücher
        self.tab_books = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_books, text=" 📦 Zugeordnete Bücher ")
        self.book_tree = ttk.Treeview(self.tab_books, columns=("id", "idx", "path"), show="headings")
        self.book_tree.heading("id", text="ID");
        self.book_tree.column("id", width=50)
        self.book_tree.heading("idx", text="Idx");
        self.book_tree.column("idx", width=40)
        self.book_tree.heading("path", text="Pfad");
        self.book_tree.column("path", width=500)
        self.book_tree.pack(fill=tk.BOTH, expand=True)

        # Tab B: Clones
        self.tab_clones = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_clones, text=" 🔗 Dubletten-Check ")
        self.clone_tree = ttk.Treeview(self.tab_clones, columns=("id", "name", "author"), show="headings")
        self.clone_tree.heading("id", text="ID");
        self.clone_tree.column("id", width=50)
        self.clone_tree.heading("name", text="Serie");
        self.clone_tree.column("name", width=200)
        self.clone_tree.heading("author", text="Autor");
        self.clone_tree.column("author", width=200)
        self.clone_tree.pack(fill=tk.BOTH, expand=True)

    # --- UI UPDATES (Von der Bridge aufgerufen) ---
    # D_Navigation/serie_view.py

    def update_series_list(self, df):
        self.tree.delete(*self.tree.get_children())
        # Sortiere den DF vor der Anzeige absteigend nach Büchern,
        # damit Perry Rhodan/NEO oben stehen
        df_sorted = df.sort_values(by='count_b', ascending=False)

        for _, row in df_sorted.iterrows():
            self.tree.insert("", "end", iid=str(row['id']), values=(
                row['id'],
                row['name'],
                row['author_full'],
                row['count_w'],
                row['count_b'],
                row['count_a']
            ))

    def _sort_column(self, col, reverse):
        """Verbesserte Sortierung für numerische Werte."""
        data = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        # Korrekte Zuordnung der numerischen Spalten
        if col in ["id", "count_w", "count_b", "count_a"]:
            data.sort(key=lambda t: int(t[0]) if t[0] and str(t[0]).isdigit() else 0, reverse=reverse)
        else:
            data.sort(key=lambda t: t[0].lower(), reverse=reverse)

        for index, (val, k) in enumerate(data):
            self.tree.move(k, "", index)
        self.tree.heading(col, command=lambda: self._sort_column(col, not reverse))

    def display_series_details(self, atom):
        """Befüllt die Entry-Felder in der Mitte."""
        self.fields["name"].delete(0, tk.END)
        self.fields["name"].insert(0, atom.name or "")
        self.fields["padding"].delete(0, tk.END)
        self.fields["padding"].insert(0, str(getattr(atom, 'padding', 2)))

    # --- EVENTS (Leiten an die Bridge weiter) ---

    def _on_series_selected(self, event):
        sel = self.tree.selection()
        if sel: self.bridge.select_series(sel[0])

    def _on_save_clicked(self):
        data = {k: v.get() for k, v in self.fields.items()}
        self.bridge.save_series_changes(data)

    def _on_delete_clicked(self):
        self.bridge.delete_current_series()

    def _on_merge_clicked(self):
        target = self.merge_combo.get()
        self.bridge.execute_merge(target)

    def update_book_list(self, books):
        """Füllt den Tab 'Zugeordnete Bücher'."""
        self.book_tree.delete(*self.book_tree.get_children())
        for b in books:
            self.book_tree.insert("", "end", iid=str(b['id']), values=(
                b['id'],
                b.get('series_index', '0'),
                b.get('path', '---')
            ))

    def update_clone_list(self, clones):
        """Füllt den Tab 'Dubletten-Check'."""
        self.clone_tree.delete(*self.clone_tree.get_children())
        for c in clones:
            self.clone_tree.insert("", "end", iid=str(c['id']), values=(
                c['id'],
                c['name'],
                c.get('author_full', '---')
            ))
