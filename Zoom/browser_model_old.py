"""
DATEI: browser_model.py
PROJEKT: MyBook-Management (v1.5.0)
BESCHREIBUNG: Das "Gehirn" des Browsers. Bietet explizite Methoden für
              den Zugriff via ID oder Pfad sowie die Speicherlogik.
"""
import os
import tkinter as tk
from typing import Tuple, Optional

try:
    from Audio.book_data import BookData, BookTData, WorkTData, SerieTData
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
        return BookData.load_by_id(book_id)

    @staticmethod
    def get_book_by_path(path: str) -> BookData:
        clean_path = sanitize_path(path)

        # 1. VERSUCH: Datenbank (Der "Grüne" Pfad)
        book_obj = BookData.load_by_path(clean_path)
        if book_obj:
            book_obj.capture_db_state()  # Anker für Vergleich werfen
            book_obj.is_in_db = True
            return book_obj

        # 2. VERSUCH: Physischer Scan (Der "Blaue" Pfad)
        if os.path.exists(clean_path):
            # Wir erzeugen den Manager vorab
            book_obj = BookData()
            # Der Scanner (Alte Welt) liefert das Atom
            scanned_obj = Scanner.scan_single_book(clean_path)

            if scanned_obj:
                scanned_obj.is_in_db = False
                BrowserModel.auto_migrate(scanned_obj)
                return scanned_obj

        # 3. VERSUCH: Datei existiert gar nicht (Virtuelle Hülle)
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
        wm = WorkManager()

        # Vorbereitung: Sprache des Autors ermitteln
        # Wir nehmen an, BookData hat Zugriff auf die Autoren-Tabelle
        author_lang = manager.get_author_language() or 'en'  # Default 'en'

        # 1. & 8. IDENTIFIZIERUNG (Work & Serie)
        # Wir suchen in allen Sprachspalten nach Treffern
        best_work_id = manager.find_best_work_match(manager.book.title, author_lang)
        best_serie_id = manager.find_best_serie_match(manager.book.series_name, author_lang)

        if best_work_id:
            manager.book.work_id = best_work_id
            manager.load_work_into_manager(best_work_id)

        if best_serie_id:
            manager.serie = manager.get_series_details_by_id(best_serie_id)

        # Wenn wir ein Werk haben (neu oder gefunden), führen wir die Datenzusammenführung aus:
        # 2. bis 9. DATEN-KONSOLIDIERUNG
        # Hierfür holen wir uns alle Bücher, die bereits an diesem Werk hängen
        associated_books = manager.get_all_books_for_work(manager.work.id)

        # 2. BEWERTUNGEN (Sterne)
        # Wir nehmen den Durchschnitt oder das Maximum der zugeordneten Bücher
        all_stars = [b.stars for b in associated_books if b.stars > 0]
        if manager.book.stars > 0: all_stars.append(manager.book.stars)
        if all_stars:
            manager.work.stars = int(sum(all_stars) / len(all_stars))

        # 3. BESCHREIBUNG (Sprach-Priorität)
        # Prio: Autor-Sprache > de > en > fr > es > it
        prio_langs = [author_lang, 'de', 'en', 'fr', 'es', 'it']
        if not manager.work.description:
            for lang in prio_langs:
                desc = manager.get_description_by_lang(associated_books, lang)
                if desc:
                    manager.work.description = desc
                    break

        # 4. & 5. KEYWORDS, REGIONS & GENRE
        for b in associated_books:
            # Keywords & Regions als Sets sammeln (Punkt 4)
            if hasattr(b, 'keywords'): manager.work.keywords.update(b.keywords)
            if hasattr(b, 'regions'): manager.work.regions.update(b.regions)

            # Genre (Punkt 5: Häufigstes oder "längstes" gewinnt)
            if b.genre and len(b.genre) > len(manager.work.genre or ""):
                manager.work.genre = b.genre

        # 6. NOTIZEN (Alle zusammenführen)
        all_notes = [b.notes for b in associated_books if getattr(b, 'notes', None)]
        if all_notes:
            manager.work.notes = " | ".join(set(all_notes))

        # 7. TITEL-ÜBERTRAGUNG (Sprach-Mapping)
        # Ordnet den Titel des Buches der passenden Spalte im Werk zu
        manager.assign_book_title_to_work_lang()

        # 9. SERIEN-NAMEN (Synchronisation)
        if manager.serie.id:
            manager.sync_serie_names(author_lang)

        return manager
    # ----------------------------------------------------------------------
    # 2. HILFSMETHODEN für den Browser
    # ----------------------------------------------------------------------
    @staticmethod
    def get_prioritized_series(authors: list) -> list:
        return BookData.get_prioritized_series(authors)

    @staticmethod
    def get_works_by_authors(authors: list) -> list:
        return BookData.get_works_by_authors(authors)

    @staticmethod
    def find_work_by_series_fingerprint(book_data: BookData) -> Optional[int]:
        return BookData.find_work_by_series_fingerprint(book_data)
    # ----------------------------------------------------------------------
    # 2. SPEICHERN & KONSISTENZ-LOGIK
    # ----------------------------------------------------------------------
    @staticmethod
    def save_book(mgr: BookData, old_path: str = None) -> Tuple[bool, str]:
        """
        Zentrale Speicher-Routine. Nutzt die bereits im mgr-Objekt
        vorhandenen Daten aus der View.
        """
        try:
            # Merken des alten Pfades für das physische Rename
            actual_old_path = old_path or mgr.book.path

            # 1. AUFLÖSUNG DER RELATIONEN (Das "Andocken")
            # Die Namen (mgr.serie.name, mgr.work.title) wurden bereits durch
            # get_data_from_widgets() in die Atome geschrieben.
            authors = mgr.authors

            # A. SERIE: Prüfung auf Neuzuordnung
            if mgr.serie.name:
                # Wir suchen nach dem Namen, um die ID zu finden
                s_id = mgr.get_series_id_by_name(mgr.serie.name)
                if s_id:
                    mgr.serie.id = s_id
                    mgr.work.series_id = s_id
                else:
                    # Neuer Name -> Kennzeichnung für Neuanlage in mgr.save()
                    mgr.serie.id = 0
                    mgr.work.series_id = None

            # B. WERK: Prüfung auf Neuzuordnung oder Neuanlage
            # Wir prüfen, ob der Work-Titel (aus der ComboBox oder getippt) existiert
            db_work = mgr.get_work_details_by_title(mgr.work.title, authors)

            if db_work and db_work.id > 0:
                # MATCH: Wir hängen dieses Buch an das existierende Werk-Objekt an
                mgr.work = db_work
                mgr.book.work_id = db_work.id
                print(f"🔗 Match! Buch wird an Werk '{mgr.work.title}' (ID {db_work.id}) gebunden.")
            else:
                # KEIN MATCH: mgr.save() wird ein neues Werk-Atom in der DB erzeugen
                mgr.book.work_id = 0
                mgr.work.id = 0
                print(f"🆕 Neues Werk wird angelegt: {mgr.work.title}")

            # 2. PHYSIKALISCHES RENAME (Pfad-Heilung & Extension-Schutz)
            if actual_old_path and os.path.exists(actual_old_path):
                # Wir nutzen den Scanner, um den Namen nach V1.5 Regeln zu bauen
                # Wichtig: Die Extension muss aus dem mgr.book.ext Feld kommen!
                new_path = Scanner.build_perfect_filename(mgr)

                if sanitize_path(actual_old_path) != sanitize_path(new_path):
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    os.rename(actual_old_path, new_path)
                    mgr.book.path = new_path
                    print(f"🚚 Rename erfolgreich: {os.path.basename(new_path)}")

            # 3. DB-COMMIT
            # Schreibt Serie (falls neu), Werk (falls neu oder geänderte ID)
            # und das Buch inkl. Verknüpfung.
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
    # Import hier, um Zirkelbezüge zu vermeiden
    from Audio.book_browser import BookBrowser

    root = tk.Tk()
    root.withdraw() # Hauptfenster verstecken

    # 1. Das Model instanziieren (Das "Gehirn")
    # In der finalen Version macht das der BookBrowser selbst in seinem __init__

    # 2. Eine Test-Liste erstellen (z.B. von einer App oder einem Pfad)
    # Hier simulieren wir den Start mit einer ID
    test_nav = [{'ID': 1}]

    # 3. Den Browser in einem Toplevel öffnen
    browser_win = tk.Toplevel(root)
    app = BookBrowser(browser_win, initial_list=test_nav)

    # Sicherstellen, dass beim Schließen alles beendet wird
    browser_win.protocol("WM_DELETE_WINDOW", root.destroy)

    root.mainloop()