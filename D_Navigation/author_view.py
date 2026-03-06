# D_Navigation/author_view.py
import os
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk


class AuthorView:
    def __init__(self, win, bridge):
        self.root = win
        self.bridge = bridge
        self.search_var = tk.StringVar()
        self._setup_ui()
        self.load_authors()

    def _setup_ui(self):
        self.root.geometry("1500x900")
        self.root.title("Enterprise - Author Master Control v3.0")

        # --- Top Search Bar ---
        self.top_frame = tk.Frame(self.root, padx=10, pady=5)
        self.top_frame.pack(side=tk.TOP, fill=tk.X)
        tk.Label(self.top_frame, text="Autor suchen:").pack(side=tk.LEFT)
        self.search_var.trace_add("write", lambda *args: self._on_search_changed())
        ttk.Entry(self.top_frame, textvariable=self.search_var, width=40).pack(side=tk.LEFT, padx=10)

        # NEU: Das Pfad-Anzeige-Feld
        tk.Label(self.top_frame, text="zB.:     ", fg="gray").pack(side=tk.LEFT, padx=(20, 5))

        # Wir nutzen ein Entry, damit man den Text kopieren kann (ReadOnly)
        self.ent_sample_path = tk.Entry(
            self.top_frame,
            width=80,
            font=("Arial", 12),
            fg="#555",
            relief="flat",
            bg=self.root.cget("bg")  # Gleiche Farbe wie Hintergrund
        )
        self.ent_sample_path.pack(side=tk.LEFT, fill="x", expand=True)
        self.ent_sample_path.insert(0, "-")
        self.ent_sample_path.config(state="readonly")

        # Rechts neben dem Pfad-Entry in der top_frame
        self.btn_browse_paths = tk.Button(
            self.top_frame,
            text="🔍 Alle Pfade zeigen",
            command=self._on_browse_all_paths_clicked,
            bg="#ecf0f1"
        )
        self.btn_browse_paths.pack(side=tk.LEFT, padx=5)

        # --- Main Layout (3 Columns) ---
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=6, bg="#cccccc")
        self.paned.pack(fill="both", expand=True)

        # 1. LINKE SPALTE: Liste
        self.f_left = tk.Frame(self.paned, width=350)
        self.left_scroll = ttk.Scrollbar(self.f_left, orient="vertical")
        self.left_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.cols = ("name", "total", "de", "en", "es", "fr", "it")
        self.tree = ttk.Treeview(self.f_left, columns=self.cols, show="headings", yscrollcommand=self.left_scroll.set)
        self.left_scroll.config(command=self.tree.yview)

        cap = {"name": "Autor", "total": "Σ", "de": "DE", "en": "EN", "es": "ES", "fr": "FR", "it": "IT"}
        for cid in self.cols:
            self.tree.heading(cid, text=cap[cid], command=lambda _c=cid: self._sort_table(self.tree, _c))
            self.tree.column(cid, width=150 if cid == "name" else 30, anchor="w" if cid == "name" else "center")

        self.tree.pack(fill="both", expand=True)
        self.paned.add(self.f_left)

        # 2. MITTLERE SPALTE: Details & Bild
        self.f_mid = tk.Frame(self.paned, width=500, padx=15, pady=10)
        self._setup_mid_column()
        self.paned.add(self.f_mid)


        # 3. RECHTE SPALTE: Vita Editor
        self.f_right = tk.Frame(self.paned, width=550, padx=15, pady=10)
        self._setup_right_column()
        self.paned.add(self.f_right)

        self.tree.bind("<<TreeviewSelect>>", self._on_author_selected)

        # Rechtsklick-Menü definieren
        self.context_menu = tk.Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="📁 Dateipfad kopieren", command=self._copy_author_file_path)

        # Event an den Treeview binden (Rechtsklick)
        self.tree.bind("<Button-3>", self._show_context_menu)  # Windows/Linux
        self.tree.bind("<Button-2>", self._show_context_menu)  # macOS

    def _show_context_menu(self, event):
        # Zeile unter dem Cursor auswählen
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.context_menu.post(event.x_root, event.y_root)

    def _copy_author_file_path(self):
        sel = self.tree.selection()
        if not sel: return

        author_id = sel[0]
        full_path = self.bridge.get_sample_path(author_id)

        # In Zwischenablage kopieren
        self.root.clipboard_clear()
        self.root.clipboard_append(full_path)

        messagebox.showinfo("Pfad kopiert", f"Pfad wurde in die Zwischenablage kopiert:\n\n{full_path}")

    def _setup_mid_column(self):
        # Profilbereich (Bild + Name)
        header_frame = tk.Frame(self.f_mid)
        header_frame.pack(fill="x")

        self.lbl_image = tk.Label(header_frame, text="Kein Bild", bg="#d0d0d0", width=20, height=10, relief="sunken")
        self.lbl_image.pack(side="left", padx=(0, 15))

        info_meta = tk.Frame(header_frame)
        info_meta.pack(side="left", fill="both", expand=True)

        tk.Label(info_meta, text="Vorname:").pack(anchor="w")
        self.ent_firstname = ttk.Entry(info_meta, font=("Arial", 11))
        self.ent_firstname.pack(fill="x", pady=(0, 5))

        tk.Label(info_meta, text="Nachname:").pack(anchor="w")
        self.ent_lastname = ttk.Entry(info_meta, font=("Arial", 11, "bold"))
        self.ent_lastname.pack(fill="x", pady=(0, 5))

        self.lbl_auth_id = tk.Label(info_meta, text="ID: -", fg="gray", font=("Arial", 8))
        self.lbl_auth_id.pack(anchor="e")

        # Navigation Button
        self.btn_open_series = tk.Button(self.f_mid, text="📂 Serien des Autors anzeigen", bg="#3498db", fg="white",
                                         font=("Arial", 10, "bold"), command=self._on_open_series_browser_clicked,
                                         state="disabled")
        self.btn_open_series.pack(fill="x", pady=10)

        # Metadaten Grid
        grid_frame = tk.LabelFrame(self.f_mid, text=" Biografie-Daten ", padx=10, pady=10)
        grid_frame.pack(fill="x", pady=5)

        fields = [("Geburt:", "birth_date"), ("Ort:", "birth_place"), ("Land:", "country"), ("Sterne:", "stars")]
        self.meta_entries = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(grid_frame, text=label).grid(row=i, column=0, sticky="w", pady=2)
            ent = ttk.Entry(grid_frame)
            ent.grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            self.meta_entries[key] = ent
        grid_frame.columnconfigure(1, weight=1)

        # Sprach-Links
        link_frame = tk.LabelFrame(self.f_mid, text=" Web / Wikipedia Links ", padx=10, pady=10)
        link_frame.pack(fill="x", pady=5)
        self.url_entries = {}
        for lang in ["de", "en", "fr", "es", "it"]:
            row = tk.Frame(link_frame)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=lang.upper(), width=4).pack(side="left")
            ent = ttk.Entry(row)
            ent.pack(side="left", fill="x", expand=True)
            self.url_entries[lang] = ent

        # Aliases
        alias_frame = tk.Frame(self.f_mid)
        alias_frame.pack(fill="x", pady=10)
        tk.Label(alias_frame, text="Aliase:", font=("Arial", 9, "bold")).pack(side="left")
        self.ent_aliases = ttk.Entry(alias_frame)
        self.ent_aliases.pack(side="left", fill="x", expand=True, padx=(5, 0))

        self.btn_find_dupes = tk.Button(
            self.f_mid,
            text="🔍 Dubletten suchen",
            command=self.bridge.find_duplicates_for_current,
            bg="#f39c12", fg="white"
        )

        self.btn_find_dupes.pack(fill="x", pady=5)
        self.btn_sort_len = tk.Button(self.top_frame, text="📏 Sort by Len",
                                      command=self._on_sort_by_length, bg="#f8f9fa")
        self.btn_sort_len.pack(side=tk.LEFT, padx=5)

        # Save Button
        tk.Button(self.f_mid, text="💾 Stammdaten speichern", bg="#27ae60", fg="white",
                  font=("Arial", 10, "bold"), command=self._on_save_author_clicked, height=2).pack(fill="x",
                                                                                                   pady=(10, 0))

    def _on_sort_by_length(self):
        sorted_df = self.bridge.get_authors_sorted_by_len()
        self.load_authors(sorted_df)

    def _setup_right_column(self):
        tk.Label(self.f_right, text="VITA / BIOGRAFIE", font=("Arial", 11, "bold")).pack(anchor="w")
        v_frame = tk.Frame(self.f_right)
        v_frame.pack(fill="both", expand=True, pady=10)

        self.vita_scroll = ttk.Scrollbar(v_frame)
        self.vita_scroll.pack(side="right", fill="y")

        self.txt_vita = tk.Text(v_frame, font=("Georgia", 11), wrap="word",
                                yscrollcommand=self.vita_scroll.set, padx=10, pady=10)
        self.txt_vita.pack(side="left", fill="both", expand=True)
        self.vita_scroll.config(command=self.txt_vita.yview)

    # --- Logik-Methoden ---
    def load_authors(self, df=None):
        if df is None:
            df = self.bridge.get_author_df()

        # Bestehende Einträge im Treeview löschen
        for item in self.tree.get_children():
            self.tree.delete(item)

        for _, row in df.iterrows():
            # Sicherer Zugriff mit .get() - falls Spalte fehlt, wird 0 eingesetzt
            # Das verhindert den KeyError: 'en'
            self.tree.insert("", "end", iid=str(row.get('id')), values=(
                row.get('display_name', 'Unbekannt'),
                row.get('total', 0),
                row.get('de', 0),
                row.get('en', 0),  # Hier passierte der Fehler
                row.get('es', 0),
                row.get('fr', 0),
                row.get('it', 0)
            ))

    def display_author_master(self, a):
        """Befüllt alle Widgets mit Daten aus dem AuthorTData Objekt 'a'."""
        self.lbl_auth_id.config(text=f"ID: {a.id}")
        self.btn_open_series.config(state="normal", text=f"📂 Serien von '{a.lastname}'")

        self.ent_firstname.delete(0, tk.END);
        self.ent_firstname.insert(0, a.firstname or "")
        self.ent_lastname.delete(0, tk.END);
        self.ent_lastname.insert(0, a.lastname or "")

        # Metadaten
        for key in ["birth_date", "birth_place", "country", "stars"]:
            self.meta_entries[key].delete(0, tk.END)
            val = getattr(a, key, "")
            self.meta_entries[key].insert(0, str(val) if val is not None else "")

        # URLs
        for lang in ["de", "en", "fr", "es", "it"]:
            self.url_entries[lang].delete(0, tk.END)
            val = getattr(a, f"url_{lang}", "")
            self.url_entries[lang].insert(0, val or "")

        # Aliases & Vita
        self.ent_aliases.delete(0, tk.END)
        if hasattr(a, 'aliases') and a.aliases:
            self.ent_aliases.insert(0, ", ".join(list(a.aliases)))

        self.txt_vita.delete("1.0", tk.END)
        self.txt_vita.insert("1.0", a.vita or "")

    def _on_author_selected(self, e):
        sel = self.tree.selection()
        if sel:
            a_id = sel[0]
            self.bridge.select_author(a_id)
            # NEU: Pfad oben anzeigen
            self.update_sample_path_display(a_id)

    def _on_search_changed(self):
        s = self.search_var.get().strip()
        if len(s) >= 3 or len(s) == 0: self.bridge.search_authors(s)

    def _on_save_author_clicked(self):
        a_id = self.lbl_auth_id.cget("text").replace("ID: ", "")
        if a_id == "-": return

        # Hier alle Daten aus den Feldern sammeln und an die Bridge senden
        data = {
            "firstname": self.ent_firstname.get(),
            "lastname": self.ent_lastname.get(),
            "vita": self.txt_vita.get("1.0", tk.END).strip(),
            "aliases": set([x.strip() for x in self.ent_aliases.get().split(",") if x.strip()])
        }
        # Metadaten hinzufügen
        for key, ent in self.meta_entries.items(): data[key] = ent.get()
        # URLs hinzufügen
        for lang, ent in self.url_entries.items(): data[f"url_{lang}"] = ent.get()

        self.bridge.update_author_full(a_id, data)

    def _on_open_series_browser_clicked(self):
        a_id = self.lbl_auth_id.cget("text").replace("ID: ", "")
        if a_id != "-": self.bridge.open_series_browser_for_author(a_id)

    def _sort_table(self, tree, col):
        data = [(tree.set(k, col), k) for k in tree.get_children("")]
        is_numeric = col in ["total", "de", "en", "es", "fr", "it"]
        if is_numeric:
            data.sort(key=lambda t: float(t[0]) if t[0] else 0, reverse=True)
        else:
            data.sort(key=lambda t: t[0].lower() if t[0] else "")
        for index, (val, k) in enumerate(data): tree.move(k, "", index)

    def display_author_master(self, a):
        """Befüllt die UI und lädt das Bild basierend auf dem Slug."""
        self.lbl_auth_id.config(text=f"ID: {a.id}")
        self.btn_open_series.config(state="normal", text=f"📂 Serien von '{a.lastname}'")

        # Textfelder befüllen
        self.ent_firstname.delete(0, tk.END);
        self.ent_firstname.insert(0, a.firstname or "")
        self.ent_lastname.delete(0, tk.END);
        self.ent_lastname.insert(0, a.lastname or "")

        # Metadaten (Sterne, etc.)
        for key in ["birth_date", "birth_place", "country", "stars"]:
            self.meta_entries[key].delete(0, tk.END)
            val = getattr(a, key, "")
            self.meta_entries[key].insert(0, str(val) if val is not None else "")

        # Aliase & Vita
        self.ent_aliases.delete(0, tk.END)
        if hasattr(a, 'aliases') and a.aliases:
            self.ent_aliases.insert(0, ", ".join(list(a.aliases)))

        self.txt_vita.delete("1.0", tk.END)
        self.txt_vita.insert("1.0", a.vita or "")

        # --- BILD LADEN ---
        # Wir nutzen den Slug aus dem Objekt 'a'
        self._update_image_display(a.slug)

    def _update_image_display(self, slug):
        """Lädt das Bild aus dem festen Autoren-Verzeichnis."""
        if not slug:
            self.lbl_image.config(image='', text="Kein Slug")
            return

        # Dein Pfad aus dem Beispiel
        base_path = r"D:\Bücher\Autoren"
        img_path = os.path.join(base_path, f"{slug}.jpg")

        if os.path.exists(img_path):
            try:
                img = Image.open(img_path)
                # Thumbnail-Größe passend zur mittleren Spalte
                img.thumbnail((250, 350))

                photo = ImageTk.PhotoImage(img)
                self.lbl_image.config(image=photo, text="", width=0, height=0)

                # Wichtig: Referenz behalten, damit das Bild nicht verschwindet
                self.lbl_image.image = photo
            except Exception as e:
                print(f"Fehler beim Bildladen: {e}")
                self.lbl_image.config(image='', text="Bildfehler")
        else:
            # Wenn kein Bild da ist, zeigen wir den Namen der erwarteten Datei
            self.lbl_image.config(image='', text=f"Fehlt:\n{slug}.jpg")


    def _setup_right_column(self):
        # Container für die rechte Spalte
        self.right_container = tk.Frame(self.f_right)
        self.right_container.pack(fill="both", expand=True)

        # Ansicht 1: Vita Editor (Standard)
        self.vita_frame = tk.Frame(self.right_container)
        tk.Label(self.vita_frame, text="VITA / BIOGRAFIE", font=("Arial", 11, "bold")).pack(anchor="w")

        v_scroll_frame = tk.Frame(self.vita_frame)
        v_scroll_frame.pack(fill="both", expand=True, pady=10)
        self.vita_scroll = ttk.Scrollbar(v_scroll_frame)
        self.vita_scroll.pack(side="right", fill="y")
        self.txt_vita = tk.Text(v_scroll_frame, font=("Georgia", 11), wrap="word",
                                yscrollcommand=self.vita_scroll.set, padx=10, pady=10)
        self.txt_vita.pack(side="left", fill="both", expand=True)
        self.vita_scroll.config(command=self.txt_vita.yview)
        self.vita_frame.pack(fill="both", expand=True)

        # Ansicht 2: Merge-Dialog (Standardmäßig versteckt)
        self.merge_frame = tk.Frame(self.right_container)
        tk.Label(self.merge_frame, text="AUTOREN MERGEN (DUBLETTEN)", font=("Arial", 11, "bold"), fg="red").pack(anchor="w")

        self.merge_list = ttk.Treeview(self.merge_frame, columns=("id", "name", "count"), show="headings")
        self.merge_list.heading("id", text="ID")
        self.merge_list.heading("name", text="Name im System")
        self.merge_list.heading("count", text="Werke")
        self.merge_list.pack(fill="both", expand=True, pady=10)

        btn_row = tk.Frame(self.merge_frame)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="Abbrechen", command=self.show_vita).pack(side="left")
        tk.Button(btn_row, text="Selektierte Dublette MERGEN", bg="#e74c3c", fg="white",
                  command=self._on_merge_confirmed).pack(side="right")


    def show_merge_ui(self, duplicates):
        """Schaltet die rechte Spalte auf den Merge-Dialog um."""
        self.vita_frame.pack_forget()
        self.merge_frame.pack(fill="both", expand=True)

        # Liste leeren und mit Dubletten füllen
        for item in self.merge_list.get_children(): self.merge_list.delete(item)
        for d in duplicates:
            self.merge_list.insert("", "end", values=(d['id'], d['name'], d['work_count']))


    def show_vita(self):
        """Schaltet zurück zur Vita."""
        self.merge_frame.pack_forget()
        self.vita_frame.pack(fill="both", expand=True)

    def _on_merge_confirmed(self):
        """Wird aufgerufen, wenn der User im Merge-Frame auf den roten Button klickt."""
        sel = self.merge_list.selection()
        if not sel:
            messagebox.showwarning("Selektion", "Bitte wählen Sie eine Dublette aus der Liste aus.")
            return

        # Die ID des Slaves aus der ersten Spalte des Treeview holen
        item_values = self.merge_list.item(sel[0], "values")
        slave_id = item_values[0]
        slave_name = item_values[1]

        # Die ID des Masters steht in unserem Label in der Mitte
        master_id_raw = self.lbl_auth_id.cget("text")  # z.B. "ID: 123"
        master_id = master_id_raw.replace("ID: ", "").strip()

        if master_id == "-":
            messagebox.showerror("Fehler", "Kein gültiger Master-Autor ausgewählt.")
            return

        # Sicherheitsabfrage
        msg = f"Möchten Sie den Autor '{slave_name}' wirklich in den aktuellen Autor mergen?\n\n" \
              f"Dabei werden alle Werke verschoben und der Datensatz '{slave_name}' gelöscht."

        if messagebox.askyesno("Merge bestätigen", msg):
            # Aufruf der Bridge, die wiederum den AuthorService nutzt
            self.bridge.execute_merge(master_id, slave_id)

    def show_merge_ui(self, duplicates):
        """Schaltet die rechte Spalte auf den Merge-Dialog um."""
        self.vita_frame.pack_forget()
        self.merge_frame.pack(fill="both", expand=True)

        # Liste leeren
        for item in self.merge_list.get_children():
            self.merge_list.delete(item)

        # Dubletten einfügen
        for d in duplicates:
            self.merge_list.insert("", "end", values=(d['id'], d['name'], d['work_count']))

    def show_vita(self):
        """Schaltet zurück zur normalen Vita-Ansicht."""
        self.merge_frame.pack_forget()
        self.vita_frame.pack(fill="both", expand=True)

    def update_sample_path_display(self, author_id):
        """Aktualisiert das schreibgeschützte Pfad-Feld oben."""
        path = self.bridge.get_sample_path(author_id)

        self.ent_sample_path.config(state="normal")  # Kurz entsperren
        self.ent_sample_path.delete(0, tk.END)
        self.ent_sample_path.insert(0, path)
        self.ent_sample_path.config(state="readonly")  # Wieder sperren

    def _on_browse_all_paths_clicked(self):
        a_id = self.lbl_auth_id.cget("text").replace("ID: ", "")
        if a_id != "-":
            self.bridge.open_path_browser_for_author(a_id)