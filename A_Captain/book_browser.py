"""
DATEI: A_Captain/book_browser_app.py
BESCHREIBUNG:
    Der Haupt-Controller für den Buch-Browser.
    Verbindet die View (D_Navigation) mit der Logik (Bridge/Manager).
"""
import os
import tkinter as tk
import logging
from tkinter import messagebox, filedialog
from typing import List
from D_Navigation.book_view import BookView
from Bridge.book_manager import BookManager


# from Pille.browser_view import BrowserView <--- Bleibt gleich

class BookBrowser:
    def __init__(self, win, initial_list=None):
        self.win = win
        self.manager = BookManager()
        # Die View wird jetzt aus dem D_Navigation-Sektor geladen
        self.view = BookView(self.win)

        self.navigation_list = initial_list if initial_list else []
        self.current_index = 0
        self.current_book = None
        self.current_file_path = ""
        self._img_keep_alive = None

        # Initialisierung
        self.create_menu()
        self._bind_view_actions()

        if self.navigation_list:
            self.display_navigation_item(0)

    # ----------------------------------------------------------------------
    # MENÜ & NAVIGATION
    # ----------------------------------------------------------------------
    def create_menu(self):
        menubar = tk.Menu(self.win)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="📁 Datei laden", command=self.load_from_file)
        file_menu.add_command(label="🔍 DB Suche",
                              command=lambda: self.view.show_search_popup(self.load_from_database))
        file_menu.add_separator()
        file_menu.add_command(label="📋 Report laden", command=self.load_from_report_file)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.win.quit)
        menubar.add_cascade(label="Datei", menu=file_menu)
        self.win.config(menu=menubar)

    def _bind_view_actions(self):
        """Verknüpft Buttons und Events der View mit Controller-Methoden."""
        self.view.create_nav_buttons(self)

        # Bindings für Comboboxen & Fokus-Events
        if 's_name' in self.view.widgets:
            self.view.widgets['s_name'].bind("<<ComboboxSelected>>", self._on_series_selected)
        if 'w_title' in self.view.widgets:
            self.view.widgets['w_title'].bind("<<ComboboxSelected>>", self._on_work_selected)
        if 'authors' in self.view.widgets:
            self.view.widgets['authors'].bind("<FocusOut>", lambda e: self.update_ui_lists())
        if 'b_series_name' in self.view.widgets:
            self.view.widgets['b_series_name'].bind("<FocusOut>", lambda e: self.re_evaluate_fingerprint())
        if 'b_series_index' in self.view.widgets:
            self.view.widgets['b_series_index'].bind("<FocusOut>", lambda e: self.re_evaluate_fingerprint())

    # ----------------------------------------------------------------------
    # NAV-HELFER
    # ----------------------------------------------------------------------
    def nav_next(self): self.display_navigation_item(self.current_index + 1)
    def nav_prev(self): self.display_navigation_item(self.current_index - 1)
    def nav_first(self): self.display_navigation_item(0)
    def nav_last(self): self.display_navigation_item(len(self.navigation_list) - 1)

    def _on_series_selected(self, event=None):
        new_name = self.view.widgets['b_series_name'].get()
        if not new_name: return
        data = self.model.get_series_details_by_name(new_name)
        if data:
            self.current_book.serie = data
            self.current_book.book.series_name = data.name
        self.update_ui_lists()

    def _on_work_selected(self, event=None):
        selected_title = self.view.widgets['w_title'].get().strip()
        if not selected_title: return
        work_data = self.model.get_work_details_by_title(selected_title, self.current_book.book.authors)
        if work_data and work_data.id > 0:
            self.current_book.work = work_data
            self.current_book.book.work_id = work_data.id
            self.current_book.book.title = work_data.title
            self.view.fill_widgets(self.current_book)


    # ----------------------------------------------------------------------
    # EXTERNE LOADER (REPORT, DB, FILE)
    # ----------------------------------------------------------------------
    def load_from_database(self, author="", title=""):
        # ... Suche wird ausgeführt ...
        found_paths = self.manager.search_db(author, title)

        if found_paths:
            # Wir müssen die Pfade in das Format bringen, das display_navigation_item erwartet
            self.navigation_list = [{'PATH': p} for p in found_paths]
            self.current_index = 0
            # Rufe direkt die neue Methode auf:
            self.display_navigation_item(0)

    def load_from_file(self):
        target_file = filedialog.askopenfilename(filetypes=[("E-Books", "*.epub *.pdf *.mobi")])
        if not target_file: return
        directory = os.path.dirname(target_file)
        exts = ('.epub', '.pdf', '.mobi')
        all_files = []
        try:
            for f in os.listdir(directory):
                if f.lower().endswith(exts):
                    all_files.append({'PATH': os.path.join(directory, f)})
            all_files.sort(key=lambda x: x['PATH'].lower())
            self.navigation_list = all_files
            self.current_index = next((i for i, item in enumerate(all_files) if item['PATH'] == target_file), 0)
            self.display_navigation_item(self.current_index)
        except Exception as e:
            messagebox.showerror("Fehler", f"Verzeichnis-Ladefehler: {e}")

    def load_from_list(self, book_ids: List[int]):
        """
        Wichtig: Diese Methode fehlte und verursachte den Abbruch!
        Sie konvertiert die IDs vom Serienbrowser in die Navigationsliste.
        """
        if not book_ids:
            return
        # 1. Navigationsliste erstellen
        self.navigation_list = [{'ID': bid} for bid in book_ids]
        self.current_index = 0

        # 2. Das erste Buch laden und anzeigen. Dies ruft intern self.model.get_book_by_id auf
        self.display_navigation_item(0)

        # 3. Fenster aktualisieren
        self.win.lift()
        self.win.focus_force()

    def load_from_report_file(self):
        report_path = filedialog.askopenfilename(title="Report wählen", filetypes=[("Text", "*.txt")])
        if not report_path: return
        report_data = {}
        current_block = []
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("---") or line.startswith("___"):
                        if current_block:
                            self._process_report_block(current_block, report_data)
                            current_block = []
                        continue
                    if line.strip(): current_block.append(line.strip())
            if current_block: self._process_report_block(current_block, report_data)

            if report_data:
                self.navigation_list = []
                for key in report_data.keys():
                    if key.startswith("ID:"):
                        self.navigation_list.append({'ID': int(key.split(":")[1])})
                    else:
                        self.navigation_list.append({'PATH': key})
                self.display_navigation_item(0)
        except Exception as e:
            messagebox.showerror("Fehler", f"Report-Ladefehler: {e}")

    def _process_report_block(self, block, data_dict):
        found_id, found_path, errors = None, None, []
        for line in block:
            l = line.lower()
            if "id:" in l: found_id = line.split(":", 1)[1].strip()
            elif "pfad:" in l: found_path = os.path.abspath(os.path.normpath(line.split(":", 1)[1].strip()))
            elif "❌" in line or "info:" in l or "note:" in l: errors.append(line)
        key = f"ID:{found_id}" if found_id else found_path
        if key and errors: data_dict[key] = "\n".join(errors)

    # ----------------------------------------------------------------------
    # DISPLAY-ANZEIGE
    # ----------------------------------------------------------------------
    def display_navigation_item(self, index: int):
        if not (0 <= index < len(self.navigation_list)): return
        self.current_index = index
        item = self.navigation_list[index]

        # Wir lassen den Manager entscheiden, wie er das Buch lädt (DB oder Scan)
        path = item.get('PATH')
        book_id = item.get('ID')

        if book_id:
            self.current_core = self.manager.get_book_by_id(book_id)
        elif path:
            self.current_core = self.manager.get_book_by_path(path)

        logging.debug(self.current_core)
        print(f" Debug: Genre = {self.current_core.book.genre}")

        if self.current_core:
            # Die View befüllen wir jetzt direkt aus dem Core-Aggregat
            self.view.fill_widgets(self.current_core)

            # Cover-Anzeige via Scotty
            c_path = self.current_core.book.path
            self.view.display_cover(None, c_path)  # Scotty extrahiert Cover intern

            self._update_navigation_status()

    # ----------------------------------------------------------------------
    # DATEN-LOGIK & SYNC
    # ----------------------------------------------------------------------
    def update_ui_lists(self):
        """Aktualisiert die Auswahl-Listen (Serien/Werke) basierend auf den aktuellen Autoren."""
        if not self.current_book: return
        author_list = self.current_book.book.authors
        self.current_book.all_available_series = self.current_book.get_prioritized_series(author_list)

        # Werk-Match via Fingerprint prüfen
        suggested_work_id = self.current_book.find_work_by_series_fingerprint(self.current_book)
        if suggested_work_id:
            self.current_book.load_work_into_manager(suggested_work_id)
            self.current_book.book.work_id = suggested_work_id

        self.current_book.all_available_works = self.current_book.get_works_by_authors(author_list)
        self.view.fill_widgets(self.current_book)

    def re_evaluate_fingerprint(self, event=None):
        """Prüft bei Änderungen an Serie/Index, ob ein passendes Werk existiert."""
        if not self.current_book: return
        self.view.get_data_from_widgets(self.current_book)
        found_id = self.current_book.find_work_by_series_fingerprint(self.current_book)

        if found_id:
            self.current_book.work.id = found_id
            print(f"✨ Automatische Zuordnung: Werk ID {found_id} erkannt.")

        self.update_ui_lists()


    def _update_navigation_status(self):
        """Nutzt die Status-Logik des Cores für die Farben."""
        total = len(self.navigation_list)
        curr = self.current_index + 1
        path = self.current_core.book.path if self.current_core else ""
        self.view.update_status(curr, total, path)

        if self.current_core:
            # Die Farbe kommt jetzt aus dem Core-Status
            if not self.current_core.is_in_db:
                color = "#E1F5FE"  # Blau: Neu
            elif self.current_core.is_dirty():  # Eine neue Methode im Core!
                color = "#FFF9C4"  # Gelb: Geändert
            else:
                color = "#C8E6C9"  # Grün: Synchron
            self.view.set_navigation_item_color(color)


    # ----------------------------------------------------------------------
    # SPEICHERN (Delegation an Manager)
    # ----------------------------------------------------------------------
    def save_data(self):
        # 1. View -> Core (Daten sammeln)
        core = self.view.get_data_from_widgets(self.manager.current_core)

        # 2. Manager rufen (Der koordiniert Datei & DB)
        if self.manager.save_current_state(core):
            print("🖖 A_Captain: Logbuch aktualisiert. Speichern erfolgreich.")

    def delete_current_book(self):
        if not self.current_book: return
        if not messagebox.askyesno("Löschen", "Buch wirklich löschen?", parent=self.win):
            return
        try:
            self.current_book.delete_book()
            self.navigation_list.pop(self.current_index)
            if not self.navigation_list:
                self.win.destroy()
                return
            if self.current_index >= len(self.navigation_list):
                self.current_index = len(self.navigation_list) - 1
            self.display_navigation_item(self.current_index)
            self.win.focus_force()
        except Exception as e:
            messagebox.showerror("Fehler", f"Löschen fehlgeschlagen: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    # Der A_Captain betritt die Brücke
    app = BookBrowser(root)

    # Das hier ist der "Haltebefehl" – ohne das schließt sich das Fenster sofort
    root.mainloop()