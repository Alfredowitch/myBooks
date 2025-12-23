import io
import os
import sys

from typing import Optional, Dict
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageFile
import fitz  # Das ist PyMuPDF

# Setze dies, um Pillow zu erlauben, abgeschnittene Bilder zu laden (nötig für manche EPUB-Cover)
ImageFile.LOAD_TRUNCATED_IMAGES = True

# --- NEU: HINZUFÜGEN DES MODULES-PFADS ---
# Wenn deine Module im Ordner 'Gemini' (neben der aktuellen Datei) liegen:
MODULES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Gemini'))
sys.path.append(MODULES_DIR)

# --- Importiere vorhandene Funktionen ---
try:
    # Passe diese Importe an deine tatsächlichen Modulnamen an
    # Füge google_books hinzu!
    from read_db_ebooks import get_db_metadata, search_books, get_first_book_entry
    from save_db_ebooks import save_book_with_authors, delete_book_from_db
    from read_file import extract_info_from_filename, derive_metadata_from_path
    from read_epub import get_epub_metadata
    from read_pdf import get_book_cover
    from google_books import get_book_data_by_isbn  # <<< NEU: Für API-Daten
    from book_data_model import BookMetadata
except ImportError as e:
    # Kritischer Fehler: Zeige eine Meldung und beende das Programm
    print(f"Fehler beim Modul-Import. Bitte Dateinamen prüfen: {e}")
    # messagebox.showerror("Importfehler", f"Wichtige Module fehlen. App kann nicht starten: {e}")
    # sys.exit(1)

# Definiere den DB_PATH
DB_PATH = r'M://books.db'


def parse_author_string(author_str):
    """Wandelt 'Max Mustermann & Erika Musterfrau' in [('Max', 'Mustermann'), ('Erika', 'Musterfrau')] um."""
    if not author_str:
        return []

    # Trenne bei typischen Trennzeichen
    for sep in [' & ', ' und ', ', ']:
        author_str = author_str.replace(sep, '|')

    raw_list = [a.strip() for a in author_str.split('|') if a.strip()]
    parsed_authors = []

    for name in raw_list:
        parts = name.split()
        if len(parts) >= 2:
            # Einfachster Fall: Letztes Wort ist Nachname, alles davor Vorname
            first_name = " ".join(parts[:-1])
            last_name = parts[-1]
        else:
            # Falls nur ein Name da ist
            first_name = ""
            last_name = parts[0]
        parsed_authors.append((first_name, last_name))

    return parsed_authors

class BookBrowser:
    def __init__(self, win, initial_list=None):
        self.win = win
        # --- 1. Vorbereitung (Ganz am Anfang) ---
        win.title("E-Book Browser")
        win.geometry("850x850")
        self.navigation_list = initial_list if initial_list else []
        self.current_index = 0

        # --- 2. Daten-Container initialisieren ---
        self.book_data: BookMetadata = BookMetadata()
        self.widgets = {}
        self.vars = {}
        self.tk_img = None
        self.current_file_path = None
        self.temp_cover_to_delete = None
        self.original_db_data: Optional[Dict] = None  # <<< NEU: Für den Daten-Vergleich

        # --- 3. Initiales Layout ---
        self.create_menu()
        self.create_main_frame()
        self.create_nav_buttons()

        # --- NEU: Event-Handler für das Schließen des Fensters ---
        # Das fängt das "X" oben rechts ab
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- 4. Navigations-Daten laden nachdem alle Labels definiert sind ---
        if self.navigation_list:
            self.load_data(self.navigation_list[0])
        else:
            # Das hier sorgt dafür, dass die Felder trotzdem gezeichnet werden,
            # auch wenn kein Pfad übergeben wurde.
            self.clear_fields()
            self._fill_widgets_from_book_data()
            self.status_label.config(text="Bereit. Bitte Datei öffnen oder suchen...")
        self.update_status_bar()  # Initialer Aufruf

    def create_menu(self):
        menubar = tk.Menu(self.win)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="E-Book öffnen...", command=self.open_file)
        file_menu.add_command(label="Buch in DB suchen...", command=self.open_search_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Ersten Eintrag laden", command=self.load_first_entry)
        file_menu.add_command(label="DB-Pfad prüfen", command=self.check_db_path)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.win.quit)
        menubar.add_cascade(label="Datei", menu=file_menu)

        self.win.config(menu=menubar)

    # ----------------------------------------------------------------------
    # GUI-ERSTELLUNG (UNVERÄNDERT)
    # ----------------------------------------------------------------------

    def create_main_frame(self):
        """Erstellt das Hauptfenster-Layout mit allen Widgets."""
        self.main_frame = tk.Frame(self.win, padx=10, pady=10)
        self.main_frame.pack(fill='both', expand=True)
        # Das hier ist wichtig: Die Zeile, in der die Felder sitzen (Row 1),
        # muss sich ausdehnen dürfen.
        self.main_frame.rowconfigure(1, weight=1)
        self.main_frame.columnconfigure(1, weight=1)

        self.status_label = tk.Label(self.main_frame, text="Bitte eine Datei öffnen oder suchen...", fg="blue",
                                     wraplength=730, anchor="w", justify="left")
        self.status_label.grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky="ew")

        # --- 1. Detail-Frame für Felder (links) und Bild (rechts) ---
        detail_frame = tk.Frame(self.main_frame)
        detail_frame.grid(row=1, column=0, sticky="nsew", columnspan=2)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.columnconfigure(1, weight=0)

        fields_frame = tk.Frame(detail_frame)
        fields_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        fields_frame.columnconfigure(1, weight=1)

        # --- Label-Widget rechts für das Coverbild ändert sich einmal nach PIxel und einmal nach Text---
        self.cover_label = tk.Label(detail_frame, text="Coverbild", relief=tk.RIDGE,
                                    width=40, height=20)  # 40 Zeichen breit, 20 Zeilen hoch
        self.cover_label.grid(row=0, column=1, sticky="ne")
        # --- Ende Detail-Frame ---

        fields = [
            ('Autoren', 'authors_raw', 'entry'),
            ('Titel', 'title', 'entry'),
            ('Serienname', 'series_name', 'entry'),
            ('Seriennr.', 'series_number', 'entry'),
            ('Genre', 'genre', 'entry'),
            ('Region', 'region', 'entry'),
            ('Sprache', 'language', 'entry'),
            ('Jahr', 'year', 'entry'),
            ('ISBN', 'isbn', 'entry'),
            ('Schlüsselwörter', 'keywords', 'entry'),
            ('Durchschn. Rating', 'average_rating', 'entry'),
            ('Anzahl Ratings', 'ratings_count', 'entry'),
            ('Meine Sterne', 'stars', 'entry'),
            ('Gelesen', 'is_read', 'check')
        ]

        row_counter = 0
        for label_text, key, type_ in fields:
            label = tk.Label(fields_frame, text=f"{label_text}:", anchor="w")
            label.grid(row=row_counter, column=0, sticky="w", pady=3, padx=5)

            if type_ == 'check':
                # Wir erzeugen eine Liste von tk-Variablen. key ist das Datum, z.B. "is_read". Daraus wird "is_read_var"
                self.vars[key + '_var'] = tk.BooleanVar(fields_frame, value=False)
                widget = tk.Checkbutton(fields_frame, variable=self.vars[key + '_var'], onvalue=True, offvalue=False)
                widget.grid(row=row_counter, column=1, sticky="w", pady=3, padx=5)
            else:
                widget = tk.Entry(fields_frame, width=60)
                widget.grid(row=row_counter, column=1, sticky="ew", pady=3, padx=5)

            self.widgets[key] = widget
            row_counter += 1

        # Mehrzeilige Felder (Text-Widgets) unterhalb des Detail-Frames

        tk.Label(self.main_frame, text="Klappentext:", anchor="nw").grid(row=2, column=0, sticky="nw", pady=5, padx=5)
        self.widgets['description_raw'] = tk.Text(self.main_frame, height=5, width=50)
        self.widgets['description_raw'].grid(row=2, column=1, sticky="ew", pady=5, padx=(50, 5))

        tk.Label(self.main_frame, text="Notizen:", anchor="nw").grid(row=3, column=0, sticky="nw", pady=5, padx=5)
        self.widgets['notes'] = tk.Text(self.main_frame, height=5, width=50)
        self.widgets['notes'].grid(row=3, column=1, sticky="ew", pady=5, padx=(50, 5))

    def create_exit_button(self):
        # Wir nutzen einen Frame, der ganz unten am Fenster klebt
        exit_frame = tk.Frame(self.win)
        exit_frame.pack(fill='x', side="bottom", pady=10, padx=10)
        # Der Beenden-Button schließt jetzt ohne Umwege
        exit_button = tk.Button(exit_frame, text="Beenden", width=15,
                                command=self.win.quit)
        exit_button.pack(side="right")

    def create_nav_buttons(self):
        """Erstellt die Navigations- und Statuszeile auf einer Höhe."""
        # Der Container für alles (Navi, Status, Speichern, Löschen, Beenden)
        nav_container = tk.Frame(self.main_frame)
        nav_container.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        # --- LINKE SEITE: Navigation ---
        self.btn_first = tk.Button(nav_container, text="|<", width=3, command=self.nav_first)
        self.btn_first.pack(side="left", padx=2)
        self.btn_prev = tk.Button(nav_container, text="<", width=3, command=self.nav_prev)
        self.btn_prev.pack(side="left", padx=2)

        # Der Zähler: "x von y"
        self.pos_label = tk.Label(nav_container, text="0 von 0", font=("Arial", 9, "bold"), padx=10)
        self.pos_label.pack(side="left")

        self.btn_next = tk.Button(nav_container, text=">", width=3, command=self.nav_next)
        self.btn_next.pack(side="left", padx=2)
        self.btn_last = tk.Button(nav_container, text=">|", width=3, command=self.nav_last)
        self.btn_last.pack(side="left", padx=2)

        # --- MITTE: Speichern & Löschen ---
        save_button = tk.Button(nav_container, text="Speichern", bg="#e1f5fe", command=self.save_data)
        save_button.pack(side="left", padx=(20, 0))

        delete_button = tk.Button(nav_container, text="🗑", fg="red", command=self.delete_current_book, relief="flat")
        delete_button.pack(side="left", padx=(10, 0))

        # --- RECHTE SEITE: Beenden ---
        exit_button = tk.Button(nav_container, text="Beenden", width=10, command=self.on_close)
        exit_button.pack(side="right", padx=5)

    # ----------------------------------------------------------------------
    # NAVIGATIONSLOGIK
    # ----------------------------------------------------------------------
    def update_navigation(self, file_path, context_list):
        """Aktualisiert die Liste für die Vor/Zurück-Navigation."""
        self.navigation_list = context_list
        try:
            self.current_index = self.navigation_list.index(file_path)
        except ValueError:
            self.current_index = -1

    def _build_author_navigation(self, author_name):
        """Holt alle Bücher des Autors und sortiert sie nach Serie/Nummer."""
        try:
            # Suche nur nach dem Autor, ohne Titel-Einschränkung
            all_author_books = search_books(author_name, "", db_path=DB_PATH)
            if not all_author_books:
                return

            # Sortier-Logik:
            # 1. Serienname (Bücher ohne Serie kommen zuerst oder zuletzt, je nach Wunsch)
            # 2. Seriennummer (als Zahl sortiert)
            # 3. Titel (falls keine Serie vorhanden)
            sorted_books = sorted(
                all_author_books,
                key=lambda x: (
                    (x.get('series_name') or '').lower(),
                    float(x.get('series_number') or 0),
                    (x.get('title') or '').lower()
                )
            )
            self.navigation_list = [os.path.normpath(b['file_path']) for b in sorted_books]
            # Position in der Liste finden
            if self.current_file_path in self.navigation_list:
                self.current_index = self.navigation_list.index(self.current_file_path)
            else:
                self.current_index = 0  # Fallback

        except Exception as e:
            print(f"Fehler beim Aufbau der Autor-Navigation: {e}")

    def nav_first(self):
        if self.navigation_list:
            self.load_data(self.navigation_list[0])

    def nav_last(self):
        if self.navigation_list:
            self.load_data(self.navigation_list[-1])

    def nav_next(self):
        if self.navigation_list and self.current_index < len(self.navigation_list) - 1:
            new_index = self.current_index + 1
            self.load_data(self.navigation_list[self.current_index + 1])

    def nav_prev(self):
        if self.navigation_list and self.current_index > 0:
            new_index = self.current_index - 1
            self.load_data(self.navigation_list[self.current_index - 1])

    def update_status_bar(self):
        """Aktualisiert die Positionsanzeige und den Pfad."""
        if self.navigation_list:
            total = len(self.navigation_list)
            current = self.current_index + 1
            # Den Zähler unten aktualisieren
            self.pos_label.config(text=f"{current} von {total}")

            # Den Pfad lassen wir oben im blauen Label, damit man weiß, wo die Datei liegt
            status_text = f"Datei: {os.path.basename(self.current_file_path)}"
            self.status_label.config(text=status_text, fg="blue")
        else:
            self.pos_label.config(text="0 von 0")
            self.status_label.config(text="Bereit.", fg="blue")

    # ----------------------------------------------------------------------
    # ALLGEMEINE FUNKTIONEN (ANGEPASST)
    # ----------------------------------------------------------------------
    def delete_old_cover(self):
        """Löscht die temporäre Cover-Datei des vorherigen Buches."""
        if self.temp_cover_to_delete and os.path.exists(self.temp_cover_to_delete):
            try:
                os.remove(self.temp_cover_to_delete)
                print(f"Altes temporäres Cover gelöscht: {self.temp_cover_to_delete}")
            except OSError as e:
                print(f"WARNUNG: Konnte altes temporäres Cover nicht löschen: {e}")

        self.temp_cover_to_delete = None

    def check_db_path(self):
        """Zeigt den aktuell verwendeten Datenbankpfad an."""
        messagebox.showinfo("Datenbankpfad", f"Derzeit verwendeter DB-Pfad:\n{DB_PATH}")


    def clear_fields(self):
        # Leere alle Entry/Text-Widgets und setze Checkbuttons zurück
        for key, widget in self.widgets.items():
            if isinstance(widget, tk.Entry):
                widget.delete(0, tk.END)
            elif isinstance(widget, tk.Text):
                widget.delete('1.0', tk.END)
            elif key.startswith(('is_read')):  # is_complete gibt es nicht als Checkbox
                var = self.vars.get(key + '_var')
                if var:
                    var.set(False)

        # Setze Cover-Label zurück
        self.cover_label.config(image='', text='Coverbild')
        self.cover_label.image = None


    def _fill_widgets_from_book_data(self):
        """Füllt alle GUI-Widgets basierend auf self.book_data."""

        # Mapping der GUI-Keys zu den BookMetadata-Attributen
        widget_to_attr_map = {
            'authors_raw': 'authors',
            'title': 'title',
            'series_name': 'series_name',
            'series_number': 'series_number',
            'genre': 'genre',
            'region': 'region',
            'language': 'language',
            'year': 'year',
            'isbn': 'isbn',
            'keywords': 'keywords',
            'average_rating': 'average_rating',
            'ratings_count': 'ratings_count',
            'stars': 'stars',
            'is_read': 'is_read',
            'description_raw': 'description',  # Mappung auf 'description' in BookMetadata
            'notes': 'notes',
            # 'is_complete' wird hier nicht verwendet, da es kein direktes Widget hat
        }

        for widget_key, attr_name in widget_to_attr_map.items():

            value = getattr(self.book_data, attr_name, None)
            widget = self.widgets.get(widget_key)

            if widget is None: continue

            # Titel-Check
            if widget_key == 'title':
                widget.delete(0, tk.END)
                widget.insert(0, str(value) if value else "")
                continue

            # Spezialfall: Checkbuttons (is_read)
            if widget_key == 'is_read':
                var = self.vars.get(widget_key + '_var')
                if var: var.set(bool(value))
                continue

            # Spezialfall: Autoren (List[Tuple] -> String)
            elif widget_key == 'authors_raw':
                if isinstance(value, list):
                    author_display = [f"{fn} {ln}" for fn, ln in value]
                    value = " & ".join(author_display)

            # Spezialfall: Keywords (List[str] -> String)
            elif widget_key == 'keywords':
                if isinstance(value, list):
                    # Macht aus ["Business\Python", "KI"] -> "Business\Python, KI"
                    value = ", ".join(str(k) for k in value if k)
                    widget.delete(0, tk.END)
                    widget.insert(0, str(value) if value else "")

            # Behandlung der Text-Widgets (mehrzeilig: description, notes)
            if isinstance(widget, tk.Text):
                widget.delete('1.0', tk.END)
                if value is not None:
                    widget.insert('1.0', str(value))

            # Behandlung der Entry-Widgets (einzeilig)
            elif isinstance(widget, tk.Entry):
                widget.delete(0, tk.END)
                widget.insert(0, str(value) if value is not None else "")

        self.update_status_bar()

    def on_close(self):
        """Sicheres Schließen des Browsers."""
        try:
            # Falls du temporäre Cover-Dateien löschen willst
            if hasattr(self, 'temp_cover_to_delete') and self.temp_cover_to_delete:
                self.delete_old_cover()

            # Wenn du Gemini Live oder Threads nutzt, hier stoppen
        except Exception as e:
            print(f"Fehler beim Aufräumen: {e}")
        finally:
            # DIESER BEFEHL IST ENTSCHEIDEND:
            self.win.destroy()

    def get_star_string(self, rating):
        try:
            # Falls rating ein String ist, in Zahl umwandeln
            num = int(float(rating))
            if 1 <= num <= 5:
                return "⭐" * num
            return ""
        except (ValueError, TypeError):
            return ""

    # ----------------------------------------------------------------------
    # GUI SUCH-FUNKTIONEN (Sucht nach 1. Datensatz, Buch aus DB mit Autor & Titel oder Buch vom Filesystem.)
    # ----------------------------------------------------------------------
    def open_search_dialog(self):
        """Startet den Suchvorgang mit einem komplexeren Dialog."""
        self.show_search_popup()

    def show_search_popup(self):
        """Erstellt ein Toplevel-Fenster für die Eingabe von Autor und Titel."""
        self.search_window = tk.Toplevel(self.win)
        self.search_window.title("Buch suchen")
        self.search_window.geometry("600x180")
        self.search_window.transient(self.win)

        frame = tk.Frame(self.search_window, padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Autor (teilweise):").grid(row=0, column=0, sticky="w", pady=5)
        self.search_author_entry = tk.Entry(frame, width=40)
        self.search_author_entry.grid(row=0, column=1, sticky="ew", padx=5)

        tk.Label(frame, text="Titel (teilweise):").grid(row=1, column=0, sticky="w", pady=5)
        self.search_title_entry = tk.Entry(frame, width=40)
        self.search_title_entry.grid(row=1, column=1, sticky="ew", padx=5)

        tk.Button(frame, text="Suchen", command=self.perform_search).grid(row=2, column=1, sticky="e", pady=10)

        # --- FOKUS UND KEY-BINDINGS ---
        self.search_author_entry.focus_set()
        self.search_window.bind('<Return>', lambda event: self.perform_search())

        self.search_window.grab_set()
        self.win.wait_window(self.search_window)

    # ----------------------------------------------------------------------
    # 1. LADEN DES 1. Datensatzes (vor allem als Apps gedacht)
    # ----------------------------------------------------------------------
    def load_first_entry(self):
        """Lädt den allerersten Eintrag aus der Datenbank und zeigt ihn an."""
        self.status_label.config(text="Versuche, den ersten Datensatz zu laden...", fg="orange")

        try:
            # Wir laden nur den Pfad und rufen dann load_data mit diesem Pfad auf
            first_entry_dict = get_first_book_entry(DB_PATH)

            if first_entry_dict and first_entry_dict.get('file_path'):
                # load_data übernimmt die Aggregation
                self.load_data(first_entry_dict['file_path'])
                # Status wird von load_data gesetzt
            else:
                messagebox.showinfo("Datenbankleer",
                                    "Die Datenbank ist leer oder der erste Eintrag konnte nicht geladen werden.")
                self.status_label.config(text="Datenbankfehler oder keine Einträge gefunden.", fg="red")

        except Exception as e:
            messagebox.showerror("Fehler beim Laden",
                                 f"Ein Fehler ist beim Abrufen des ersten Datensatzes aufgetreten: {e}")
            self.status_label.config(text="Fehler beim Laden des ersten Eintrags.", fg="red")
            print(f"Fehler beim Laden des ersten Eintrags: {e}")


    # ----------------------------------------------------------------------
    # 2. SUCHEN NACH EINEM BUCH IN DER DB (Auto und Titel gemäß GUI-SEARCH)
    # ----------------------------------------------------------------------
    def perform_search(self):
        """Führt die Suche in der Datenbank aus und zeigt Ergebnisse an."""
        author = self.search_author_entry.get().strip()
        title = self.search_title_entry.get().strip()

        if not author and not title:
            messagebox.showwarning("Eingabe fehlt", "Bitte Autor oder Titel zur Suche eingeben.")
            return

        self.search_window.destroy()
        self.status_label.config(text=f"Suche läuft: Autor='{author}', Titel='{title}'...", fg="blue")

        try:
            results = search_books(author, title, db_path=DB_PATH)
            if not results:
                messagebox.showinfo("Keine Treffer", "Keine Bücher gefunden.")
                self.status_label.config(text="Suche abgeschlossen. Keine Treffer.", fg="red")
                return
            if len(results) == 1:
                # Direkt laden ohne Umweg über die Liste
                self.load_data(results[0]['file_path'])
            else:
                # Mehrere Treffer -> Liste zur Auswahl zeigen
                self.display_search_results(results)

        except Exception as e:
            messagebox.showerror("Datenbankfehler", f"Fehler bei der Suche: {e}")
            self.status_label.config(text="Datenbankfehler bei der Suche.", fg="red")
            print(f"Fehler bei der Suche: {e}")

    def display_search_results(self, results):
        """WEnn die Datenbanksuche mehrere Treffer ergibt, werden alle in einem Listenfeld gezeigt."""
        """Der Nutzer kann ein Buch auswählen. Das wird dann geladen und angezeigt."""
        result_window = tk.Toplevel(self.win)
        result_window.title(f"Suchergebnisse ({len(results)} Treffer)")
        result_window.transient(self.win)
        result_window.geometry("600x400")

        tk.Label(result_window, text="Bitte Buch zum Bearbeiten/Bewerten auswählen (Doppelklick):").pack(padx=10,
                                                                                                         pady=5)

        list_frame = tk.Frame(result_window)
        list_frame.pack(padx=10, pady=5, fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(list_frame, width=80, height=15, yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.config(command=listbox.yview)

        self.search_results_map = {}

        for i, book in enumerate(results):
            # Erstellt den Anzeigetext mit Serie, Seriennummer und Autor
            series_display = ""
            if book.get('series_name') and book.get('series_number'):
                series_display = f"[{book['series_name']} #{book['series_number']}]"
            elif book.get('series_name'):
                series_display = f"[{book['series_name']}]"

            # Autorenliste ist in der DB eine Liste von Tupeln (Vorname, Nachname)
            author_names = " & ".join([f"{fn} {ln}" for fn, ln in book.get('authors', [])])

            display_text = (
                f"{series_display} {book.get('title')} von {author_names}"
            )

            listbox.insert(tk.END, display_text)
            self.search_results_map[i] = book

        def on_select(evt):
            selected_indices = listbox.curselection()
            if selected_indices:
                selected_index = selected_indices[0]
                selected_book = self.search_results_map[selected_index]

                # NAVIGATION FIX: Wir setzen die Liste auf ALLE Suchergebnisse
                self.navigation_list = [os.path.normpath(b['file_path']) for b in results]
                self.current_index = selected_index

                # Nur den Pfad übergeben! load_data ruft get_db_metadata auf, um ALLE Details zu laden.
                self.load_data(selected_book['file_path'])
                result_window.destroy()
                self.status_label.config(text=f"Buch geladen: {selected_book['title']}", fg="green")

        listbox.bind('<Double-1>', on_select)

        result_window.grab_set()
        self.win.wait_window(result_window)

    # ----------------------------------------------------------------------
    # 3. LADEN EINES BUCHES VOM FILESYSTEM (nach dem SUCHDIALOG aus der GUI-SEARCH)
    # ----------------------------------------------------------------------
    # Es wird nur über das GUI-SEARCH open_file aufgerufen.
    # Anschließend und beim Navigieren wird nur noch load_data(file_path) aufgerufen.
    def open_file(self):
        file_path = filedialog.askopenfilename(
            defaultextension=".epub",
            filetypes=[("E-Books", "*.epub *.pdf *.mobi")]
        )
        if not file_path:
            return

        # Pfad normalisieren
        file_path = os.path.normpath(file_path)

        # Für die Filesystem-Navigation
        directory = os.path.dirname(file_path)
        extensions = ('.epub', '.pdf', '.mobi')
        # Alle unterstützten Dateien im Ordner finden und sortieren
        files_in_dir = [
            os.path.normpath(os.path.join(directory, f)) for f in os.listdir(directory)
            if f.lower().endswith(extensions)
        ]
        self.navigation_list = sorted(files_in_dir)
        self.update_navigation(file_path, files_in_dir)

        self.current_file_path = file_path
        self.load_data(file_path)

    def load_data(self, file_path):
        """
        Lädt ein Buch aus dem Filesystem und verwaltet die Navigations-Position.
        Wichtig: Wir prüfen zuerst, ob es das Buch schon in der DB gibt,
                 dann reichern wir die Info an vom, Dateinamen, EPUB-Metadaten und Google Books API.
        Die Aggregation der Daten nutzt die BookMetadata.merge_with() Methode zur Priorisierung.
        """

        # Wir initialisieren das Load ..
        self.status_label.config(text=f"Lade Daten für: {os.path.basename(file_path)}", fg="blue")
        self.delete_old_cover()
        file_path = os.path.normpath(file_path)
        self.current_file_path = file_path
        # WICHTIG: Prüfen, ob das Buch in der aktuellen Navi-Liste ist
        if file_path in self.navigation_list:
            self.current_index = self.navigation_list.index(file_path)

        # A. DATEN AUS DB LADEN (Highest Priority- basierend auf den Pfadnamen)
        db_data_dict = get_db_metadata(file_path, db_path=DB_PATH)
        self.original_db_data = db_data_dict

        # Wenn der Eintrag als 'Komplett' markiert ist, verwenden wir ihn direkt
        if db_data_dict and db_data_dict.get('is_complete') == 1:
            self.book_data = BookMetadata.from_dict(db_data_dict)
            print(f"Lade DB-Daten: '{self.book_data.title}' (als komplett markiert).")
            # Springe direkt zum Füllen der Maske

            return
        else:
            # B. BASIS: Dateiname-Parsing (Höchste Priorität für Titel/Autor)
            print("  -> Basis: Dateiname-Parsing...")
            filename_data_dict = extract_info_from_filename(file_path)

            lang, reg, gen, path_keywords = derive_metadata_from_path(file_path)
            if lang:
                filename_data_dict['language'] = lang
            if gen:
                filename_data_dict['genre'] = gen
            if reg:
                filename_data_dict['region'] = reg
            if path_keywords:
                # Falls schon Keywords im dict sind, hängen wir die neuen an
                existing_keywords = filename_data_dict.get('keywords', [])
                # Dubletten vermeiden beim Zusammenführen
                for kw in path_keywords:
                    if kw not in existing_keywords:
                        existing_keywords.append(kw)
                filename_data_dict['keywords'] = existing_keywords
            filename_data_dict['file_path'] = file_path

            final_data = BookMetadata.from_dict(filename_data_dict)

            # C. EPUB-Anreicherung
            if file_path.lower().endswith('.epub'):
                print("  -> EPUB-Parsing...")
                try:
                    epub_data_dict = get_epub_metadata(file_path)
                    epub_data = BookMetadata.from_dict(epub_data_dict)
                    final_data.merge_with(epub_data)
                    self.temp_cover_to_delete = final_data.temp_image_path
                except Exception as e:
                    print(f"WARNUNG: Konnte EPUB-Metadaten nicht lesen: {e}")

            # D. DB-Daten-Anreicherung (Mittlere Priorität, holt manuelle Felder)
            if db_data_dict:
                print("  -> Vorhandene DB-Daten ergänzen (Manuelle Felder)")
                db_data_instance = BookMetadata.from_dict(db_data_dict)
                final_data.merge_with(db_data_instance)

            # E. API-Daten-Anreicherung (Niedrigste Priorität)
            if final_data.isbn:
                print(f"  -> Suche API-Daten für ISBN: {final_data.isbn}...")
                try:
                    api_data_dict = get_book_data_by_isbn(final_data.isbn)
                    api_data = BookMetadata.from_dict(api_data_dict)
                    final_data.merge_with(api_data)
                except Exception as e:
                    print(f"WARNUNG: Konnte Google Books API nicht abrufen: {e}")

        self.book_data = final_data

        if not self.book_data.title:
            self.status_label.config(text="FEHLER: Datei enthält keine lesbaren Metadaten.", fg="red")
            return
        else:
            print(f"Aggregation abgeschlossen. Titel: {self.book_data.title}")


        # ----------------------------------------------------------------------
        # 3. Navigationspfad für Autoren füllen (nur beim 1. Mal!)
        # ----------------------------------------------------------------------
        # 1. Fall: Das Buch ist bereits in der aktuellen Liste (User klickt Next/Prev)
        if file_path in self.navigation_list:
            self.current_index = self.navigation_list.index(file_path)

        # 2. Fall: Das Buch ist NEU (User kommt von Suche oder Datei-Öffnen)
        else:
            # Wir leeren die alte Liste, damit kein falscher Kontext bleibt
            self.navigation_list = []
            self.current_index = -1

            # Jetzt bauen wir die Navigation basierend auf dem Autor neu auf
            if self.book_data.authors:
                # Wir bauen den Namen für die Suche zusammen
                first_author_tuple = self.book_data.authors[0]
                author_name = f"{first_author_tuple[0]} {first_author_tuple[1]}".strip()

                # Diese Methode füllt self.navigation_list und setzt den self.current_index
                self._build_author_navigation(author_name)

        # ----------------------------------------------------------------------
        # 4. Maske füllen
        # ----------------------------------------------------------------------
        self.clear_fields()
        self.load_cover_image(self.book_data.temp_image_path)  # Lädt das Cover (ob temp oder permanent)
        self._fill_widgets_from_book_data()
        self.update_status_bar()
        self.status_label.config(text=f"Geladen: {self.book_data.title}", fg="green")

    # ----------------------------------------------------------------------
    # 4. LADEN DES COVER IMAGES (Sowohl für Daten aus dem Filesystem, als auch von der DB)
    # ----------------------------------------------------------------------
    def load_cover_image(self, image_path):
        """Lädt ein Bild von einem Pfad ODER extrahiert es aus einer PDF."""
        if not image_path or not os.path.exists(image_path):
            self.cover_label.config(image='', text='Kein Cover', width=40, height=20)
            return
        else:
            self.cover_label.config(image='', text='Lädt...')
            self.cover_label.image = None
            self.tk_img = None
            max_size = (330, 420)

        # FALL A: Wir haben einen Pfad zu einer Bilddatei (z.B. von einer EPUB extrahiert)
        if image_path and os.path.exists(image_path) and not image_path.lower().endswith('.pdf'):
            try:
                img = Image.open(image_path)
                # Seitenaspekt wird beibehalten
                img.thumbnail(max_size, Image.LANCZOS)
                # Platz wird ausgefüllt
                # img.resize(max_size, Image.LANCZOS)
                self.tk_img = ImageTk.PhotoImage(img)
                # Wir weisen dem Label das Bild zu und löschen den Text
                self.cover_label.config(image=self.tk_img, text='')
                self.cover_label.image = self.tk_img  # Referenz behalten!

            except Exception as e:
                print(f"Fehler beim Laden der Bilddatei: {e}")

        # FALL B: Wir haben eine PDF-Datei und brauchen die erste Seite als Cover
        elif self.current_file_path and self.current_file_path.lower().endswith('.pdf'):
            try:
                doc = fitz.open(self.current_file_path)
                page = doc.load_page(0)

                # Wir berechnen den Zoom so, dass wir auf jeden Fall über 1000 Pixel Breite kommen
                # Das garantiert genug Auflösung für die Skalierung
                zoom = 4.0
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))

                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))

                # Hier erzwingen wir die Größe!
                # Resize statt Thumbnail sorgt dafür, dass es genau max_size füllt
                img = img.resize((310, 420), Image.Resampling.LANCZOS)

                self.tk_img = ImageTk.PhotoImage(img)
                doc.close()
            except Exception as e:
                print(f"Fehler bei PDF-Extraktion: {e}")

        # ANZEIGE AKTUALISIEREN
        if self.tk_img:
            self.cover_label.config(image=self.tk_img, text='', width=0, height=0)
            self.cover_label.image = self.tk_img
        else:
            self.cover_label.config(text="Kein Cover verfügbar", width=40, height=20)


    # ----------------------------------------------------------------------
    # 5. SPEICHERN DES DATENSATZES
    # ----------------------------------------------------------------------
    def save_data(self):
        # Wir speichern die BookMetadata-Instanz, nicht das alte Dictionary.
        if not self.book_data or not self.book_data.file_path:
            messagebox.showerror("Fehler", "Zuerst ein Buch laden.")
            return

        # 1. Werte aus der Maske in self.book_data zurückschreiben
        for key, widget in self.widgets.items():
            if key == 'is_read':
                var = self.vars.get(key + '_var')
                if var:
                    setattr(self.book_data, key, 1 if var.get() else 0)
                continue

            # Text-Widgets
            elif key in ['description_raw', 'notes']:
                attr_name = 'description' if key == 'description_raw' else key
                value = widget.get('1.0', tk.END).strip()
                setattr(self.book_data, attr_name, value if value else None)
                continue

            # Autoren (Spezialfall, da wir Tupel benötigen)
            elif key == 'authors_raw':
                raw_author_string = widget.get().strip()
                # Nutze die neue Parser-Funktion
                new_authors = parse_author_string(raw_author_string)
                self.book_data.authors = new_authors
                continue
            # Titel
            if key == 'title':  # oder wie auch immer der Key bei dir heißt
                value = widget.get().strip()
                print(f"DEBUG-TITEL: Key ist '{key}', Wert im Feld ist '{value}'")
                # Erzwinge das Speichern testweise mal ohne setattr:
                self.book_data.title = value
                # Entry-Widgets
            else:
                value = widget.get().strip()
                attr_name = key

                # Spezialfall Seriennummer (sollte immer ein String sein)
                if attr_name == 'series_number' and value:
                    try:
                        value = str(int(float(value)))
                    except ValueError:
                        pass  # Bleibt ein String

                # Spezialfall Keywords (String -> List[str])
                if attr_name == 'keywords' and value:
                    value = [k.strip() for k in value.split(',') if k.strip()]
                elif attr_name == 'keywords' and not value:
                    value = []

                setattr(self.book_data, attr_name, value if value else None)

        # 2. Daten in die DB speichern
        try:
            # save_book_with_authors erwartet BookMetadata-Instanz (haben wir in save_db_ebooks.py korrigiert)
            save_book_with_authors(self.book_data, db_path=DB_PATH)
            messagebox.showinfo("Erfolg",
                                f"Daten für {os.path.basename(self.book_data.file_path)} erfolgreich gespeichert.")
            # Zur Kontrolle. Wir laden denselben Datensatz wieder aus der DB. Jetzt sehen wir, ob die Änderungen gespeichert wurden.
            self.load_data(self.current_file_path)
        except Exception as e:
            messagebox.showerror("Datenbankfehler", f"Fehler beim Speichern: {e}")
            print(f"Fehler beim Speichern der Daten: {e}")

    def delete_current_book(self):
        """Löscht das aktuelle Buch aus der DB und aktualisiert die Liste."""
        if not self.original_db_data:
            messagebox.showwarning("Löschen", "Dieses Buch existiert nicht in der Datenbank.")
            return

        if messagebox.askyesno("Löschen", f"Soll '{self.book_data.title}' wirklich aus der Datenbank gelöscht werden?"):
             # Falls vorhanden, sonst über path
            # Annahme: Deine DB-Funktion zum Löschen existiert
            delete_book_from_db(self.current_file_path)

            # Aus der Navigationsliste entfernen
            current_path = self.navigation_list.pop(self.current_index)

            # Anzeige aktualisieren
            if self.navigation_list:
                # Springe zum vorherigen oder bleibe am Ende
                self.current_index = min(self.current_index, len(self.navigation_list) - 1)
                self.load_data(self.navigation_list[self.current_index])
            else:
                self.clear_fields()
                self.status_label.config(text="Alle Bücher gelöscht.", fg="red")

            messagebox.showinfo("Erfolg", "Buch wurde gelöscht.")

if __name__ == "__main__":
    try:
        if 'get_db_metadata' in globals() and 'get_epub_metadata' in globals():
            root = tk.Tk()
            app = BookBrowser(root)
            root.mainloop()

            app.delete_old_cover()

        else:
            messagebox.showerror("Startfehler",
                                 "Kritische Funktionen konnten nicht geladen werden. App kann nicht starten.")
    except Exception as final_e:
        print(f"Kritischer Fehler beim Starten oder Beenden der App: {final_e}")