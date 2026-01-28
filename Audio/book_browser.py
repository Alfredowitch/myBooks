"""
DATEI: book_browser.py
PROJEKT: MyBook-Management (v1.5.0)
BESCHREIBUNG: Vollständiger Controller. Alle Methoden für View-Buttons vorhanden.
              Inklusive sanitize_path und Cover-Testlogik.
"""
import tkinter as tk
from tkinter import messagebox, filedialog
import os
import re
from typing import List, Dict, Union

# Eigene Module
from Zoom.utils import sanitize_path

try:
    from Zoom.browser_model import BrowserModel
    from Zoom.browser_view import BrowserView
except ImportError as e:
    print(f"DEBUG: IMPORT FEHLER! {e}")

class BookBrowser:

    # ----------------------------------------------------------------------
    # Initialisieren und Datenhandel für externe Apps (Autoren-Browser und Book-Analyser
    #                    liefern eine Navigationslist als List of Dictionaries (ID:Nummer oder Path: pfad)
    # ----------------------------------------------------------------------
    def __init__(self, win, initial_list: List[Dict[str, Union[int, str]]] = None):
        self.win = win
        self.model = BrowserModel()
        self.view = BrowserView(self.win)

        self.load_new_list = self.load_from_list
        self.navigation_list = initial_list if initial_list else []
        self.current_index = 0
        self.current_book = None
        self.current_file_path = ""
        self._img_keep_alive = None

        # Menü direkt vom Browser aus initialisieren
        self.create_menu()

        # Bind erst NACHDEM alle Methoden definiert sind
        self._bind_view_actions()

        if self.navigation_list:
            self.display_navigation_item(0)
    # ----------------------------------------------------------------------
    #  Menü im Browser
    # ----------------------------------------------------------------------
    def create_menu(self):
        menubar = tk.Menu(self.win)
        file_menu = tk.Menu(menubar, tearoff=0)

        # Hier nutzen wir 'self', da wir uns im Browser befinden
        file_menu.add_command(label="📁 Datei laden", command=self.load_from_file)
        file_menu.add_command(label="🔍 DB Suche",
                              command=lambda: self.view.show_search_popup(self.load_from_database))
        file_menu.add_separator()
        file_menu.add_command(label="📋 Report laden", command=self.load_from_report_file)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.win.quit)

        menubar.add_cascade(label="Datei", menu=file_menu)
        self.win.config(menu=menubar)

    # ----------------------------------------------------------------------
    # Verbinden der GUI-Buttons
    # ----------------------------------------------------------------------
    def nav_next(self):
        self.display_navigation_item(self.current_index + 1)

    def nav_prev(self):
        self.display_navigation_item(self.current_index - 1)

    def nav_first(self):
        self.display_navigation_item(0)

    def nav_last(self):
        self.display_navigation_item(len(self.navigation_list) - 1)

    def _bind_view_actions(self):
        """Verknüpft Controller-Methoden mit View-Buttons und ergänzt die Toolbar."""
        # Standard-Buttons der View (Navigation etc.)
        self.view.create_nav_buttons(self)

        # Binding für die Serien-Name-Combobox (Blau)
        # Wenn der User eine Serie auswählt, soll die Serie einem Werk zugeordnet oder angelegt werden
        if 's_name' in self.view.widgets:
            self.view.widgets['s_name'].bind("<<ComboboxSelected>>", self._on_series_selected)
        # Binding für die Work-Titel-Combobox (Grün)
        # Wenn der User ein neues Work auswählt, soll dieses Werk dem Buch zugeordnet oder angelegt werden
        if 'w_title' in self.view.widgets:
            self.view.widgets['w_title'].bind("<<ComboboxSelected>>", self._on_work_selected)

        # WICHTIG: Wenn der Autor geändert wird, müssen die Listen neu geladen werden
        if 'authors' in self.view.widgets:
            # 'FocusOut' triggert, wenn der User das Feld verlässt
            self.view.widgets['authors'].bind("<FocusOut>", lambda e: self.update_ui_lists())

        if 'b_series_name' in self.view.widgets:
            self.view.widgets['b_series_name'].bind("<FocusOut>", lambda e: self.re_evaluate_fingerprint())
        if 'b_series_number' in self.view.widgets:
            self.view.widgets['b_series_number'].bind("<FocusOut>", lambda e: self.re_evaluate_fingerprint())

    def update_ui_lists(self):
        if not self.current_book:
            return
        author_list = self.current_book.authors
        # 1. Serien-Liste aktualisieren (via Model)
        self.current_book.all_available_series = self.current_book.get_prioritized_series(author_list)

        # 2. Werk-Match via Fingerprint (via Model)
        # WICHTIG: Wir übergeben das gesamte Objekt ans Model
        suggested_work_id = self.current_book.find_work_by_series_fingerprint(self.current_book)

        if suggested_work_id:
            # Falls wir ein Werk finden, laden wir die Details (Titel etc.) direkt in den Manager
            self.current_book.load_work_into_manager(suggested_work_id)
            # Die book_id Verknüpfung setzen
            self.current_book.book.work_id = suggested_work_id

        # 3. Alle Werke dieser Autoren für die Werk-Combobox holen
        self.current_book.all_available_works = self.current_book.get_works_by_authors(author_list)

        # 4. View aktualisieren
        # fill_widgets nimmt jetzt die befüllten Listen aus current_book und schreibt sie in die Combos
        self.view.fill_widgets(self.current_book)

    def re_evaluate_fingerprint(self, event=None):
        """
        Holt die aktuellen Daten aus der View und prüft, ob durch die
        Korrekturen (Serie/Nummer) ein passendes Werk in der DB existiert.
        """
        if not self.current_book:
            return

        # 1. Aktuelle UI-Eingaben (auch die ungespeicherten!) in den Manager laden
        self.view.get_data_from_widgets(self.current_book)

        # 2. Den "Fingerabdruck" prüfen (Autor + Serie + Nummer + Sprache)
        #found_work_id = self.current_book.find_work_by_series_fingerprint()
        found_work_id = self.current_book.find_work_by_series_fingerprint(self.current_book)

        if found_work_id:
            # Treffer! Wir biegen die Work-ID im Manager um
            self.current_book.work.id = found_work_id
            # Optional: Wir könnten hier auch den Master-Titel des Werks
            # aus der DB laden und im UI anzeigen
            print(f"✨ Automatische Zuordnung: Werk ID {found_work_id} erkannt.")

            # 3. Listen in der View aktualisieren (damit das Combo-Feld den Treffer zeigt)
            self.update_ui_lists()
        else:
            # Kein Fingerabdruck? Dann zumindest die Listen für die Combo-Boxen
            # basierend auf den (neuen) Autoren/Serien aktualisieren
            self.update_ui_lists()

    def _on_series_selected(self, event=None):
        """Wird aufgerufen, wenn eine Serie aus der Liste gewählt wird."""
        new_name = self.view.widgets['b_series_name'].get()
        if not new_name:
            return
        # 1. Details vom Model holen
        full_serie_data = self.model.get_series_details_by_name(new_name)
        # 2. Im aktuellen Buch-Aggregat ersetzen
        if full_serie_data:
            self.current_book.serie = full_serie_data
            self.current_book.book.series_name = full_serie_data.name
        # 3. UI updaten (damit z.B. die Werk-Liste des Autors gefiltert wird)
        self.update_ui_lists()

    def _on_work_selected(self, event=None):
        """Wird aufgerufen, wenn ein Werk aus der Combobox gewählt wird."""
        selected_title = self.view.widgets['w_title'].get().strip()
        if not selected_title:
            return
        # 1. Details vom Model holen
        work_data = self.model.get_work_details_by_title(selected_title, self.current_book.authors)

        if work_data and work_data.id > 0:
            # 2. Das Werk-Atom im Manager ersetzen
            self.current_book.work = work_data
            # 3. WICHTIG: Die ID auch im Buch-Atom setzen für den DB-FK
            self.current_book.book.work_id = work_data.id
            # 4. Titel im Buch-Atom synchronisieren
            self.current_book.book.title = work_data.title
            # 5. UI aktualisieren
            self.view.fill_widgets(self.current_book)
            print(f"✅ Werk verknüpft: {work_data.title} (ID: {work_data.id})")

    # ----------------------------------------------------------------------
    # LADEN DER DATEN
    # ----------------------------------------------------------------------
    def load_from_file(self):
        """Lädt eine Datei und füllt die Navigationsliste mit allen E-Books des Verzeichnisses."""
        path = filedialog.askopenfilename(filetypes=[("E-Books", "*.epub *.pdf *.mobi")])
        if not path:
            return
        target_file = sanitize_path(path)
        directory = os.path.dirname(target_file)
        # Alle unterstützten Dateien im selben Ordner finden
        extensions = ('.epub', '.pdf', '.mobi')
        all_files = []
        try:
            for f in os.listdir(directory):
                if f.lower().endswith(extensions):
                    full_path = sanitize_path(os.path.join(directory, f))
                    all_files.append({'PATH': full_path})
            # Sortieren, damit die Navigation logisch ist (alphabetisch)
            all_files.sort(key=lambda x: x['PATH'].lower())
            self.navigation_list = all_files
            # Den Index der ursprünglich gewählten Datei finden
            try:
                self.current_index = next(i for i, item in enumerate(self.navigation_list)
                                          if item['PATH'] == target_file)
            except StopIteration:
                self.current_index = 0
            self.display_navigation_item(self.current_index)
        except Exception as e:
            messagebox.showerror("Fehler", f"Verzeichnis konnte nicht gelesen werden: {e}")

    def load_from_database(self, author, title):
        res = self.model.search_books_in_db(author, title)
        if res:
            self.navigation_list = [{'PATH': sanitize_path(p)} for p in res]
            self.display_navigation_item(0)

    def load_from_list(self, book_ids: List[int]):
        self.navigation_list = [{'ID': bid} for bid in book_ids]
        self.display_navigation_item(0)
        self.win.lift()


    def load_from_report_file(self):
        """Lädt den Text-Report und analysiert die Blöcke (V1.3)."""
        report_path = filedialog.askopenfilename(title="Report wählen", filetypes=[("Text", "*.txt")])
        if not report_path: return
        report_data = {}
        current_block = []

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines:
                line_s = line.strip()
                if line_s.startswith("---") or line_s.startswith("___"):
                    if current_block:
                        self._process_report_block(current_block, report_data)
                        current_block = []
                    continue
                if line_s:
                    current_block.append(line_s)

            if current_block:
                self._process_report_block(current_block, report_data)

            if report_data:
                # Wir wandeln die Keys ("ID:123" oder Pfad) in unsere Navigations-Struktur um
                self.navigation_list = []
                for key in report_data.keys():
                    if key.startswith("ID:"):
                        self.navigation_list.append({'ID': int(key.split(":")[1])})
                    else:
                        self.navigation_list.append({'PATH': key})

                self.mismatch_errors = report_data
                self.display_navigation_item(0)
            else:
                messagebox.showwarning("Fehler", "Keine gültigen Einträge im Report gefunden.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Ladefehler: {e}")

    def _process_report_block(self, block, data_dict):
        """Analysiert einen gesammelten Block auf ID, Pfad und Fehler (V1.3)."""
        found_id = None
        found_path = None
        errors = []

        for line in block:
            line_l = line.lower()
            if "buch-id:" in line_l or "id:" in line_l:
                found_id = line.split(":", 1)[1].strip()
            elif "pfad:" in line_l:
                p = line.split(":", 1)[1].strip()
                if p and p.lower() not in ["", "unbekannt", "bereits leer"]:
                    found_path = os.path.abspath(os.path.normpath(p))
            elif "❌" in line or "info:" in line_l or "note:" in line_l:
                errors.append(line)

        key = f"ID:{found_id}" if found_id else found_path
        if key and errors:
            data_dict[key] = "\n".join(errors)

    def load_navigation_data(self):
        updated_books = self.model.get_all_books()
        self.view.update_navigation_list(updated_books)

    # ----------------------------------------------------------------------
    # Anzeigen der DATEN
    # ----------------------------------------------------------------------
    def display_navigation_item(self, index: int):
        if not (0 <= index < len(self.navigation_list)):
            return
        self.current_index = index
        item = self.navigation_list[index]

        # 1. Buch-Daten laden
        if 'ID' in item:
            self.current_book = self.model.get_book_by_id(item['ID'])
        elif 'PATH' in item:
            self.current_book = self.model.get_book_by_path(item['PATH'])

        if self.current_book:
            # 1. Info für ComboBox-Listen vorbereiten
            # Wir laden die Listen basierend auf den Autoren des gerade geladenen Buchs
            author_list = getattr(self.current_book, 'authors', [])
            # Falls die DB keine Autoren liefert (AUTHORS: []), extrahieren wir aus dem Pfad
            if not author_list:
                # Extrahiert "Rowling" aus "J.K. Rowling — Harry Potter..."
                filename = os.path.basename(getattr(self.current_book.book, 'path', ""))
                if " — " in filename:
                    raw_author = filename.split(" — ")[0]
                    # Wir nehmen den letzten Teil als Nachnamen für die Suche
                    ln = raw_author.split(" ")[-1]
                    author_list = [('', ln)]
                    print(f"🔍 Backup-Suche: Nutze Nachname '{ln}' aus Dateiname.")
                # Bandnummer (Series Index) aus dem Pfad extrahieren (z.B. "07")

                path_str = getattr(self.current_book.book, 'path', "")
                match = re.search(r' (\d+)-', path_str)
                s_idx = int(match.group(1)) if match else None
                if s_idx:
                    self.current_book.book.series_index = s_idx  # Dem Atom zuweisen!

            self.current_book.all_available_series = self.current_book.get_prioritized_series(author_list)
            # Hier nutzen wir jetzt den neuen Filter (Autoren + Bandnummer)
            # Das liefert entweder genau das eine richtige Werk oder alle 50 als Backup
            self.current_book.all_available_works = self.current_book.get_works_by_authors(author_list,
                                                                                           series_index=s_idx)
            # 2. Pfade säubern
            self.current_file_path = sanitize_path(getattr(self.current_book.book, 'path', ""))
            # Falls es schon einen extrahierten Pfad in der DB gibt, nutzen wir ihn,
            # ansonsten muss die View aus der Quelldatei extrahieren.
            c_path = sanitize_path(getattr(self.current_book.book, 'cover_path', None))

            # 3. View füllen & On-the-fly Extraktion triggern
            self.view.fill_widgets(self.current_book)

            # Hier passiert die Magie: View extrahiert aus self.current_file_path
            self.view.display_cover(c_path, self.current_file_path)

            # 4. Bild-Referenz "festkrallen"
            # Wir holen das on-the-fly erzeugte Bild aus der View
            if hasattr(self.view, 'tk_img') and self.view.tk_img:
                self._img_keep_alive = self.view.tk_img
                # Zwinge das Label zur Anzeige des neuen Objekts
                if hasattr(self.view, 'cover_label'):
                    self.view.cover_label.config(image=self._img_keep_alive)
                    # Interner Python-Trick: Referenz direkt am Widget speichern
                    self.view.cover_label.image = self._img_keep_alive
            self._update_navigation_status()

    def _update_navigation_status(self):
        total = len(self.navigation_list)
        curr = self.current_index + 1
        self.view.update_status(curr, total, self.current_file_path)
        # --- NEU: FARB-LOGIK ANWENDEN ---
        if self.current_book:
            # Die Entscheidungsgewalt liegt hier beim Controller
            if not self.current_book.is_in_db:
                color = "#E1F5FE"  # Hellblau (Neu/Scan)
            elif self.current_book.is_dirty:
                color = "#FFF9C4"  # Hellgelb (Änderung/Rescan)
            else:
                color = "#C8E6C9"  # Hellgrün (Synchron)

            # Wir sagen der View, welche Zeile wie eingefärbt werden soll
            self.view.set_navigation_item_color(color)

    # ----------------------------------------------------------------------
    # SaVE DATEN
    # ----------------------------------------------------------------------
    def save_data(self):
        if not self.current_book: return
        # 1. Daten aus der GUI in das Objekt übertragen
        self.current_book = self.view.get_data_from_widgets(self.current_book)
        print("\n--- 🖥️ UI -> MODEL ÜBERGABE CHECK ---")
        mgr = self.current_book
        print(f"PFAD:      {self.current_file_path}")
        print(f"AUTOREN:   {mgr.book.authors}")
        print(f"SERIE:     {mgr.serie.name}")
        print(f"SERIE-DE:  {getattr(mgr.serie, 'name_de', 'MISSING')}")
        print(f"SERIE-FR:  {getattr(mgr.serie, 'name_fr', 'MISSING')}")
        print(f"WORK-DESC: {mgr.work.description[:30] if mgr.work.description else 'LEER'}...")
        print(f"WORK-KEYS: {mgr.work.keywords}")
        print("--------------------------------------\n")
        # --- DEBUG ENDE ---


        # 2. Speichern via Model
        print(f"DEBUG BROWSER: self.current_file_path = '{self.current_file_path}'")
        print(f"DEBUG BROWSER: self.current_book.book.path = '{self.current_book.book.path}'")
        success, final_path = self.model.save_book(self.current_book, self.current_file_path)
        if success:
            # 3. Den Pfad im Speicher aktualisieren, falls er sich beim Verschieben geändert hat
            if final_path:
                self.current_file_path = sanitize_path(final_path)
                self.current_book.path = self.current_file_path
                # WICHTIG: Auch den Pfad im Navigation-Item aktualisieren!
                if 'PATH' in self.navigation_list[self.current_index]:
                    self.navigation_list[self.current_index]['PATH'] = self.current_file_path
            # 4. den Status aktualisieren
            self.current_book.is_in_db = True
            self.current_book.capture_db_state()  # Der Arbeitsstand ist jetzt der neue DB-Stand
            # 5. Das UI-Element in der Navigation aktualisieren
            self.display_navigation_item(self.current_index)  # Zeichnet die Zeile neu (jetzt GRÜN)
            print(f"✅ Erfolgreich gespeichert: {os.path.basename(self.current_file_path)}")
        else:
            messagebox.showerror("Fehler", f"Speichern fehlgeschlagen: {final_path}")


    # ----------------------------------------------------------------------
    # LÖSCHEN eines BUCHES
    # ----------------------------------------------------------------------
    def delete_current_book(self):
        if self.current_book and self.model.delete_book(self.current_book):
            messagebox.showinfo("Löschen", "Buch wurde entfernt.")
            # Nach dem Löschen zum nächsten springen oder Liste leeren
            self.display_navigation_item(self.current_index)


if __name__ == "__main__":
    root = tk.Tk()
    app = BookBrowser(root)
    root.mainloop()