"""
DATEI: browser_view.py
PROJEKT: MyBook-Management (v1.2.0)
BESCHREIBUNG: Kümmert sich um die Darstellung in der Book_Browser App mit tkinter.
              book_browser.py	=	Der Controller: Steuert den Flow (Laden -> Navigieren -> Speichern).
              browser_view.py	=	Die Maske: Zeichnet alles und fängt Benutzereingaben ab.
              browser_model.py	=	Das Gehirn: Muss die Methoden aggregate_book_data und save_book enthalten.
"""
import io
import os
import tkinter as tk
import fitz  # PyMuPDF
from PIL import Image, ImageTk


class BrowserView:
    def __init__(self, win):
        self.win = win
        self.widgets = {}
        self.vars = {}
        self.tk_img = None  # Wichtig für die Bildreferenz

        # Grundkonfiguration des Fensters
        self.win.title("E-Book Browser")
        self.win.geometry("1000x950")

        self._create_main_layout()

    # ----------------------------------------------------------------------
    # 0. Create Form
    # ----------------------------------------------------------------------
    def _create_main_layout(self):
        """Erstellt das Grundgerüst der Widgets."""
        self.main_frame = tk.Frame(self.win, padx=10, pady=10)
        self.main_frame.pack(fill='both', expand=True)
        self.main_frame.rowconfigure(1, weight=1)
        self.main_frame.rowconfigure(2, weight=1)  # Klappentext wächst mit
        self.main_frame.rowconfigure(3, weight=1)  # Notizen wachsen mit
        self.main_frame.columnconfigure(1, weight=1)

        # Das Pfad-Feld (oben)
        self.path_entry = tk.Entry(self.main_frame, fg="blue", bg="#f0f0f0",
                                   relief="flat", font=("Arial", 9))
        self.path_entry.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky="ew")
        self.path_entry.insert(0, "Bereit...")
        self.path_entry.config(state='readonly')

        # Detail-Bereich
        detail_frame = tk.Frame(self.main_frame)
        detail_frame.grid(row=1, column=0, sticky="nsew", columnspan=2)
        detail_frame.columnconfigure(0, weight=1)

        # Links: Textfelder
        fields_frame = tk.Frame(detail_frame)
        fields_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        fields_frame.columnconfigure(1, weight=1)

        # Rechts: Cover
        self.cover_label = tk.Label(detail_frame, text="Coverbild", relief=tk.RIDGE,
                                    width=40, height=20)
        self.cover_label.grid(row=0, column=1, sticky="ne")

        # Definition der Felder
        fields = [
            ('Autoren', 'authors_raw', 'entry'),
            ('Titel', 'title', 'entry'),
            ('Dateiendung', 'extension', 'entry'),
            ('Serienname', 'series_name', 'entry'),
            ('Seriennr.', 'series_number', 'entry'),
            ('Genre', 'genre', 'entry'),
            ('Regionen', 'regions', 'entry'),
            ('Sprache', 'language', 'entry'),
            ('Jahr', 'year', 'entry'),
            ('ISBN', 'isbn', 'entry'),
            ('Schlüsselwörter', 'keywords', 'entry'),
            ('Durchschn. Rating', 'average_rating', 'entry'),
            ('Anzahl Ratings', 'ratings_count', 'entry'),
            ('Meine Sterne', 'stars', 'entry'),
            ('Gelesen', 'is_read', 'check')
        ]

        for i, (label_text, key, type_) in enumerate(fields):
            tk.Label(fields_frame, text=f"{label_text}:", anchor="w").grid(row=i, column=0, sticky="w", pady=3, padx=5)

            if type_ == 'check':
                self.vars[key + '_var'] = tk.BooleanVar(value=False)
                widget = tk.Checkbutton(fields_frame, variable=self.vars[key + '_var'])
                widget.grid(row=i, column=1, sticky="w", pady=3, padx=5)
            else:
                widget = tk.Entry(fields_frame, width=60)
                widget.grid(row=i, column=1, sticky="ew", pady=3, padx=5)

            self.widgets[key] = widget

        # Mehrzeilige Felder
        tk.Label(self.main_frame, text="Klappentext:", anchor="nw").grid(row=2, column=0, sticky="nw", pady=5, padx=5)
        self.widgets['description_raw'] = tk.Text(self.main_frame, height=15, width=80, wrap="word", font=("Arial", 10))
        self.widgets['description_raw'].grid(row=2, column=1, sticky="ew", pady=5, padx=(50, 5))

        tk.Label(self.main_frame, text="Notizen:", anchor="nw").grid(row=3, column=0, sticky="nw", pady=5, padx=5)
        self.widgets['notes'] = tk.Text(self.main_frame, height=10, width=80, wrap="word", font=("Arial", 10))
        self.widgets['notes'].grid(row=3, column=1, sticky="ew", pady=5, padx=(50, 5))

    def create_nav_buttons(self, controller):
        """Erstellt die Buttons und verknüpft sie mit den Methoden des Controllers."""
        nav_container = tk.Frame(self.main_frame)
        nav_container.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        tk.Button(nav_container, text="|<", width=3, command=controller.nav_first).pack(side="left", padx=2)
        tk.Button(nav_container, text="<", width=3, command=controller.nav_prev).pack(side="left", padx=2)

        self.pos_label = tk.Label(nav_container, text="0 von 0", font=("Arial", 9, "bold"), padx=10)
        self.pos_label.pack(side="left")

        tk.Button(nav_container, text=">", width=3, command=controller.nav_next).pack(side="left", padx=2)
        tk.Button(nav_container, text=">|", width=3, command=controller.nav_last).pack(side="left", padx=2)

        tk.Button(nav_container, text="Speichern", bg="#e1f5fe", command=controller.save_data).pack(side="left",
                                                                                                    padx=(20, 0))
        tk.Button(nav_container, text="🗑", fg="red", command=controller.delete_current_book, relief="flat").pack(
            side="left", padx=(10, 0))
        tk.Button(nav_container, text="Beenden", width=10, command=controller.on_close).pack(side="right", padx=5)

    # ----------------------------------------------------------------------
    # 1. Display Coverbild
    # ----------------------------------------------------------------------
    def display_cover(self, image_path, current_file_path):
        """Lädt Bilddatei oder extrahiert Cover aus PDF/EPUB via fitz."""
        self.cover_label.config(image='', text='Lädt...')
        self.tk_img = None
        max_size = (310, 420)

        try:
            # Pfad-Normalisierung für Windows
            if current_file_path:
                current_file_path = os.path.abspath(os.path.normpath(current_file_path))

            # Fall A: Existierendes Bild (JPG/PNG)
            if image_path and os.path.exists(image_path) and not image_path.lower().endswith('.pdf'):
                img = Image.open(image_path)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                self.tk_img = ImageTk.PhotoImage(img)

            # Fall B: Extraktion aus Buchdatei (PDF oder EPUB)
            elif current_file_path and os.path.exists(current_file_path):
                ext = current_file_path.lower()
                if ext.endswith('.pdf') or ext.endswith('.epub') or ext.endswith('.mobi'):
                    doc = fitz.open(current_file_path)
                    # Erste Seite laden (bei EPUBs oft das Cover)
                    page = doc.load_page(0)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                    img_data = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_data))
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    self.tk_img = ImageTk.PhotoImage(img)
                    doc.close()

            if self.tk_img:
                # WICHTIG: width=0, height=0 damit das Bild die Größe bestimmt
                self.cover_label.config(image=self.tk_img, text='', width=0, height=0)
                self.cover_label.image = self.tk_img
            else:
                self.cover_label.config(text="Kein Cover verfügbar", width=40, height=20)

        except Exception as e:
            print(f"❌ Cover-Fehler für {os.path.basename(current_file_path) if current_file_path else '???'}: {e}")
            self.cover_label.config(text="Fehler beim Laden", width=40, height=20)

    # ----------------------------------------------------------------------
    # 2. Füller der Form
    # ----------------------------------------------------------------------
    def fill_widgets(self, data):
        """Füllt die Maske mit Daten aus einem BookData-Objekt."""
        # 1. Grund-Mapping erstellen
        mapping = {
            'title': data.title,
            'series_name': data.series_name,
            'series_number': data.series_number,
            'genre': data.genre,
            'language': data.language,
            'year': data.year,
            'isbn': data.isbn,
            'average_rating': data.average_rating,
            'ratings_count': data.ratings_count,
            'stars': data.stars
        }

        # 2. Extension-Logik (Robustes Befüllen)
        ext = getattr(data, 'extension', None)
        if not ext and data.path:
            ext = os.path.splitext(data.path)[1]
        clean_ext = ext.lstrip('.') if ext else "epub"

        # Extension sofort setzen
        if 'extension' in self.widgets:
            self.widgets['extension'].delete(0, tk.END)
            self.widgets['extension'].insert(0, clean_ext.lower())

        # 3. Einfache Felder loopen
        for key, value in mapping.items():
            if key in self.widgets:
                self.widgets[key].delete(0, tk.END)
                self.widgets[key].insert(0, str(value) if value is not None else "")

        # 1. Einfache Felder (mapping ohne regions und keywords!)
        for key, value in mapping.items():
            if key in self.widgets:
                self.widgets[key].delete(0, tk.END)
                self.widgets[key].insert(0, str(value) if value is not None else "")
        # 2. Helfer für Collections (Sets/Listen)
        def format_collection(col):
            if isinstance(col, (set, list)):
                return ", ".join(sorted(list(col))) if col else ""
            return str(col) if col else ""
        # 3. Regions spezial (jetzt mit schöner Formatierung)
        if 'regions' in self.widgets:
            self.widgets['regions'].delete(0, tk.END)
            self.widgets['regions'].insert(0, format_collection(data.regions))
        # 4. Keywords spezial (erweitert für Sets)
        kw_str = format_collection(data.keywords)
        self.widgets['keywords'].delete(0, tk.END)
        self.widgets['keywords'].insert(0, kw_str)
        # 5. Autoren spezial
        author_str = " & ".join([f"{fn} {ln}".strip() for fn, ln in data.authors]) if data.authors else ""
        self.widgets['authors_raw'].delete(0, tk.END)
        self.widgets['authors_raw'].insert(0, author_str)

        # Checkbutton
        if 'is_read_var' in self.vars:
            self.vars['is_read_var'].set(bool(data.is_read))

        # Textfelder
        for key, value in [('description_raw', data.description), ('notes', data.notes)]:
            self.widgets[key].delete('1.0', tk.END)
            self.widgets[key].insert('1.0', str(value) if value else "")

    def update_status(self, current, total, path, is_magic=False):
        """Aktualisiert Zähler und Pfadanzeige mit Farbsignal bei Magic-Heilung."""
        self.pos_label.config(text=f"{current} von {total}")
        self.path_entry.config(state='normal')
        self.path_entry.delete(0, tk.END)
        self.path_entry.insert(0, path)

        if is_magic:
            # Kräftiges Orange/Rot für den Text, helles Gelb für den Hintergrund
            self.path_entry.config(fg="red", bg="#fff9c4")
            # Kleiner Trick: Wir setzen den Fokus kurz drauf, damit man es sieht
        else:
            # Standardfarben (dein Blau auf Grau)
            self.path_entry.config(fg="blue", bg="#f0f0f0")

        self.path_entry.config(state='readonly')
    # ----------------------------------------------------------------------
    # 3. Auslesen der Form
    # ----------------------------------------------------------------------
    def get_data_from_widgets(self) -> 'BookData':
        """
        Sammelt alle Daten aus den Widgets ein und gibt ein BookData-Objekt zurück.
        Durch die Anführungszeichen versteht Python das als "Versprechen",
        dass es diese Klasse irgendwo gibt, ohne sie sofort beim Laden der Datei validieren zu müssen.
        """
        from Apps.book_data import BookData  # Lokaler Import, falls nötig

        # 1. Autoren-String parsen (Name & Name -> [('Vor', 'Nach'), ...])
        raw_authors = self.widgets['authors_raw'].get().strip()
        parsed_authors = []
        if raw_authors:
            # Trenne bei & oder ,
            temp_authors = raw_authors.replace(' & ', '|').replace(',', '|').split('|')
            for name in temp_authors:
                parts = name.strip().split()
                if len(parts) >= 2:
                    parsed_authors.append((" ".join(parts[:-1]), parts[-1]))
                elif parts:
                    parsed_authors.append(("", parts[0]))

        # 2. Keywords-String parsen (Wort, Wort -> [Wort, Wort])
        def string_to_set(widget_key):
            raw = self.widgets[widget_key].get().strip()
            if not raw or raw == "set()":
                return set()
            return {item.strip() for item in raw.split(',') if item.strip()}

        current_keywords = string_to_set('keywords')
        current_regions = string_to_set('regions')

        # 3. BookData Objekt befüllen
        data = BookData(
            path=self.path_entry.get(),  # Wird vom Controller überschrieben, falls nötig
            authors=parsed_authors,
            title=self.widgets['title'].get().strip(),
            extension=self.widgets['extension'].get().strip(),
            series_name=self.widgets['series_name'].get().strip() or None,
            series_number=self.widgets['series_number'].get().strip() or None,
            genre=self.widgets['genre'].get().strip() or None,
            regions=current_regions,
            language=self.widgets['language'].get().strip() or None,
            year=self.widgets['year'].get().strip() or None,
            isbn=self.widgets['isbn'].get().strip() or None,
            keywords=current_keywords,
            average_rating=self.widgets['average_rating'].get().strip() or None,
            ratings_count=self.widgets['ratings_count'].get().strip() or None,
            stars=self.widgets['stars'].get().strip() or None,
            is_read=1 if self.vars['is_read_var'].get() else 0,
            description=self.widgets['description_raw'].get('1.0', tk.END).strip() or None,
            notes=self.widgets['notes'].get('1.0', tk.END).strip() or None
        )

        return data
    # ----------------------------------------------------------------------
    # 4. GUI Elemente für Search
    # ----------------------------------------------------------------------
    def show_search_popup(self, search_callback):
        """Erstellt ein Toplevel-Fenster für die Suche."""
        search_window = tk.Toplevel(self.win)
        search_window.title("Buch suchen")
        search_window.geometry("500x180")
        search_window.transient(self.win)
        search_window.grab_set()

        frame = tk.Frame(search_window, padx=15, pady=15)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Autor (teilweise):").grid(row=0, column=0, sticky="w", pady=5)
        author_entry = tk.Entry(frame, width=40)
        author_entry.grid(row=0, column=1, sticky="ew", padx=5)

        tk.Label(frame, text="Titel (teilweise):").grid(row=1, column=0, sticky="w", pady=5)
        title_entry = tk.Entry(frame, width=40)
        title_entry.grid(row=1, column=1, sticky="ew", padx=5)

        def on_search():
            author = author_entry.get().strip()
            title = title_entry.get().strip()
            search_window.destroy()
            search_callback(author, title)  # Ruft die Suche im Controller auf

        tk.Button(frame, text="Suchen", command=on_search, width=15).grid(row=2, column=1, sticky="e", pady=10)

        author_entry.focus_set()
        search_window.bind('<Return>', lambda e: on_search())