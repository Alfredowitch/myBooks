"""
DATEI: browser_view.py
PROJEKT: MyBook-Management (v1.6.18)
BESCHREIBUNG:
    - Werk-Beschreibung hinzugefügt (breit, 2-zeilig).
    - Pfad-Feld im Buch-Bereich entfernt.
    - Werk-Felder auf readonly (grau) gesetzt.
    - Navigations-Buttons und Delete-Beschriftung korrigiert.
"""

import os
import tkinter as tk
from tkinter import ttk, scrolledtext
import fitz
from PIL import Image, ImageTk


class BrowserView:
    # ----------------------------------------------------------------------
    # Nötigen Kontroller und Verbindungen
    # ----------------------------------------------------------------------
    def __init__(self, win):
        self.win = win
        self.widgets = {}
        self.tk_img = None
        self.pos_label = None


        self.win.title("MyBook Browser v1.6.18")
        self.win.geometry("1450x950")

        self.colors = {
            'serie': '#e3f2fd', 'work': '#e8f5e9', 'book': '#fffde7',
            'bg': '#f5f5f5', 'nav': '#cfd8dc', 'gray_bg': '#f0f0f0'
        }

        self.font_standard = ("Arial", 11)
        self.font_bold = ("Arial", 11, "bold")
        self.font_title = ("Arial", 13, "bold")

        # --- TOP BAR ---
        self.top_bar = tk.Frame(self.win, bg="#e0e0e0", bd=1, relief="raised")
        self.top_bar.pack(side='top', fill='x')

        self.path_entry = tk.Entry(self.top_bar, fg="blue", bg=self.colors['gray_bg'], relief="flat", font=self.font_standard)
        self.path_entry.pack(side='left', fill='x', expand=True, padx=5, pady=5)

        self.btn_load_db = tk.Button(self.top_bar, text="DB LADEN", bg="#90caf9", font=("Arial", 9, "bold"))
        self.btn_load_db.pack(side='left', padx=2)

        self.btn_load_fs = tk.Button(self.top_bar, text="DATEISYSTEM", bg="#a5d6a7", font=("Arial", 9, "bold"))
        self.btn_load_fs.pack(side='left', padx=2)

        self.btn_report = tk.Button(self.top_bar, text="REPORT", bg="#fff59d", font=("Arial", 9, "bold"))
        self.btn_report.pack(side='left', padx=2)

        # --- HAUPT-CONTAINER ---
        self.main_container = tk.Frame(self.win, bg=self.colors['bg'])
        self.main_container.pack(side='top', fill='both', expand=True, padx=15, pady=10)
        self.main_container.columnconfigure(0, weight=3)
        self.main_container.columnconfigure(1, weight=1)

        self._create_widgets()


    # ----------------------------------------------------------------------
    # GUI als GRID aufbauen für besseres Alignment und Kontrolle
    # ----------------------------------------------------------------------
    def _create_widgets(self):
        left_panel = tk.Frame(self.main_container, bg=self.colors['bg'])
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # --- SERIE ---
        self.f_serie = tk.LabelFrame(left_panel, text=" SERIE ", bg=self.colors['serie'], font=self.font_title, padx=10, pady=10)
        self.f_serie.pack(fill="x", pady=(0, 5))
        self.f_serie.columnconfigure(1, weight=1)
        # 1. Die Combobox für den Seriennamen (Zeile 0)
        tk.Label(self.f_serie, text="Serie:", bg=self.colors['serie'], font=self.font_bold, width=12,
                 anchor="w").grid(row=0, column=0, sticky="w")
        self.widgets['s_name'] = ttk.Combobox(self.f_serie, font=self.font_standard)
        self.widgets['s_name'].grid(row=0, column=1, sticky="ew", padx=5, pady=2)  # Grid-Aufruf hinzugefügt!
        # 2. Die weiteren Felder (müssen in die nächsten Zeilen!)
        self._add_lang_grid(self.f_serie, "s_name", 1)

        # --- WERK ---
        self.f_work = tk.LabelFrame(left_panel, text=" WERK ", bg=self.colors['work'], font=self.font_title, padx=10, pady=10)
        self.f_work.pack(fill="x", pady=5)
        self.f_work.columnconfigure(1, weight=1)
        tk.Label(self.f_work, text="Werk Titel:", bg=self.colors['work'], font=self.font_bold, width=12,
                 anchor="w").grid(row=0, column=0, sticky="w")
        self.widgets['w_title'] = ttk.Combobox(self.f_work, font=self.font_standard)
        self.widgets['w_title'].grid(row=0, column=1, sticky="ew", padx=5, pady=2)  # Grid-Aufruf hinzugefügt!
        self._add_lang_grid(self.f_work, "w_title", 1)

        # Werk Beschreibung (2 Zeilen hoch, volle Breite)
        tk.Label(self.f_work, text="Beschreibung:", bg=self.colors['work'], font=self.font_bold, width=12, anchor="w").grid(row=2, column=0, sticky="nw")
        w_desc = tk.Text(self.f_work, height=2, font=self.font_standard, bg=self.colors['gray_bg'], wrap="word")
        w_desc.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        self.widgets['w_description'] = w_desc

        f_w_row3 = tk.Frame(self.f_work, bg=self.colors['work'])
        f_w_row3.grid(row=3, column=1, sticky="ew", pady=2)
        self._add_mini_field(f_w_row3, "Keywords:", "w_keywords", 0, 0, width=45, readonly=True)
        self._add_mini_field(f_w_row3, "Regions:", "w_regions", 0, 2, width=20, readonly=True)

        f_w_row4 = tk.Frame(self.f_work, bg=self.colors['work'])
        f_w_row4.grid(row=4, column=1, sticky="ew", pady=2)
        self._add_mini_field(f_w_row4, "Genre:", "w_genre", 0, 0, width=30, readonly=True)
        self._add_mini_field(f_w_row4, "Rating:", "w_rating", 0, 2, width=10, readonly=True)
        self._add_mini_field(f_w_row4, "Stars:", "w_stars", 0, 4, width=10, readonly=True)

        # --- BUCH ---
        self.f_book = tk.LabelFrame(left_panel, text=" BUCH-DETAILS (Leading) ", bg=self.colors['book'], font=self.font_title, padx=10, pady=10)
        self.f_book.pack(fill="x", pady=5)
        self.f_book.columnconfigure(1, weight=1)

        # Pfad-Display entfernt (ist ja oben in Top-Bar)
        self._add_field_row(self.f_book, "Buchtitel:", "b_title", 0)
        self._add_field_row(self.f_book, "Autoren:", "authors_raw", 1)

        f_b_row2 = tk.Frame(self.f_book, bg=self.colors['book'])
        f_b_row2.grid(row=2, column=1, sticky="ew", pady=2)
        self._add_mini_field(f_b_row2, "Serie:", "b_series_name", 0, 0, width=40)
        self._add_mini_field(f_b_row2, "Nr:", "b_series_number", 0, 2, width=5)
        self._add_mini_field(f_b_row2, "Sprache:", "b_language", 0, 4, width=10)
        self._add_mini_field(f_b_row2, "Jahr:", "b_year", 0, 6, width=8)

        f_b_row3 = tk.Frame(self.f_book, bg=self.colors['book'])
        f_b_row3.grid(row=3, column=1, sticky="ew", pady=2)
        self._add_mini_field(f_b_row3, "Keywords:", "b_keywords", 0, 0, width=50)
        self._add_mini_field(f_b_row3, "Regions:", "b_regions", 0, 2, width=20)

        f_b_row4 = tk.Frame(self.f_book, bg=self.colors['book'])
        f_b_row4.grid(row=4, column=1, sticky="ew", pady=2)
        self._add_mini_field(f_b_row4, "Genre:", "b_genre", 0, 0, width=40)
        self._add_mini_field(f_b_row4, "ISBN:", "b_isbn", 0, 2, width=25)

        f_b_row5 = tk.Frame(self.f_book, bg=self.colors['book'])
        f_b_row5.grid(row=5, column=1, sticky="ew", pady=2)
        self._add_mini_field(f_b_row5, "Rating OL:", "b_rating_ol", 0, 0, width=6)
        self._add_mini_field(f_b_row5, "Count:", "b_rating_ol_count", 0, 2, width=6)
        self._add_mini_field(f_b_row5, "Rating G:", "b_rating_g", 0, 4, width=6)
        self._add_mini_field(f_b_row5, "Count:", "b_rating_g_count", 0, 6, width=6)
        self._add_mini_field(f_b_row5, "Stars:", "b_stars", 0, 8, width=6)

        # --- COVER ---
        self.cover_frame = tk.Frame(self.main_container, width=350, height=470, relief="ridge", bd=2)
        self.cover_frame.grid(row=0, column=1, sticky="ne")
        self.cover_frame.pack_propagate(False)
        self.cover_label = tk.Label(self.cover_frame, bg="#ddd")
        self.cover_label.pack(fill="both", expand=True)

        # --- NAVIGATION ---
        self.nav_frame = tk.Frame(self.main_container, bg=self.colors['nav'], bd=2, relief="raised")
        self.nav_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=10)
        self.btn_container = tk.Frame(self.nav_frame, bg=self.colors['nav'])
        self.btn_container.pack(expand=True, fill='y', pady=5)
        self._setup_nav_widgets()

        # --- TEXTFELDER ---
        self.text_panel = tk.Frame(self.main_container, bg=self.colors['bg'])
        self.text_panel.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.text_panel.columnconfigure(0, weight=1); self.text_panel.columnconfigure(1, weight=1)

        for i, (name, key) in enumerate([("Buch Beschreibung:", "b_description"), ("Notizen:", "b_notes")]):
            f = tk.Frame(self.text_panel, bg=self.colors['book'], bd=1, relief="sunken")
            f.grid(row=0, column=i, sticky="nsew", padx=5)
            tk.Label(f, text=name, bg=self.colors['book'], font=self.font_bold).pack(anchor="w", padx=5)
            self.widgets[key] = scrolledtext.ScrolledText(f, height=12, font=self.font_standard, wrap="word")
            self.widgets[key].pack(fill="both", expand=True, padx=5, pady=5)

    # ----------------------------------------------------------------------
    # GUI FUNKTIONALE ELEMENTE
    # ----------------------------------------------------------------------
    def _setup_nav_widgets(self):
        btn_cfg = {'font': self.font_bold, 'width': 6}
        self.btn_first = tk.Button(self.btn_container, text="|<", **btn_cfg)
        self.btn_first.pack(side='left', padx=5)
        self.btn_prev = tk.Button(self.btn_container, text="<", **btn_cfg)
        self.btn_prev.pack(side='left', padx=5)
        self.pos_label = tk.Label(self.btn_container, text="0 von 0", font=self.font_title, bg=self.colors['nav'], width=15)
        self.pos_label.pack(side='left', padx=20)
        self.btn_next = tk.Button(self.btn_container, text=">", **btn_cfg)
        self.btn_next.pack(side='left', padx=5)
        self.btn_last = tk.Button(self.btn_container, text=">|", **btn_cfg)
        self.btn_last.pack(side='left', padx=5)
        tk.Frame(self.btn_container, width=40, bg=self.colors['nav']).pack(side='left')
        self.btn_save = tk.Button(self.btn_container, text="SPEICHERN", bg="#4caf50", fg="white", font=self.font_bold, width=20)
        self.btn_save.pack(side='left', padx=10)
        self.btn_delete = tk.Button(self.btn_container, text="LÖSCHEN in DB", bg="#f44336", fg="white", font=self.font_bold, width=15)
        self.btn_delete.pack(side='left', padx=5)

    # ----------------------------------------------------------------------
    # GUI FUNKTIONALE VERKNÜPFUNG MIT DEM BROWSER
    # Im Browser wird die Funktion mit self.view.create_nav_buttons(self) aufgerufen.
    # Dammit kennen die Buttons den Browser = Controller.
    # Im Browser ist auch die Funktionalität mit Navigationsliste verankert.
    # Durch das config wird das Steuerelement im View mit der Funktion im Browser verknüpft.
    # Man nennt dieses Prinzip Dependency Injection (Abhängigkeitsinjektion).
    # ----------------------------------------------------------------------
    def create_nav_buttons(self, controller):
        # Verbindung der Steuerelemente mit dem Controller
        self.btn_first.config(command=controller.nav_first)
        self.btn_prev.config(command=controller.nav_prev)
        self.btn_next.config(command=controller.nav_next)
        self.btn_last.config(command=controller.nav_last)
        self.btn_save.config(command=controller.save_data)
        # hier werden die Buttons im TOP mit dem Controller verbunden.
        self.btn_delete.config(command=controller.delete_current_book)
        # f() ruft eine Funktion auf
        # f gibt einfach die Adresse der Funktion zurück für später
        # command = controller.delete_current_book wird erst beim Click ausgeführt.
        # command = self.show_search_popup(controller...) würde sofort beim Erzeugen der Buttons ausgeführt.
        # daher lambda zur Verzögerung der Ausführung.
        # das Argument, der controller-Befehl wird als Callback-Funktion weitergereicht.
        self.btn_load_db.config(command=lambda: self.show_search_popup(controller.load_from_database))
        self.btn_load_fs.config(command=controller.load_from_file)
        self.btn_report.config(command=controller.load_from_report_file)
    # Hier wird das Argument (callback) weitergereicht und ganz unten ausgeführt mit callback(a,t)
    def show_search_popup(self, callback):
        top = tk.Toplevel(self.win)
        top.title("Datenbank Suche")
        top.geometry("400x200")
        tk.Label(top, text="Autor:", font=self.font_bold).pack(pady=(10, 0))
        ent_author = tk.Entry(top, font=self.font_standard, width=35)
        ent_author.pack(pady=5); ent_author.focus_set()
        tk.Label(top, text="Titel:", font=self.font_bold).pack(pady=(5, 0))
        ent_title = tk.Entry(top, font=self.font_standard, width=35)
        ent_title.pack(pady=5)
        def do_search():
            a, t = ent_author.get().strip(), ent_title.get().strip()
            if a or t: top.destroy(); callback(a, t)
        btn = tk.Button(top, text="Suchen", command=do_search, bg="#90caf9", width=15)
        btn.pack(pady=15); top.bind('<Return>', lambda e: do_search())

    # ----------------------------------------------------------------------
    # GUI FÜLLEN HILFSFUNKTIONEN
    # ----------------------------------------------------------------------
    def _add_field_row(self, parent, label, key, row, readonly=False):
        tk.Label(parent, text=label, bg=parent.cget("bg"), font=self.font_bold, width=12, anchor="w").grid(row=row, column=0, sticky="w")
        bg_color = self.colors['gray_bg'] if readonly else "white"
        w = tk.Entry(parent, font=self.font_standard, bg=bg_color)
        w.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
        self.widgets[key] = w

    def _add_mini_field(self, parent, label, key, row, col, width, readonly=False):
        tk.Label(parent, text=label, bg=parent.cget("bg"), font=self.font_bold, padx=5).grid(row=row, column=col, sticky="w")
        bg_color = self.colors['gray_bg'] if readonly else "white"
        w = tk.Entry(parent, width=width, font=self.font_standard, bg=bg_color)
        w.grid(row=row, column=col+1, sticky="w", padx=2)
        self.widgets[key] = w

    def _add_lang_grid(self, parent, key_prefix, row, readonly=False):
        f = tk.Frame(parent, bg=parent.cget("bg"))
        f.grid(row=row, column=1, sticky="ew", pady=2)
        bg_color = self.colors['gray_bg'] if readonly else "white"
        for i in range(5): f.columnconfigure(i*2+1, weight=1)
        for i, l in enumerate(['de', 'en', 'fr', 'es', 'it']):
            tk.Label(f, text=f"{l.upper()}:", bg=parent.cget("bg"), font=("Arial", 9)).grid(row=0, column=i*2, padx=(5,0))
            w = tk.Entry(f, font=self.font_standard, bg=bg_color)
            w.grid(row=0, column=i*2+1, sticky="ew", padx=2)
            self.widgets[f"{key_prefix}_{l}"] = w

    def _set_val(self, key, val):
        if key in self.widgets:
            w = self.widgets[key]
            is_readonly = w.cget('bg') == self.colors['gray_bg']

            # --- NEU: Spezialbehandlung für Sets/Listen ---
            if isinstance(val, (set, list)):
                display_val = ", ".join(sorted([str(v) for v in val if v]))
            else:
                display_val = str(val) if val is not None else ""

            if isinstance(w, (tk.Text, scrolledtext.ScrolledText)):
                w.config(state='normal')
                w.delete('1.0', tk.END); w.insert('1.0', display_val)
                if is_readonly: w.config(state='disabled')
            else:
                w.config(state='normal')
                w.delete(0, tk.END); w.insert(0, display_val)
                if is_readonly: w.config(state='readonly')

    def fill_widgets(self, data):
        """Mappt BookData-Aggregat sicher auf die UI."""
        if not data: return

        # 1. Pfad-Anzeige (Oben)
        self.path_entry.config(state='normal')
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, data.path if hasattr(data, 'path') else "")
        self.path_entry.config(state='readonly')

        # 2. SERIE
        if hasattr(data, 'serie') and data.serie:
            s = data.serie
            for l in ['de', 'en', 'fr', 'es', 'it']:
                self._set_val(f's_name_{l}', getattr(s, f'name_{l}', ""))
            # Serie Combobox befüllen
            if hasattr(data, 'all_available_series'):
                self.widgets['s_name']['values'] = data.all_available_series
            self.widgets['s_name'].set(s.name if s.name else "")

        # 3. WERK (Leading Object ist Buch -> Werk Felder sind Readonly)
        if hasattr(data, 'work') and data.work:
            w = data.work
            self._set_val('w_description', getattr(w, 'description', ""))
            self._set_val('w_genre', getattr(w, 'genre', ""))
            self._set_val('w_rating', getattr(w, 'rating', ""))
            self._set_val('w_stars', getattr(w, 'stars', ""))
            self._set_val('w_keywords', getattr(w, 'keywords', ""))
            self._set_val('w_regions', getattr(w, 'regions', ""))
            for l in ['de', 'en', 'fr', 'es', 'it']:
                self._set_val(f'w_title_{l}', getattr(w, f'title_{l}', ""))
            # Werk ComboBox befüllen
            if hasattr(data, 'all_available_works'):
                self.widgets['w_title']['values'] = data.all_available_works
            self.widgets['w_title'].set(w.title if w.title else "")
            # Wir aktualisieren den Titel des Frames, um die Anzahl anzuzeigen
            b_count = getattr(w, 'book_count', 0)
            self.f_work.config(text=f" WERK (ID: {w.id if w.id else 'NEW'}, {b_count} Bücher verknüpft) ")

        # 4. BUCH-DETAILS
        if hasattr(data, 'book') and data.book:
            b = data.book
            self._set_val('b_title', getattr(b, 'title', ""))
            self._set_val('b_series_name', getattr(b, 'series_name', ""))
            self._set_val('b_series_number', getattr(b, 'series_number', ""))
            self._set_val('b_isbn', getattr(b, 'isbn', ""))
            self._set_val('b_genre', getattr(b, 'genre', ""))
            self._set_val('b_regions', getattr(b, 'regions', ""))
            self._set_val('b_language', getattr(b, 'language', ""))
            self._set_val('b_keywords', getattr(b, 'keywords', ""))
            self._set_val('b_year', getattr(b, 'year', ""))
            self._set_val('b_rating_ol', getattr(b, 'rating_ol', ""))
            self._set_val('b_rating_ol_count', getattr(b, 'rating_ol_count', ""))
            self._set_val('b_rating_g', getattr(b, 'rating_g', ""))
            self._set_val('b_rating_g_count', getattr(b, 'rating_g_count', ""))
            self._set_val('b_stars', getattr(b, 'stars', ""))
            self._set_val('b_description', getattr(b, 'description', ""))
            self._set_val('b_notes', getattr(b, 'notes', ""))

            # 5. AUTOREN (Anzeige aus data.book.authors)
            if hasattr(b, 'authors') and b.authors:
                names = []
                for a in b.authors:
                    if isinstance(a, (list, tuple)) and len(a) >= 2:
                        names.append(f"{a[0]} {a[1]}".strip())
                    else:
                        names.append(str(a))
                self._set_val('authors_raw', " & ".join(names))
            else:
                self._set_val('authors_raw', "")

    def display_cover(self, image_path, current_file_path):
        import io
        self.cover_label.config(image='', text='')
        self.tk_img = None
        try:
            img = None
            if image_path and os.path.exists(image_path) and not image_path.lower().endswith(('.pdf', '.epub')):
                img = Image.open(image_path)
            elif current_file_path and os.path.exists(current_file_path):
                doc = fitz.open(current_file_path)
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                doc.close()
            if img:
                img.thumbnail((320, 500), Image.Resampling.LANCZOS)
                self.tk_img = ImageTk.PhotoImage(img)
                self.cover_label.config(image=self.tk_img)
        except: self.cover_label.config(text="X")

    def update_status(self, current, total, path, is_magic=False):
        if self.pos_label: self.pos_label.config(text=f"{current} von {total}")
        self.win.title(f"MyBook Browser - {os.path.basename(path)}")
        self.path_entry.config(state='normal')
        self.path_entry.delete(0, tk.END); self.path_entry.insert(0, path)
        self.path_entry.config(state='readonly', bg="#fffde7" if is_magic else self.colors['gray_bg'])

    # ----------------------------------------------------------------------
    # GUI ELEMENTE AUSLESEN und Rückgabe eines BookData Objekts.
    # ----------------------------------------------------------------------
    def get_data_from_widgets(self, data):
        """
        Liest alle Werte aus den GUI-Widgets aus und schreibt sie
        direkt in die Atome des BookData-Aggregats.
        """
        if not data:
            return None

        # --- 1. SERIE ---
        if hasattr(data, 'serie') and data.serie:
            s = data.serie
            s.name = self.widgets['s_name'].get().strip()
            for l in ['de', 'en', 'fr', 'es', 'it']:
                setattr(s, f'name_{l}', self.widgets[f's_name_{l}'].get().strip())

        # --- 2. WERK ---
        # Hinweis: Da Werk-Felder im UI 'readonly' (grau) sind,
        # übernehmen wir hier nur Daten, falls sie dennoch editierbar sind
        # oder wir die Master-Beschreibung synchronisieren wollen.
        if hasattr(data, 'work') and data.work:
            w = data.work
            w.title = self.widgets['w_title'].get().strip()
            for l in ['de', 'en', 'fr', 'es', 'it']:
                setattr(w, f'title_{l}', self.widgets[f'w_title_{l}'].get().strip())
            # Falls die Werk-Beschreibung Leading ist oder synchronisiert wird:
            w.description = self.widgets['w_description'].get('1.0', tk.END).strip()
            # Andere Felder sind im Browser meist Readonly, aber hier der Vollständigkeit halber:
            w.keywords = self.widgets['w_keywords'].get().strip()
            w.regions = self.widgets['w_regions'].get().strip()
            w.genre = self.widgets['w_genre'].get().strip()

        # --- 3. BUCH (Leading Object) ---
        if hasattr(data, 'book') and data.book:
            b = data.book
            b.title = self.widgets['b_title'].get().strip()
            b.series_name = self.widgets['b_series_name'].get().strip()
            b.series_number = self.widgets['b_series_number'].get().strip()
            b.isbn = self.widgets['b_isbn'].get().strip()
            b.genre = self.widgets['b_genre'].get().strip()
            b.regions = self.widgets['b_regions'].get().strip()
            b.language = self.widgets['b_language'].get().strip()
            b.keywords = self.widgets['b_keywords'].get().strip()
            b.year = self.widgets['b_year'].get().strip()
            # Beschreibungen und Notizen
            b.description = self.widgets['b_description'].get('1.0', tk.END).strip()
            b.notes = self.widgets['b_notes'].get('1.0', tk.END).strip()
            # Numerische Werte (Ratings & Stars)
            try:
                b.stars = int(self.widgets['b_stars'].get() or 0)
                b.rating_ol = float(self.widgets['b_rating_ol'].get() or 0.0)
                b.rating_ol_count = int(self.widgets['b_rating_ol_count'].get() or 0)
                b.rating_g = float(self.widgets['b_rating_g'].get() or 0.0)
                b.rating_g_count = int(self.widgets['b_rating_g_count'].get() or 0)
            except ValueError:
                pass  # Fehlerhafte numerische Eingaben ignorieren wir hier (oder Log-Ausgabe)

            # --- 4. AUTOREN ---
            if 'authors_raw' in self.widgets:
                raw_authors = self.widgets['authors_raw'].get().strip()
                if raw_authors:
                    # Zerlegt "Vorname Nachname & Vorname Nachname" in [(Vorname, Nachname), ...]
                    new_authors = []
                    parts = [p.strip() for p in raw_authors.split('&')]
                    for p in parts:
                        name_parts = p.split(maxsplit=1)
                        if len(name_parts) == 2:
                            new_authors.append((name_parts[0], name_parts[1]))
                        else:
                            new_authors.append(("", name_parts[0]))
                    b.authors = new_authors

        return data

    def set_navigation_item_color(self, color):
        """
        Visualisiert den Status (Dirty/New/Sync) durch Einfärben der Navigations-Bar.
        Da wir keine Liste haben, nutzen wir das Label und den Container als Indikator.
        """
        try:
            # 1. Die Positionsanzeige einfärben
            if self.pos_label:
                self.pos_label.config(bg=color)

            # 2. Den gesamten Navigations-Frame leicht einfärben (optional für mehr Sichtbarkeit)
            if self.nav_frame:
                self.nav_frame.config(bg=color)
                self.btn_container.config(bg=color)

        except Exception as e:
            print(f"⚠️ Fehler beim Setzen der Status-Farbe: {e}")