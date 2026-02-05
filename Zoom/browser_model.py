"""
DATEI: browser_model.py
PROJEKT: MyBook-Management (v1.5.0)
BESCHREIBUNG: Das "Gehirn" des Browsers. Bietet explizite Methoden für
              den Zugriff via ID oder Pfad sowie die Speicherlogik.
"""
import os
from typing import Tuple, Optional, List

try:
    from Audio.book_data import BookData, BookTData, WorkTData, SerieTData
    from Zoom.scan_file import extract_info_from_filename, derive_metadata_from_path
    from Audio.book_scanner import Scanner
    from Zoom.utils import sanitize_path, DB_PATH, slugify
    from Zoom.work_manager import WorkManager

except ImportError as e:
    print(f"❌ Fehler beim Laden der Untermodule in browser_model.py: {e}")

class BrowserModel:
    # ----------------------------------------------------------------------
    # 1. GEZIELTE DATEN-ABFRAGE
    # Im Grunde ist es nur eine: Get_BOOK_BY_PATH
    # Wir haben eine ganz strenge Logik in diesem Stadium:
    # 1. DB-Abruf = 1:1 die Datenbank (Grün)
    # 2  NUR wenn es das Buch noch nicht in der DB gibt: Einlesen bom Dateiverzeichnis (Blau)
    #    Wenn wir das Buch speichern wollen, müssen wir auf Speichern drücken!
    # 3. Leeres Buch
    # ----------------------------------------------------------------------
    @staticmethod
    def get_book_by_id(book_id: int) -> Optional[BookData]:
        # Kein eigenes SQL mehr!
        return BookData.load_db_by_id(book_id)

    @staticmethod
    def get_book_by_path(path: str) -> BookData:
        clean_path = sanitize_path(path)

        # 1. VERSUCH: Datenbank (Der "Grüne" Pfad)
        book_obj = BookData.load_db_by_path(clean_path)
        if book_obj:
            book_obj.capture_db_state()  # Anker für Vergleich werfen
            book_obj.is_in_db = True
            return book_obj

        # 2. VERSUCH: Physischer Scan (Der "Blaue" Pfad)
        if os.path.exists(clean_path):
            # Der Scanner (Alte Welt) liefert das Atom
            scanned_obj = Scanner.scan_single_book(clean_path)

            if scanned_obj:
                scanned_obj.is_in_db = False
                BrowserModel.auto_migrate(scanned_obj)
                return scanned_obj

        # 3. VERSUCH: Datei existiert gar nicht (Virtuelle Hülle)
        print("DEBUG: FAllback - leere Struktur")
        fallback_obj = BookData()
        fallback_obj.book.path = clean_path
        filename = os.path.basename(clean_path) or "Unbekannt"
        if not os.path.exists(clean_path):
            fallback_obj.book.title = f"⚠️ DATEI FEHLT: {filename}"
        else:
            fallback_obj.book.title = f"❌ SCAN FEHLER: {filename}"
        fallback_obj.is_in_db = False

        return fallback_obj

    # ----------------------------------------------------------------------
    # 2. AUTO MIGRATION für den Browser
    # ----------------------------------------------------------------------
    @staticmethod
    def auto_migrate(manager: BookData):
        """
        Vollautomatische Veredelung des Aggregats nach dem Scan.
        Setzt die 9 Punkte der Konsolidierung um.
        """

        # Vorbereitung: Sprache des Autors ermitteln
        author_lang = manager.get_author_language() or 'en'  # Nutzt jetzt die konsolidierte Methode

        # 1. & 8. IDENTIFIZIERUNG (Work & Serie)
        # Wir suchen in allen Sprachspalten nach Treffern
        best_work_id = manager.find_best_work_match(manager.book.title, author_lang)
        best_serie_id = manager.find_best_serie_match(manager.book.series_name, author_lang)

        print(f"DEBUG Work_ID in migrate: {best_work_id} and {best_serie_id}")
        if best_work_id:
            manager.book.work_id = best_work_id
            manager.load_work_into_manager(best_work_id)

        if best_serie_id:
            # Nutzt jetzt die neue universelle Methode get_series_details
            manager.serie = manager.get_series_details(best_serie_id)
        if manager.book.series_index:
            manager.work.series_index = manager.book.series_index
        # Wenn wir ein Werk haben (neu oder gefunden), führen wir die Datenzusammenführung aus:
        # 2. bis 9. DATEN-KONSOLIDIERUNG
        associated_books = manager.get_all_books_for_work(manager.work.id)

        print(f"DEBUG associated books: {associated_books}")
        # 2. BEWERTUNGEN (Sterne)
        # all_stars = [b.stars for b in associated_books if b.stars > 0]
        all_stars = []
        for b in associated_books:
            try:
                # Sicherstellen, dass wir mit Zahlen arbeiten (wegen '0' Strings)
                val = int(getattr(b, 'stars', 0))
                if val > 0:
                    all_stars.append(val)
            except (ValueError, TypeError):
                continue
        # Auch die Sterne des aktuell bearbeiteten Buchs einbeziehen
        if manager.book.stars and manager.book.stars > 0:
            all_stars.append(int(manager.book.stars))
        if all_stars:
            manager.work.stars = sum(all_stars) // len(all_stars)
        else:
            manager.work.stars = 0

        # 3. BESCHREIBUNG (Sprach-Priorität)
        prio_langs = [author_lang, 'de', 'en', 'fr', 'es', 'it']
        if not manager.work.description:
            for lang in prio_langs:
                desc = manager.get_description_by_lang(associated_books, lang)
                if desc:
                    manager.work.description = desc
                    break

        # 4. & 5. KEYWORDS, REGIONS & GENRE
        for b in associated_books:
            if hasattr(b, 'keywords'): manager.work.keywords.update(b.keywords)
            if hasattr(b, 'regions'): manager.work.regions.update(b.regions)
        # Logik: Work-Genre hat Priorität. Nur wenn dort nichts steht,
        if not manager.work.genre and manager.book.genre:
            manager.work.genre = manager.book.genre

        # 6. NOTIZEN (Alle zusammenführen)
        all_notes = [b.notes for b in associated_books if getattr(b, 'notes', None)]
        if all_notes:
            manager.work.notes = " | ".join(set(all_notes))

        # 7. TITEL-ÜBERTRAGUNG (Sprach-Mapping)
        manager.assign_book_title_to_work_lang()

        # 9. SERIEN-NAMEN (Synchronisation)
        print("DEBUG Serien-Name Synchronisation")
        if manager.serie.id:
            manager.sync_serie_names(author_lang)

        return manager
    # ----------------------------------------------------------------------
    # 2. HILFSMETHODEN für den Browser
    # ----------------------------------------------------------------------
    @staticmethod
    def search_books_in_db(author: str, title: str) -> List[str]:
        return BookData.search_books_in_db(author, title)

    # ----------------------------------------------------------------------
    # 3. SPEICHERN & KONSISTENZ-LOGIK
    # ----------------------------------------------------------------------
    @staticmethod
    def save_book(mgr: BookData, old_path: str = None) -> Tuple[bool, str]:
        """
        Zentrale Speicher-Routine. Überlässt die DB-Logik dem BookData-Modul,
        kümmert sich aber um die physikalische Datei-Operation.
        """
        try:
            actual_old_path = old_path or mgr.book.path

            # 1. Wenn der Serienname gelöscht wurde, kappen wir die Verbindung im Objekt.
            # mgr.save() kümmert sich um den Rest (Update oder neues Werk).
            if not mgr.book.series_name or not mgr.book.series_name.strip():
                mgr.work.series_id = 0
                mgr.work.series_index = 0.0  # Typsicher
                mgr.book.series_id = 0
                mgr.book.series_index = 0.0  # Umbenannt von series_number
                print(f"DEBUG: Serien-Entkopplung für '{mgr.work.title}' gesetzt.")
            else:
                # WICHTIG: Synchronisation Buch -> Werk vor dem DB-Save
                # Das stellt sicher, dass das Werk den Index des führenden Buchs übernimmt.
                mgr.work.series_index = float(mgr.book.series_index or 0.0)
                print(f"DEBUG: Serien-Entkopplung für '{mgr.work.title}' im Objekt gesetzt.")

            # 2. PHYSIKALISCHES RENAME (Vor dem DB-Save, damit Pfad in DB stimmt)
            if actual_old_path and os.path.exists(actual_old_path):
                new_path = Scanner.build_perfect_filename(mgr)

                if sanitize_path(actual_old_path) != sanitize_path(new_path):
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    os.rename(actual_old_path, new_path)
                    mgr.book.path = new_path
                    print(f"🚚 Rename: {os.path.basename(new_path)}")

            # 3. DB-COMMIT
            # Nutzt die Logik: "Passt der Titel noch zur ID?" direkt im Modul
            success = mgr.save()

            if success:
                mgr.capture_db_state()

            return success, mgr.book.path

        except Exception as e:
            print(f"❌ Fehler bei save_book: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)


# --------------------------------------------------------------------------
# TEST-AUFRUF UND INITIALISIERUNG
# --------------------------------------------------------------------------
if __name__ == "__main__":
    # Da alles statisch ist, kannst du direkt testen (Beispiel):
    print("🚀 BrowserModel geladen. Teste Pfad-Abfrage...")
    # test_path = "C:/Dein/Test/Pfad.epub"
    # book = BrowserModel.get_book_by_path(test_path)
    # print(f"Buch-Titel: {book.book.title}")