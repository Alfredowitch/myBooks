"""
DATEI: browser_model.py
PROJEKT: MyBook-Management (v1.3.0)
BESCHREIBUNG: Kümmert sich um die Daten von der Book_Browser App.
              book_browser.py	=	Der Controller: Steuert den Flow (Laden -> Navigieren -> Speichern).
              browser_view_old.py	=	Die Maske: Zeichnet alles und fängt Benutzereingaben ab.
              browser_model.py	=	Das Gehirn: Muss die Methoden aggregate_book_data und save_book enthalten.
"""
import os
import shutil
import difflib
from tkinter import filedialog
from typing import List

# --- Importe deiner spezialisierten Module ---
try:
    from Apps.book_data import BookData
    from Apps.book_scanner import scan_single_book
    from Apps.book_data import BookData
    from Gemini.file_utils import build_perfect_filename, sanitize_path

except ImportError as e:
    print(f"WARNUNG: Ein Untermodul im Model konnte nicht geladen werden: {e}")


class BrowserModel:
    def __init__(self, db_path: str = None):
        # db_path wird meist global in BookData gehandhabt,nur für Testzwecke hier
        pass

    # ----------------------------------------------------------------------
    # DATEN-AGGREGATION
    # ----------------------------------------------------------------------
    import os
    import difflib
    from tkinter import filedialog

    def aggregate_book_data(self, report_path):
        """
        Stufe 1: Das Beste annehmen (Exakter Treffer).
        Stufe 2: Messer schärfen (Fuzzy-Suche / Endungen).
        Stufe 3: Der Mensch hilft (FileDialog).
        """
        # --- STUFE 1: Der Idealfall ---
        if os.path.exists(report_path):
            book = BookData.load_by_path(report_path)
            if book: return book
            # Datei da, aber nicht in DB? Dann scannen.
            return scan_single_book(report_path)

        # --- STUFE 2: Automatischer Rettungsversuch ---
        print(f"🔍 Suche Alternative für: {os.path.basename(report_path)}")
        directory = os.path.dirname(report_path)

        if os.path.exists(directory):
            files_in_dir = os.listdir(directory)
            filename = os.path.basename(report_path)

            # Fuzzy Matching für Tippfehler, Bindestriche, Punkte und Endungen
            matches = difflib.get_close_matches(filename, files_in_dir, n=1, cutoff=0.7)
            if matches:
                alternative_path = os.path.join(directory, matches[0])
                print(f"✅ Treffer durch Automatik: {matches[0]}")
                return self._load_or_scan(alternative_path, report_path)

        # --- STUFE 3: Manuelle Hilfe ---
        print(f"⚠️ Nichts gefunden. Bitte Datei manuell wählen...")
        manual_path = filedialog.askopenfilename(
            initialdir=directory if os.path.exists(directory) else None,
            title=f"Datei suchen: {os.path.basename(report_path)}",
            filetypes=[("E-Books", "*.epub *.pdf *.mobi *.azw3")]
        )

        if manual_path:
            manual_path = os.path.abspath(os.path.normpath(manual_path))
            return self._load_or_scan(manual_path, report_path)

        return None

    def _load_or_scan(self, found_path, original_report_path):
        """Hilfsfunktion: Prüft DB nach neuem Pfad ODER altem Pfad."""
        # Schauen, ob die Datei unter dem GEFUNDENEN Namen in der DB steht
        book = BookData.load_by_path(found_path)
        if not book:
            # Schauen, ob sie unter dem ALTEN (kaputten) Namen in der DB steht
            book = BookData.load_by_path(original_report_path)
            if book:
                # Heilung: DB-Eintrag existiert, hat aber den falschen Pfad
                book.path = found_path
                print(f"ℹ️ DB-Eintrag auf neuen Pfad umgebogen.")

        if not book:
            # Völlig neu
            book = scan_single_book(found_path)

        return book

    # ----------------------------------------------------------------------
    # SUCHE & NAVIGATION
    # ----------------------------------------------------------------------
    def search_books_in_db(self, author: str, title: str) -> List[str]:
        results = BookData.search(author, title)
        return [sanitize_path(b['file_path']) for b in results if b.get('file_path')]

    def parse_mismatch_report(self, report_path: str) -> List[str]:
        """Extrahiert Dateipfade aus einem Mismatch-Report (txt)."""
        paths = []
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if "pfad:" in line.lower():
                        path = line.split(":", 1)[1].strip()
                        path = os.path.abspath(os.path.normpath(path))
                        if os.path.exists(path):
                            paths.append(path)
        except Exception as e:
            print(f"Fehler beim Parsen des Reports: {e}")
        return paths

    # ----------------------------------------------------------------------
    # SPEICHERN & DATEISYSTEM
    # ----------------------------------------------------------------------
    def save_book(self, data: BookData, old_path_from_controller: str) -> tuple[bool, str]:
        """Koordiniert Umbenennung des Files im Filesystem und stößt die DB-Update mit stabilem Anker an."""
        try:
            # Wir vertrauen dem Pfad, den der Controller uns als "Original" gibt
            old_path = sanitize_path(old_path_from_controller)
            # 1. Zentraler Zusammenbau des neuen Namens
            new_filename = build_perfect_filename(data)
            directory = os.path.dirname(old_path)
            new_path = sanitize_path(os.path.join(directory, new_filename))
             # 2. Filesystem-Aktion
            if old_path != new_path:
                # Kollisionsschutz (wie besprochen)
                if os.path.exists(new_path):
                    name, ext = os.path.splitext(new_filename)
                    new_path = sanitize_path(os.path.join(directory, f"{name}-KOPIE{ext}"))
                if os.path.exists(old_path):
                    shutil.move(old_path, new_path)
                    # DB-Anker aktualisieren
                    success = data.update_file_path(old_path, new_path)
                    if not success:
                        return False, "Pfad konnte in DB nicht aktualisiert werden."
                    data.path = new_path
            # 3. DB-Aktion
            success = data.save()
            return success, new_path
        except Exception as e:
            print(f"Fehler im Model beim Speichern: {e}")
            return False, str(e)

    def delete_book(self, data: BookData, delete_file: bool = False) -> bool:
        db_success = data.delete()
        if db_success and delete_file:
            if os.path.exists(data.path):
                from send2trash import send2trash
                send2trash(data.path)
        return db_success
