"""
DATEI: browser_view.py
PROJEKT: MyBook-Management (v1.4.2)
BESCHREIBUNG: Optimiertes Layout ohne Haupt-Scrollbar. Fixierte Navigation unten.
              Buch-Zone über volle Breite mit Textfeldern rechts.
"""

import os
import tkinter as tk
from tkinter import ttk, scrolledtext
import fitz  # PyMuPDF
from PIL import Image, ImageTk


class BrowserView:
    def __init__(self, win):
        self.win = win
        self.widgets = {}
        self.tk_img = None
        self.pos_label = None

        self.win.title("MyBook Browser v1.4.2")
        self.win.geometry("1300x900")

        self.colors = {
            'serie': '#e3f2fd',  # Blau
            'work': '#e8f5e9',  # Grün
            'book': '#fffde7',  # Gelb
            'bg': '#f5f5f5'
        }

        # Haupt-Container (kein Scrollen des Gesamtfensters mehr)
        self.main_container = tk.Frame(self.win, bg=self.colors['bg'])
        self.main_container.pack(fill="both", expand=True)

        # 1. Pfad-Feld ganz oben
        self.path_entry = tk.Entry(self.main_container, fg="blue", bg="#f0f0f0", relief="flat", font=("Arial", 9))
        self.path_entry.pack(fill='x', pady=(0, 5))

        # 2. Fixierte Navigationsleiste ganz unten
        self.nav_frame = tk.Frame(self.win, bg="#cfd8dc", height=50, bd=1, relief="raised")
        self.nav_frame.pack(side='bottom', fill='x')

        # 3. Mittlerer Bereich für Daten
        self.content_scroll_frame = tk.Frame(self.main_container, bg=self.colors['bg'])
        self.content_scroll_frame.pack(fill="both", expand=True, padx=10)

        self._create_widgets()

    def _add_field(self, parent, label, key, width=20, is_combo=False):
        frame = tk.Frame(parent, bg=parent.cget("bg"))
        frame.pack(side="left", padx=5, pady=2)
        tk.Label(frame, text=label, bg=parent.cget("bg"), font=("Arial", 8, "bold")).pack(side="top", anchor="w")
        if is_combo:
            w = ttk.Combobox(frame, width=width)
        else:
            w = tk.Entry(frame, width=width)
        w.pack(side="top")
        self.widgets[key] = w
        return w

    def _build_small_field(self, parent, label_text, key, width=15):
        f = tk.Frame(parent, bg=parent.cget("bg"))
        f.pack(side="left", padx=2)
        tk.Label(f, text=label_text, bg=parent.cget("bg"), font=("Arial", 7)).pack(side="left")
        ent = tk.Entry(f, width=width)
        ent.pack(side="left", padx=2)
        self.widgets[key] = ent
        return ent

    def _create_widgets(self):
        # OBERER BEREICH: Serie & Werk (Links) + Cover (Rechts)
        top_row = tk.Frame(self.content_scroll_frame, bg=self.colors['bg'])
        top_row.pack(fill='x')

        upper_left = tk.Frame(top_row, bg=self.colors['bg'])
        upper_left.pack(side='left', fill='both', expand=True)

        # --- ZONE BLAU: SERIE ---
        self.f_serie = tk.LabelFrame(upper_left, text=" SERIE ", bg=self.colors['serie'], font=("Arial", 10, "bold"))
        self.f_serie.pack(fill='x', pady=2, padx=5)

        row_s1 = tk.Frame(self.f_serie, bg=self.colors['serie'])
        row_s1.pack(fill="x")
        self._add_field(row_s1, "Master Name:", "s_name", width=40, is_combo=True)
        self._add_field(row_s1, "Slug:", "s_slug", width=25)

        lang_s = tk.Frame(self.f_serie, bg=self.colors['serie'])
        lang_s.pack(fill="x", pady=2)
        for lang in ['de', 'en', 'fr', 'es', 'it']:
            self._build_small_field(lang_s, f"{lang.upper()}:", f"s_name_{lang}", width=12)

        # --- ZONE GRÜN: WERK ---
        self.f_work = tk.LabelFrame(upper_left, text=" WERK ", bg=self.colors['work'], font=("Arial", 10, "bold"))
        self.f_work.pack(fill='x', pady=2, padx=5)

        row_w1 = tk.Frame(self.f_work, bg=self.colors['work'])
        row_w1.pack(fill="x")
        self._add_field(row_w1, "Haupt-Titel:", "w_title", width=40, is_combo=True)
        self._add_field(row_w1, "Genre:", "w_genre", width=15)

        lang_w = tk.Frame(self.f_work, bg=self.colors['work'])
        lang_w.pack(fill="x", pady=2)
        for lang in ['de', 'en', 'fr', 'es', 'it']:
            self._build_small_field(lang_w, f"{lang.upper()}:", f"w_title_{lang}", width=12)

        # COVER RECHTS NEBEN SERIE/WERK
        self.cover_label = tk.Label(top_row, text="Coverbild", relief="ridge", width=35, height=18)
        self.cover_label.pack(side='right', anchor='n', padx=10, pady=5)

        # --- ZONE GELB: BUCH (VOLLE BREITE) ---
        self.f_book = tk.LabelFrame(self.content_scroll_frame, text=" BUCH (Korrektur-Zone) ", bg=self.colors['book'],
                                    font=("Arial", 10, "bold"))
        self.f_book.pack(fill='both', expand=True, pady=5, padx=5)

        # Buch-Split: Links Felder, Rechts Beschreibungen
        book_split = tk.Frame(self.f_book, bg=self.colors['book'])
        book_split.pack(fill='both', expand=True)

        book_left = tk.Frame(book_split, bg=self.colors['book'])
        book_left.pack(side='left', fill='y')

        self._add_field(book_left, "Autoren:", "authors_raw", width=60).pack(fill='x')

        row_b1 = tk.Frame(book_left, bg=self.colors['book'])
        row_b1.pack(fill="x")
        self._add_field(row_b1, "Buch-Titel:", "b_title", width=40)
        self._add_field(row_b1, "Band:", "b_series_number", width=8)

        row_b2 = tk.Frame(book_left, bg=self.colors['book'])
        row_b2.pack(fill="x")
        self._add_field(row_b2, "ISBN:", "b_isbn", width=20)
        self._add_field(row_b2, "Jahr:", "b_year", width=8)
        self._add_field(row_b2, "Sprache:", "b_language", width=8)

        # Buch-Rechts: Textfelder
        book_right = tk.Frame(book_split, bg=self.colors['book'])
        book_right.pack(side='left', fill='both', expand=True, padx=10)

        tk.Label(book_right, text="Beschreibung (Buch):", bg=self.colors['book'], font=("Arial", 8, "bold")).pack(
            anchor="w")
        self.widgets['b_description'] = scrolledtext.ScrolledText(book_right, height=8, font=("Arial", 9))
        self.widgets['b_description'].pack(fill="x", pady=(0, 5))

        tk.Label(book_right, text="Notizen:", bg=self.colors['book'], font=("Arial", 8, "bold")).pack(anchor="w")
        self.widgets['b_notes'] = scrolledtext.ScrolledText(book_right, height=4, font=("Arial", 9))
        self.widgets['b_notes'].pack(fill="x")

    def create_nav_buttons(self, controller):
        for w in self.nav_frame.winfo_children(): w.destroy()

        btn_f = tk.Frame(self.nav_frame, bg="#cfd8dc")
        btn_f.pack(expand=True)

        tk.Button(btn_f, text="|<", command=controller.nav_first, width=5).pack(side='left', padx=2)
        tk.Button(btn_f, text="<", command=controller.nav_prev, width=5).pack(side='left', padx=2)

        self.pos_label = tk.Label(btn_f, text="0 von 0", font=("Arial", 10, "bold"), bg="#cfd8dc")
        self.pos_label.pack(side='left', padx=20)

        tk.Button(btn_f, text=">", command=controller.nav_next, width=5).pack(side='left', padx=2)
        tk.Button(btn_f, text=">|", command=controller.nav_last, width=5).pack(side='left', padx=2)

        tk.Button(btn_f, text="SPEICHERN", bg="#4caf50", fg="white", font=("Arial", 10, "bold"),
                  command=controller.save_data, width=20).pack(side='left', padx=40)
        tk.Button(btn_f, text="Löschen", fg="red", command=controller.delete_current_book).pack(side='left')

    def _set_val(self, key, val):
        if key in self.widgets:
            w = self.widgets[key]
            if isinstance(w, (tk.Text, scrolledtext.ScrolledText)):
                w.delete('1.0', tk.END)
                w.insert('1.0', str(val) if val else "")
            else:
                w.delete(0, tk.END)
                w.insert(0, str(val) if val is not None else "")

    def fill_widgets(self, data):
        self.path_entry.config(state='normal')
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, data.book.path if hasattr(data, 'book') else "")
        self.path_entry.config(state='readonly')

        if hasattr(data, 'serie'):
            self._set_val('s_name', data.serie.name)
            for l in ['de', 'en', 'fr', 'es', 'it']: self._set_val(f's_name_{l}', getattr(data.serie, f'name_{l}', ""))
            self._set_val('s_slug', data.serie.slug)

        if hasattr(data, 'work'):
            self._set_val('w_title', data.work.title)
            for l in ['de', 'en', 'fr', 'es', 'it']: self._set_val(f'w_title_{l}', getattr(data.work, f'title_{l}', ""))
            self._set_val('w_genre', data.work.genre)

        if hasattr(data, 'authors'):
            self._set_val('authors_raw', " & ".join([f"{fn} {ln}".strip() for fn, ln in data.authors]))

        if hasattr(data, 'book'):
            b = data.book
            self._set_val('b_title', b.title)
            self._set_val('b_series_number', b.series_number)
            self._set_val('b_year', b.year)
            self._set_val('b_isbn', b.isbn)
            self._set_val('b_language', b.language)
            self._set_val('b_description', b.description)
            self._set_val('b_notes', b.notes)

    def display_cover(self, image_path, current_file_path):
        import io
        self.cover_label.config(image='', text='Lädt...')
        self.tk_img = None
        max_size = (310, 420)
        try:
            if image_path and os.path.exists(image_path) and not image_path.lower().endswith(('.pdf', '.epub')):
                img = Image.open(image_path)
            elif current_file_path and os.path.exists(current_file_path):
                doc = fitz.open(current_file_path)
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                doc.close()

            if img:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                self.tk_img = ImageTk.PhotoImage(img)
                self.cover_label.config(image=self.tk_img, text='')
        except:
            self.cover_label.config(text="Kein Cover")

    def update_status(self, current, total, path, is_magic=False):
        if self.pos_label: self.pos_label.config(text=f"{current} von {total}")
        self.win.title(f"MyBook Browser - {os.path.basename(path)}")