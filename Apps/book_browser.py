"""
DATEI: book_browser.py
PROJEKT: MyBook-Management (v1.2.0)
BESCHREIBUNG: Ermöglicht das Navigieren, editieren und löschen von Büchern.
              Die Buchliste (Liste von absoluten File-paths) steht in einer Navigationsliste. Sie kann aus
                a) dem Filesystem kommen (alle Files eines Ordners)
                b) der Datenbank kommen (alle Resultate eines SQL-Search zum Autor)
                c) dem Missmatch Report (alle Files aus dem Report werden eingelesen, das Problem in Notes ausgegeben)
                d) aus der Selektion oder View im Book-Analyser (Selektion im Treeview)
              Beim Ändern, wird die Datenbank und der Filename im Filesystem geändert.
              Beim Ändern der Autoren, bleiben möglicherweise verwaiste Autoren zurück.
              Refaktoriert in Version 1.2:
              book_browser.py	=	Der Controller: Steuert den Flow (Laden -> Navigieren -> Speichern).
              browser_view.py	=	Die Maske: Zeichnet alles und fängt Benutzereingaben ab.
              browser_model.py	=	Das Gehirn: Muss die Methoden aggregate_book_data und save_book enthalten.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

# Pfade setzen (Apps -> Gemini)
MODULES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Gemini'))
sys.path.append(MODULES_DIR)

try:
    from browser_view import BrowserView
    from browser_model import BrowserModel
    from book_data import BookData
except ImportError as e:
    print(f"Fehler beim Modul-Import: {e}")

DB_PATH = r'M://books.db'


class BookBrowser:
    # ----------------------------------------------------------------------
    # 1. INITIALISIERUNG
    # ----------------------------------------------------------------------
    def __init__(self, win, initial_list=None):
        self.win = win

        # Model & View initialisieren
        self.model = BrowserModel(DB_PATH)
        self.view = BrowserView(self.win)

        # Status-Variablen
        self.navigation_list = initial_list if initial_list else []
        self.current_index = 0
        self.current_file_path = None

        # Verknüpfung: Buttons & Menü
        self.view.create_nav_buttons(self)
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)
        self.create_menu()

        # Start-Daten laden
        if self.navigation_list:
            self.load_data(self.navigation_list[0])

    def create_menu(self):
        menubar = tk.Menu(self.win)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="E-Book öffnen...", command=self.open_file)
        file_menu.add_command(label="Buch in DB suchen...", command=self.open_search_dialog)
        file_menu.add_separator()
        file_menu.add_command(label="Mismatch-Report laden...", command=self.load_mismatch_report)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.on_close)
        menubar.add_cascade(label="Datei", menu=file_menu)
        self.win.config(menu=menubar)

    # ----------------------------------------------------------------------
    # 2. LADEN VON DATEN
    # ----------------------------------------------------------------------
    def open_file(self):
        """Öffnet ein E-Book und lädt alle anderen Bücher im selben Verzeichnis in die Navigation."""
        path = filedialog.askopenfilename(filetypes=[("E-Books", "*.epub *.pdf")])
        if not path:
            return

        path = os.path.abspath(os.path.normpath(path))
        directory = os.path.dirname(path)
        # 1. Alle unterstützten Dateien im selben Ordner finden
        extensions = ('.epub', '.pdf')
        all_files = [
            os.path.abspath(os.path.normpath(os.path.join(directory, f)))
            for f in os.listdir(directory)
            if f.lower().endswith(extensions)
        ]
        # 2. Sortieren (optional, aber sinnvoll für die gewohnte Reihenfolge)
        all_files.sort()
        # 3. Navigation aktualisieren
        self.navigation_list = all_files
        # 4. Den Index des ausgewählten Buches finden und laden
        if path in self.navigation_list:
            self.current_index = self.navigation_list.index(path)
        self.load_data(path)

    def load_data(self, file_path):
        """Koordiniert den Datenfluss vom Model zur View."""
        if not file_path: return
        # Normierung der Pfade: normpath = "/" für alle OS D:/Bücher/buch.epub
        self.current_file_path = os.path.abspath(os.path.normpath(file_path))

        # A. Model: Daten aggregieren
        self.current_book_data = self.model.aggregate_book_data(self.current_file_path)
        # B. Controller: Navigation tracken
        if self.current_file_path in self.navigation_list:
            self.current_index = self.navigation_list.index(self.current_file_path)
        # C. View: Alles anzeigen
        self.view.fill_widgets(self.current_book_data)
        self.view.display_cover(self.current_book_data.image_path, self.current_file_path)
        self.view.update_status(self.current_index + 1, len(self.navigation_list), self.current_file_path)

    def load_mismatch_report(self):
        """Liest den Report ein und sammelt alle Fehlerzeilen pro Pfad."""
        report_path = filedialog.askopenfilename(
            title="Mismatch Report wählen",
            filetypes=[("Textdateien", "*.txt")]
        )
        if not report_path:
            return
        report_data = {}  # { pfad: "Fehlerliste" }
        current_path = None
        current_errors = []

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line_stripped = line.strip()
                    if not line_stripped:
                        continue
                    # 1. Neuer Pfad beginnt
                    if line_stripped.lower().startswith("pfad:"):
                        # Vorherigen Pfad speichern, falls vorhanden
                        if current_path and current_errors:
                            report_data[current_path] = "\n".join(current_errors)
                        # Neuen Pfad extrahieren & normalisieren
                        raw_path = line_stripped.split(":", 1)[1].strip()
                        current_path = os.path.abspath(os.path.normpath(raw_path))
                        current_errors = []
                        continue
                    # 2. Fehlerzeilen sammeln (alles mit dem ❌ oder 'Autor/Titel')
                    if current_path and ("❌" in line_stripped or "vs." in line_stripped):
                        current_errors.append(line_stripped)
                # Letzten Eintrag nach dem Loop speichern
                if current_path and current_errors:
                    report_data[current_path] = "\n".join(current_errors)

            if report_data:
                # WICHTIG: Navigation komplett neu aufsetzen
                self.navigation_list = list(report_data.keys())
                self.mismatch_errors = report_data  # Dictionary für die load_data Methode
                self.current_index = 0
                # Jetzt das erste Buch laden
                self.load_data(self.navigation_list[0])
                messagebox.showinfo("Erfolg", f"{len(self.navigation_list)} Bücher mit Fehlern geladen.")
            else:
                messagebox.showwarning("Fehler", "Keine Einträge gefunden. Stimmen die Pfade?")

        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Parsen: {e}")

    # ----------------------------------------------------------------------
    # 3. SUCH-LOGIK
    # ----------------------------------------------------------------------
    def open_search_dialog(self):
        """Öffnet das Such-Fenster der View."""
        self.view.show_search_popup(self.perform_search)

    def perform_search(self, author_query, title_query):
        """Verarbeitet das Suchergebnis und baut die Navigation neu auf."""
        if not author_query and not title_query: return

        results = self.model.search_books_in_db(author_query, title_query)
        if not results:
            messagebox.showinfo("Suche", "Keine Bücher gefunden.")
            return
        self.navigation_list = results
        self.current_index = 0
        self.load_data(self.navigation_list[0])

    # ----------------------------------------------------------------------
    # 4. NAVIGATIONS-LOGIK
    # ----------------------------------------------------------------------
    def nav_next(self):
        if self.navigation_list and self.current_index < len(self.navigation_list) - 1:
            self.load_data(self.navigation_list[self.current_index + 1])

    def nav_prev(self):
        if self.navigation_list and self.current_index > 0:
            self.load_data(self.navigation_list[self.current_index - 1])

    def nav_first(self):
        if self.navigation_list: self.load_data(self.navigation_list[0])

    def nav_last(self):
        if self.navigation_list: self.load_data(self.navigation_list[-1])

    # ----------------------------------------------------------------------
    # 5. SPEICHERN / LÖSCHEN / SCHLIESSEN
    # ----------------------------------------------------------------------
    def save_data(self):
        """Sammelt Daten der View und lässt Model speichern."""
        updated_data = self.view.get_data_from_widgets()
        print("--- DEBUG CONTROLLER: DATEN AUS WIDGETS ---")
        print(f"Pfad (current): {repr(self.current_file_path)}")
        print(f"Titel:         {repr(updated_data.title)}")
        print(f"Sprache:       {repr(updated_data.language)}")
        print(f"Manual Desc?:  {updated_data.is_manual_description}")
        print(f"Autoren:       {repr(updated_data.authors)}")
        desc_snippet = updated_data.description[:50].replace('\n', ' ') if updated_data.description else "LEER"
        print(f"Beschreibung:  {repr(desc_snippet)}...")
        print("-------------------------------------------")


        old_path = self.current_file_path
        if self.current_book_data:
            # DIE ID IST DER SCHLÜSSEL:
            updated_data.id = self.current_book_data.id
            if updated_data.description != self.current_book_data.description:
                updated_data.is_manual_description = 1
                print("DEBUG: is_manual_description wurde auf 1 gesetzt (Änderung erkannt)")

        success, new_path = self.model.save_book(updated_data, old_path)
        # Aktualisiert die Navigation Liste
        if success:
            if new_path != old_path:
                if old_path in self.navigation_list:
                    idx = self.navigation_list.index(old_path)
                    self.navigation_list[idx] = new_path
                self.current_file_path = new_path

            messagebox.showinfo("Erfolg", "Daten gespeichert.")
            # WICHTIG: Nicht neu einlesen! Einfach zum nächsten Index springen
            self.nav_next()
        else:
            messagebox.showerror("Fehler", "Speichern fehlgeschlagen.")

    def delete_current_book(self):
        if not self.current_book_data: return

        if messagebox.askyesno("Löschen", "Soll dieses Buch aus der Datenbank gelöscht werden?"):
            # Wir übergeben das Objekt, damit das Model die ID hat
            success = self.model.delete_book(self.current_book_data)

            if success:
                path = self.current_book_data.path
                if path in self.navigation_list:
                    self.navigation_list.remove(path)

                if self.navigation_list:
                    # Index korrigieren und neu laden
                    self.current_index = min(self.current_index, len(self.navigation_list) - 1)
                    self.load_current_book()  # Nutze deine bestehende Lade-Funktion
                else:
                    self.view.clear_fields()  # View leeren, wenn nichts mehr da ist
                    messagebox.showinfo("Info", "Liste ist jetzt leer.")

    def on_close(self):
        """Aufräumen beim Beenden."""
        self.model.cleanup_temp_files()
        self.win.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = BookBrowser(root)
    root.mainloop()