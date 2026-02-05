import tkinter as tk
from tkinter import ttk, messagebox
import os

# Importe mit Fehlerbehandlung und Shadowing-Schutz
try:
    from Zoom.author_works import AuthorWorkEditor
    from Zoom.author_manager import AuthorManager
    from Zoom.author_series import AuthorSeriesEditor
except ImportError as err:
    print(f"⚠️ Import-Warnung: {err}")


    # Fallback-Klasse für die IDE-Stabilität
    class AuthorManager:
        def get_top_50_authors(self): return []

        def get_author_image_path(self, slug): return ""


class AuthorBrowser:
    def __init__(self, master_root, selection_callback=None):
        # 1. Instanz-Attribute initialisieren (Behebt 'defined outside __init__')
        self.win = master_root
        self.manager = AuthorManager()
        self.selection_callback = selection_callback
        self.authors_data = []
        self.current_author_id = None
        self.current_view_mode = "top"

        self.search_var = tk.StringVar()
        self.tree = None
        self.img_label = None
        self.fields = {}
        self.txt_vita = None
        self.serie_tree = None
        self.work_tree = None

        # 2. UI Aufbau
        self.setup_ui()

        # 3. Start-Daten laden
        self.load_top_30()

    def setup_ui(self):
        self.win.title("Autor-Master-Browser v1.7.4 - Clean Code")
        self.win.geometry("1400x900")

        # --- Top Bar ---
        top_frame = ttk.Frame(self.win, padding=(10, 5))
        top_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Label(top_frame, text="Autor suchen:").pack(side=tk.LEFT)
        self.search_var.trace_add("write", lambda *args: self.filter_list())
        ttk.Entry(top_frame, textvariable=self.search_var, width=30).pack(side=tk.LEFT, padx=5)

        ttk.Button(top_frame, text="Bild-Refresh", command=self.update_image_display).pack(side=tk.RIGHT)

        # Paned Window mit Konstanten
        paned = ttk.PanedWindow(self.win, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 1. Links: Autorenliste
        left_frame = ttk.LabelFrame(paned, text="Autoren", padding=5)
        paned.add(left_frame, weight=2)

        cols = ("Name", "Total", "DE", "EN", "ES", "FR", "IT")
        self.tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="extended")
        for col in cols:
            self.tree.heading(col, text=col, command=lambda _c=col: self.sort_table(self.tree, _c))
            self.tree.column(col, width=200 if col == "Name" else 35, anchor="w" if col == "Name" else tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.load_selected_author)

        left_btn_frame = ttk.Frame(left_frame)
        left_btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(left_btn_frame, text="Top 50", command=self.load_top_30).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(left_btn_frame, text="Bottom", command=self.load_bottom).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(left_btn_frame, text="★ Favoriten", command=self.load_favorites).pack(side=tk.LEFT, expand=True,
                                                                                         fill=tk.X)
        ttk.Button(left_btn_frame, text="🗑️ Löschen", command=self.delete_current_author).pack(side=tk.LEFT,
                                                                                               expand=True, fill=tk.X)

        # 2. Mitte: Details
        mid_label_frame = ttk.LabelFrame(paned, text="Autor-Details", padding=5)
        paned.add(mid_label_frame, weight=1)

        save_btn = ttk.Button(mid_label_frame, text="💾 Autor speichern", command=self.save_current)
        save_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

        self.img_label = tk.Label(mid_label_frame, text="Bild-Vorschau", bg="#eee", relief="ridge", height=15)
        self.img_label.pack(side=tk.TOP, pady=(0, 5), fill=tk.X)

        form_frame = ttk.Frame(mid_label_frame)
        form_frame.pack(side=tk.TOP, fill=tk.X)

        field_configs = [
            ("Name:", "display_name"), ("Sprache:", "main_language"),
            ("Link:", "info_link"), ("Slug:", "name_slug"),
            ("Stars (0-5):", "stars")
        ]
        for lbl, key in field_configs:
            row = ttk.Frame(form_frame)
            row.pack(fill=tk.X, pady=1)
            tk.Label(row, text=lbl, width=12, anchor="w").pack(side=tk.LEFT)
            ent = ttk.Entry(row)
            ent.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            self.fields[key] = ent

        tk.Label(mid_label_frame, text="Vita:").pack(side=tk.TOP, anchor="w", pady=(5, 0))
        self.txt_vita = tk.Text(mid_label_frame, width=45, wrap="word", undo=True)
        self.txt_vita.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)

        # 3. Rechts: Serien & Werke
        right_paned = ttk.PanedWindow(paned, orient=tk.VERTICAL)
        paned.add(right_paned, weight=2)

        serie_frame = ttk.LabelFrame(right_paned, text="Serien", padding=5)
        right_paned.add(serie_frame, weight=2)
        self.serie_tree = ttk.Treeview(serie_frame, columns=("ID", "Name", "Works"), show="headings")
        self.serie_tree.heading("ID", text="ID")
        self.serie_tree.column("ID", width=0, stretch=tk.NO)
        self.serie_tree.pack(fill=tk.BOTH, expand=True)
        self.serie_tree.bind("<<TreeviewSelect>>", self.on_serie_selected)

        work_frame = ttk.LabelFrame(right_paned, text="Werke", padding=5)
        right_paned.add(work_frame, weight=3)
        self.work_tree = ttk.Treeview(work_frame, columns=("ID", "Titel", "Index", "Books"), show="headings")
        self.work_tree.heading("ID", text="ID")
        self.work_tree.heading("Titel", text="Titel")
        self.work_tree.heading("Index", text="Index")
        self.work_tree.column("Index", width=60, stretch=tk.NO, anchor="w")
        self.work_tree.pack(fill=tk.BOTH, expand=True)
        self.work_tree.bind("<Double-1>", lambda event_args: self.open_work_editor())

        right_btn_frame = ttk.Frame(work_frame)
        right_btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(right_btn_frame, text="✏️ Serie", command=self.open_series_editor).pack(side=tk.LEFT, expand=True,
                                                                                           fill=tk.X)
        ttk.Button(right_btn_frame, text="✏️ Werk", command=self.open_work_editor).pack(side=tk.LEFT, expand=True,
                                                                                        fill=tk.X)
        ttk.Button(right_btn_frame, text="🗑️ Cleanup", command=self.cleanup_empty_nodes).pack(side=tk.LEFT, expand=True,
                                                                                              fill=tk.X)

    def update_image_display(self, slug=None):
        if not slug:
            try:
                slug = self.fields["name_slug"].get().strip()
            except (AttributeError, KeyError):
                return

        if not slug:
            self.img_label.config(image='', text="Kein Slug")
            return

        img_path = self.manager.get_author_image_path(slug)
        if os.path.exists(img_path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(img_path)
                img.thumbnail((300, 400))
                photo = ImageTk.PhotoImage(img)
                self.img_label.config(image=photo, text="", width=0, height=0)
                self.img_label.image = photo
            except Exception:
                self.img_label.config(image='', text="Bildfehler")
        else:
            self.img_label.config(image='', text="Kein Bild")

    def filter_list(self):
        search = self.search_var.get().strip()
        if not search:
            self.load_top_30()
        elif len(search) >= 3:
            self.current_view_mode = "search"
            results = self.manager.search_authors(search)
            self.refresh_tree(results)

    def load_top_30(self):
        self.current_view_mode = "top"
        self.refresh_tree(self.manager.get_top_50_authors())

    def load_bottom(self):
        self.current_view_mode = "bottom"
        self.refresh_tree(self.manager.load_bottom_authors())

    def load_favorites(self):
        self.current_view_mode = "favs"
        self.refresh_tree(self.manager.load_highlighted_authors())

    def refresh_current_view(self):
        if self.current_view_mode == "search":
            search = self.search_var.get().strip()
            data = self.manager.search_authors(search) if len(search) >= 3 else self.manager.get_top_50_authors()
        elif self.current_view_mode == "bottom":
            data = self.manager.load_bottom_authors()
        elif self.current_view_mode == "favs":
            data = self.manager.load_highlighted_authors()
        else:
            data = self.manager.get_top_50_authors()
        self.refresh_tree(data)

    def refresh_tree(self, data):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for r in data:
            row_dict = dict(r) if not isinstance(r, dict) else r
            self.tree.insert("", tk.END, iid=row_dict['id'], values=(
                row_dict.get('display_name', 'Unbekannt'), row_dict.get('total', 0),
                row_dict.get('de', 0), row_dict.get('en', 0), row_dict.get('es', 0),
                row_dict.get('fr', 0), row_dict.get('it', 0)
            ))

    def load_selected_author(self, event):
        selection = self.tree.selection()
        if not selection:
            self.clear_all_views()
            return
        self.current_author_id = selection[0]
        author = self.manager.get_author(int(self.current_author_id))
        if author:
            self.set_field_value("display_name", author.display_name)
            self.set_field_value("main_language", author.main_language or "")
            self.set_field_value("info_link", author.info_link)
            self.set_field_value("name_slug", author.slug)
            self.set_field_value("stars", getattr(author, 'stars', 0))
            self.txt_vita.delete("1.0", tk.END)
            self.txt_vita.insert("1.0", author.vita or "")
            self.update_image_display(author.slug)
            self.refresh_series_list(author.id)

    def clear_all_views(self):
        self.current_author_id = None
        for f in self.fields.values(): f.delete(0, tk.END)
        self.txt_vita.delete("1.0", tk.END)
        self.img_label.config(image='', text="Bild-Vorschau")
        for item in self.serie_tree.get_children(): self.serie_tree.delete(item)
        for item in self.work_tree.get_children(): self.work_tree.delete(item)

    def refresh_series_list(self, author_id):
        for item in self.serie_tree.get_children(): self.serie_tree.delete(item)
        for item in self.work_tree.get_children(): self.work_tree.delete(item)
        series = self.manager.get_series_by_author(author_id)
        for s in series:
            self.serie_tree.insert("", tk.END, iid=s['id'], values=(s['id'], s['name'], s['work_count']))

        children = self.serie_tree.get_children()
        if children:
            self.serie_tree.selection_set(children[0])
            self.serie_tree.focus(children[0])
        else:
            works = self.manager.get_works_by_serie(0, int(author_id))
            for w in works:
                idx_val = w.get('series_index', 0)
                self.work_tree.insert("", tk.END, iid=w['id'],
                                      values=(w['id'], w['title'], self.format_index(idx_val), w['book_count']))

    def on_serie_selected(self, event):
        sel = self.serie_tree.selection()
        if not sel: return
        serie_id = sel[0]
        for item in self.work_tree.get_children(): self.work_tree.delete(item)
        works = self.manager.get_works_by_serie(int(serie_id), int(self.current_author_id))
        for w in works:
            idx_val = w.get('series_index', 0)
            self.work_tree.insert("", tk.END, iid=w['id'],
                                  values=(w['id'], w['title'], self.format_index(idx_val), w['book_count']))

    def format_index(self, raw_nr):
        if raw_nr is None or raw_nr == "" or raw_nr == 0: return ""
        try:
            num = float(raw_nr)
            return f"{int(num):03d}" if num == int(num) else f"{int(num):03d}.{str(num).split('.')[1]}"
        except (ValueError, TypeError):
            return str(raw_nr)

    def save_current(self):
        if not self.current_author_id: return
        author = self.manager.get_author(int(self.current_author_id))
        saved_id = str(self.current_author_id)

        full_name = self.fields["display_name"].get().strip()
        author.firstname, author.lastname = (full_name.rsplit(" ", 1) if " " in full_name else ("", full_name))
        author.slug = self.fields["name_slug"].get().strip()
        author.main_language = self.fields["main_language"].get().strip()
        author.vita = self.txt_vita.get("1.0", tk.END).strip()
        author.info_link = self.fields["info_link"].get()
        try:
            author.stars = int(self.fields["stars"].get().strip() or 0)
        except (ValueError, TypeError):
            author.stars = 0

        self.manager.smart_save(author)
        self.refresh_current_view()

        if self.tree.exists(saved_id):
            self.tree.selection_set(saved_id)
            self.tree.see(saved_id)

    def open_series_editor(self):
        sel = self.serie_tree.selection()
        if sel: AuthorSeriesEditor(self.win, self.manager, sel[0], self.current_author_id)

    def open_work_editor(self):
        sel = self.work_tree.selection()
        if sel:
            item_data = self.work_tree.item(sel[0])
            values = item_data.get('values', [None, None, 0])
            w_id = values[0]
            s_index = values[2]
            if w_id:
                editor = AuthorWorkEditor(self.win, self.manager, w_id, self.current_author_id, s_index)
                self.win.wait_window(editor)
                self.on_serie_selected(None)

    def cleanup_empty_nodes(self):
        if self.current_author_id:
            self.manager.cleanup_empty_series_and_works(self.current_author_id)
            self.load_selected_author(None)

    def delete_current_author(self):
        selection = self.tree.selection()
        if not selection: return
        if not messagebox.askyesno("Löschen", f"{len(selection)} Autoren löschen?"): return

        for author_id in selection:
            self.manager.cleanup_empty_series_and_works(int(author_id))
            self.manager.delete_author_if_empty(int(author_id))

        self.refresh_current_view()
        self.clear_all_views()

    @staticmethod
    def sort_table(tree, col):
        l = [(tree.set(k, col), k) for k in tree.get_children("")]
        try:
            l.sort(key=lambda t: float(t[0]) if t[0] else 0.0, reverse=True)
        except (ValueError, TypeError):
            l.sort(key=lambda t: t[0].lower() if t[0] else "")
        for index, (val, k) in enumerate(l):
            tree.move(k, "", index)

    def set_field_value(self, field_name, value):
        self.fields[field_name].delete(0, tk.END)
        self.fields[field_name].insert(0, str(value) if value else "")


if __name__ == "__main__":
    app_root = tk.Tk()
    app = AuthorBrowser(app_root)
    app_root.mainloop()