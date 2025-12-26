"""
DATEI: browser_model.py
PROJEKT: MyBook-Management (v1.2.0)
BESCHREIBUNG: Kümmert sich um die Daten von der Book_Browser App.
              book_browser.py	=	Der Controller: Steuert den Flow (Laden -> Navigieren -> Speichern).
              browser_view.py	=	Die Maske: Zeichnet alles und fängt Benutzereingaben ab.
              browser_model.py	=	Das Gehirn: Muss die Methoden aggregate_book_data und save_book enthalten.
"""
import os
import shutil
import sqlite3
from typing import List, Optional

# --- Importe deiner spezialisierten Module ---
try:
    from read_db_ebooks import get_db_metadata, search_books
    from save_db_ebooks import save_book_with_authors, update_db_path
    from read_file import derive_metadata_from_path
    from read_epub import get_epub_metadata
    from book_data_model import BookData
except ImportError as e:
    print(f"WARNUNG: Ein Untermodul im Model konnte nicht geladen werden: {e}")


class BrowserModel:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.temp_files = []

    # ----------------------------------------------------------------------
    # DATEN-AGGREGATION
    # ----------------------------------------------------------------------
    def aggregate_book_data(self, file_path: str) -> 'BookData':
        print(f"DEBUG: Versuche zu laden: {file_path}")

        # 0. Existenzprüfung
        if not os.path.exists(file_path):
            print(f"❌ Datei nicht gefunden: {file_path}")
            from book_data_model import BookData
            return BookData(path=file_path, title="DATEI NICHT GEFUNDEN")

        # 1. Metadaten aus der DATEI (EPUB) extrahieren
        file_data = None
        ext = file_path.lower().split('.')[-1]

        if ext == 'epub':
            file_data = get_epub_metadata(file_path)

        if isinstance(file_data, tuple) or file_data is None:
            file_data = derive_metadata_from_path(file_path)

        # Falls es ein Dictionary war, in Objekt wandeln (BookData Klasse)
        if isinstance(file_data, dict):
            from book_data_model import BookData
            file_data = BookData(**file_data)

        file_data.path = file_path

        # 2. Datenbank-Abfrage
        db_data = get_db_metadata(file_path, db_path=self.db_path)

        # Wenn wir Daten in der DB finden (db_data ist ein DICT)
        if db_data:
            print(f"DEBUG: DB-Daten gefunden, ergänze Objekt.")

            # Sicherer Zugriff auf das Dictionary mit .get()
            # Das verhindert den AttributeError
            file_data.stars = db_data.get('stars') if db_data.get('stars') else file_data.stars
            file_data.notes = db_data.get('notes') if db_data.get('notes') else file_data.notes

            # Bei is_read reicht oft ein einfacher get, da 0/1 (False/True)
            file_data.is_read = db_data.get('is_read', file_data.is_read)

            # Klappentext
            if db_data.get('description'):
                file_data.description = db_data.get('description')

            # Metadaten-Korrekturen aus der DB
            file_data.title = db_data.get('title') if db_data.get('title') else file_data.title

            # Achte hier auf 'authors' vs 'author' - je nachdem wie es in deiner DB heißt
            db_author = db_data.get('authors') or db_data.get('author')
            file_data.authors = db_author if db_author else file_data.authors

        return file_data

    # ----------------------------------------------------------------------
    # SUCHE & NAVIGATION
    # ----------------------------------------------------------------------
    def search_books_in_db(self, author: str, title: str) -> List[str]:
        """Sucht in der DB und gibt eine Liste von Pfaden zurück."""
        results = search_books(author, title, db_path=self.db_path)
        # Normalisierte Pfade für den Controller extrahieren
        return [os.path.normpath(b['file_path']) for b in results if b.get('file_path')]

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
        """Koordiniert Umbenennung und DB-Update mit stabilem Anker."""
        try:
            # Wir vertrauen dem Pfad, den der Controller uns als "Original" gibt
            old_path = os.path.normpath(old_path_from_controller)

            # 1. Neuen Namen generieren
            # (Deine Logik für author_str, series_str etc. bleibt gleich)
            author_str = " & ".join([f"{fn} {ln}".strip() for fn, ln in data.authors]) if data.authors else "Unbekannt"
            series_str = f" — {data.series_name} {data.series_number}-" if data.series_name else " — "
            ext = old_path.split('.')[-1]
            new_filename = f"{author_str}{series_str}{data.title} ({data.year}).{ext}"
            for char in '<>:"/\\|?*': new_filename = new_filename.replace(char, '')

            new_path = os.path.join(os.path.dirname(old_path), new_filename)

            # 2. Filesystem-Aktion
            if old_path != new_path:
                if os.path.exists(old_path):
                    shutil.move(old_path, new_path)
                    # WICHTIG: Wir sagen der DB erst, dass das Buch jetzt anders heißt
                    # Bevor wir die restlichen Metadaten speichern!
                    self.update_db_path(old_path, new_path)
                data.path = new_path

                # 3. DB-Aktion
            # Hier liegt das Risiko: save_book_with_authors muss nun ein UPDATE machen.
            # Falls diese Funktion intern immer noch über den Pfad sucht,
            # findet sie jetzt den neuen Pfad, den wir gerade mit update_db_path gesetzt haben.
            success = save_book_with_authors(data, db_path=self.db_path)

            return True, new_path
        except Exception as e:
            print(f"Fehler im Model beim Speichern: {e}")
            return False, str(e)

    def delete_book(self, file_path: str):
        """Entfernt nur den DB-Eintrag."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM books WHERE file_path = ?", (file_path,))
        except Exception as e:
            print(f"DB-Löschfehler: {e}")

    def cleanup_temp_files(self):
        """Platzhalter für das Löschen von extrahierten Covern."""
        # Falls du Cover in einem Temp-Ordner zwischenspeicherst
        pass