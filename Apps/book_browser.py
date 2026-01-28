"""
DATEI: book_browser.py
PROJEKT: MyBook-Management (v1.3.0)
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
              browser_view_old.py	=	Die Maske: Zeichnet alles und fängt Benutzereingaben ab.
              browser_model.py	=	Das Gehirn: Muss die Methoden aggregate_book_data und save_book enthalten.
"""

import os
import platform
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, List, Optional, Dict  # Any ist das Wichtigste für deinen Fehler

from Apps.book_data import BookData
from Gemini.browser_view_old import BrowserView
from Gemini.browser_model import BrowserModel
from Gemini.file_utils import DB_PATH



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
        # self.current_book_data = None
        self.current_book_data: Optional['BookData'] = None
        self.mismatch_errors = {}

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

    def load_data(self, identifier):
        if not identifier: return

        # 1. Buch laden (Model nutzt jetzt Fuzzy-Suche/Messer schärfen)
        book_obj = self.model.aggregate_book_data(identifier)

        # 2. Index & Report-Info (wie gehabt)
        if identifier in self.navigation_list:
            self.current_index = self.navigation_list.index(identifier)

        report_info = self.mismatch_errors.get(identifier, "") if hasattr(self, 'mismatch_errors') else ""

        if not book_obj:
            # FEHLERFALL (Dummy Objekt wie gehabt)
            display_obj = BookData(title="DATEI NICHT LADBAR / KORRUPT", path=identifier)
            display_obj.notes = f"⚠️ REPORT-INFO:\n{report_info}"
            self.view.fill_widgets(display_obj)
            self.view.update_status(self.current_index + 1, len(self.navigation_list), f"FEHLER: {identifier}",
                                    is_magic=False)
        else:
            # MAGIC CHECK: Pfade vergleichen
            is_magic = False
            if not str(identifier).startswith("ID:"):
                norm_id = os.path.normpath(identifier).lower()
                norm_found = os.path.normpath(book_obj.path).lower()
                if norm_id != norm_found:
                    is_magic = True

            # WICHTIG: Notizen mit Magic-Info anreichern (dein Report-Block)
            if is_magic or report_info:
                header = "⚠️ HINWEISE ZUM BUCH:\n"
                if is_magic:
                    header += f"✨ MAGIC: Pfad korrigiert!\nGesucht: {identifier}\nGefunden: {book_obj.path}\n\n"
                if report_info:
                    header += f"REPORT: {report_info}\n"
                book_obj.notes = f"{header}{'-' * 30}\n{book_obj.notes or ''}"

            # DATEN ÜBERNEHMEN
            self.current_book_data = book_obj
            self.current_file_path = book_obj.path  # Das ist jetzt der ECHTE Pfad auf Disk!

            # VIEW AKTUALISIEREN
            self.view.fill_widgets(self.current_book_data)

            # Pfad-Feld auf Orange/Gelb schalten und den ECHTEN Pfad anzeigen
            self.view.update_status(
                self.current_index + 1,
                len(self.navigation_list),
                book_obj.path,  # <--- Hier den gefundenen Pfad anzeigen!
                is_magic=is_magic
            )


            # COVER ANZEIGEN (Nutzt jetzt den geheilten self.current_file_path)
            self.view.display_cover(getattr(book_obj, 'cover_path', None), self.current_file_path)

    # ----------------------------------------------------------------------
    # 3. Laden des Reports
    # ----------------------------------------------------------------------
    def load_mismatch_report(self):
        report_path = filedialog.askopenfilename(title="Report wählen", filetypes=[("Text", "*.txt")])
        if not report_path: return
        report_data = {}
        current_block = []

        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines:
                line_s = line.strip()
                # Trenner markiert das Ende eines Blocks
                if line_s.startswith("---") or line_s.startswith("___"):
                    if current_block:
                        self._process_report_block(current_block, report_data)
                        current_block = []
                    continue
                if line_s:
                    current_block.append(line_s)

            # Letzten Block nicht vergessen
            if current_block:
                self._process_report_block(current_block, report_data)

            if report_data:
                self.navigation_list = list(report_data.keys())
                self.mismatch_errors = report_data
                self.current_index = 0
                first_item = self.navigation_list[0]
                print(f"DEBUG: Versuche ersten Eintrag anzuzeigen: {first_item}")
                try:
                    self.load_data(first_item)
                except Exception as e:
                    print(f"⚠️ Erster Eintrag konnte nicht angezeigt werden: {e}")
            else:  # <--- DIESES ELSE GEHÖRT ZU 'if report_data:'
                messagebox.showwarning("Fehler", "Keine gültigen Einträge im Report gefunden.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Ladefehler: {e}")

    def _process_report_block(self, block, data_dict):
        """Analysiert einen gesammelten Block auf ID, Pfad und Fehler."""
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

        # Priorität: Wenn wir eine ID haben, nutzen wir "ID:xxx" als Key
        # Wenn nicht, den Pfad. So finden wir das Buch immer.
        key = f"ID:{found_id}" if found_id else found_path
        if key and errors:
            data_dict[key] = "\n".join(errors)

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
            # Holt sich den Fokus auf den Browser nach 100 millisekunden zurück, wenn alles erledigt ist.
            self.win.after(100, self.win.focus_force)
        else:
            messagebox.showerror("Fehler", "Speichern fehlgeschlagen.")

    def delete_current_book(self):
        if not self.navigation_list:
            return

        current_identifier = self.navigation_list[self.current_index]

        if not messagebox.askyesno("Löschen", f"Eintrag aus Datenbank entfernen?\n\n{current_identifier}"):
            return

        # 1. Lösch-Versuch (Objekt-ID hat Priorität, sonst Identifier)
        success = False
        if self.current_book_data and hasattr(self.current_book_data, 'id'):
            success = self.model.delete_book(self.current_book_data)
        else:
            # Fallback für "Adam J. Dalton" (Datei fehlt)
            if current_identifier.startswith("ID:"):
                clean_id = current_identifier.replace("ID:", "").strip()
                success = self.model.delete_book_by_id(clean_id)
            else:
                success = self.model.delete_book_by_path(current_identifier)

        if success:
            # 2. Aus der Liste entfernen
            self.navigation_list.pop(self.current_index)

            # 3. ANZEIGE AKTUALISIEREN
            if self.navigation_list:
                # Index korrigieren, falls wir am Ende der Liste waren
                if self.current_index >= len(self.navigation_list):
                    self.current_index = len(self.navigation_list) - 1

                # Das NÄCHSTE Buch in der Liste laden
                new_identifier = self.navigation_list[self.current_index]
                self.load_data(new_identifier)

                # Explizites Update der Statuszeile (z. B. "1 von 4705")
                self.view.update_status(
                    self.current_index + 1,
                    len(self.navigation_list),
                    new_identifier
                )
            else:
                # Wenn die Liste jetzt komplett leer ist
                self.current_book_data = None
                self.view.clear_fields()  # Methode in deiner View, die alle Entrys/Labels leert
                self.view.update_status(0, 0, "Keine Einträge vorhanden")
                messagebox.showinfo("Info", "Alle Mismatches abgearbeitet!")
        else:
            messagebox.showerror("Fehler", "Löschen fehlgeschlagen. Eintrag nicht gefunden.")


    def on_close(self):
        """Aufräumen beim Beenden."""
        # self.model.cleanup_temp_files()
        self.win.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = BookBrowser(root)
    root.mainloop()