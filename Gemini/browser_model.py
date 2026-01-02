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
from typing import List

# --- Importe deiner spezialisierten Module ---
try:
    from read_db_ebooks import get_db_metadata, search_books
    from save_db_ebooks import save_book_with_authors, update_db_path
    from read_file import derive_metadata_from_path
    from read_epub import get_epub_metadata
    from Apps.book_data import BookData
    from Apps.book_scanner import scan_single_book
except ImportError as e:
    print(f"WARNUNG: Ein Untermodul im Model konnte nicht geladen werden: {e}")


class BrowserModel:
    def __init__(self, db_path: str):
        #self.db_path = db_path
        self.temp_files = []

    # ----------------------------------------------------------------------
    # DATEN-AGGREGATION
    # ----------------------------------------------------------------------
    def aggregate_book_data(self, file_path: str) -> 'BookData':
        # 1. Versuch: Direkt aus der Datenbank laden
        # Wir nutzen die Methode, die uns ein fertiges Objekt inkl. ID gibt
        book_obj = BookData.load_by_path(file_path)

        if book_obj:
            print(f"DEBUG: Blitz-Ladung aus DB für ID {book_obj.id}")
        else:
            # 2. Versuch: Das Buch ist brandneu für das System
            print(f"DEBUG: {file_path} unbekannt. Starte Full-Scan...")
            book_obj = scan_single_book(file_path)
            # 2. Live-Check: Existiert die Datei auf M://?

        if book_obj and not os.path.exists(book_obj.path):
            # Den alten Pfad als Info retten, bevor wir ihn löschen
            lost_path_note = f"[Info]: Ursprünglicher Pfad war verloren: {book_obj.path}"
            if lost_path_note not in (book_obj.notes or ""):
                book_obj.notes = (book_obj.notes or "") + f"\n{lost_path_note}"
            book_obj.path =""
            book_obj.save()
        return book_obj

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
        """Koordiniert Umbenennung des Files im Filesystem und stößt die DB-Update mit stabilem Anker an."""
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
            print(f"DEBUG PATH COMPARE:")
            print(f"  Old (Raw): {repr(old_path_from_controller)}")
            print(f"  Old (Norm): {repr(old_path)}")
            print(f"  New (Norm): {repr(new_path)}")
            print(f"  Equal?    : {old_path == new_path}")


            # 2. Filesystem-Aktion
            if old_path != new_path:
                if os.path.exists(old_path):
                    shutil.move(old_path, new_path)
                    # WICHTIG: Wir sagen der DB erst, dass das Buch jetzt anders heißt
                    # Bevor wir die restlichen Metadaten speichern!
                    update_db_path(old_path, new_path)
                data.path = new_path

            # 3. DB-Aktion
            success = data.save()

            return success, new_path
        except Exception as e:
            print(f"Fehler im Model beim Speichern: {e}")
            return False, str(e)

    def delete_book(self, data: BookData, delete_file: bool = False) -> bool:
        """Koordiniert das Löschen in DB und (optional) im Filesystem."""
        try:
            # 1. Schritt: Datenbank-Eintrag löschen (via BookData-Klasse)
            db_success = data.delete()
            # 2. Schritt: Optional die echte Datei löschen
            if db_success and delete_file:
                if os.path.exists(data.path):
                    # Statt os.remove(data.path)
                    from send2trash import send2trash
                    send2trash(data.path)
                    print(f"Datei gelöscht: {data.path}")
                else:
                    print(f"Hinweis: Datei nicht gefunden, wurde nur aus DB entfernt.")

            return db_success
        except Exception as e:
            print(f"Fehler im Model beim Löschen: {e}")
            return False

    def cleanup_temp_files(self):
        """Platzhalter für das Löschen von extrahierten Covern."""
        # Falls du Cover in einem Temp-Ordner zwischenspeicherst
        pass