# Bridge/book_manager.py
from Engineering import Engineering as Eng
from Enterprise.core import Core
from Engineering.book_service import BookService


class BookManager:
    """
    Der neue Standort für die Logik aus BrowserModel.
    Zuständig für Entscheidungen und Koordination.
    """
    def __init__(self):
        self.current_core = None

    # ----------------------------------------------------------------------
    # GET DATEN-LOGIK
    # ----------------------------------------------------------------------
    def get_book_by_id(self, book_id: int) -> Core:
        self.current_core = Eng.get_book_by_id(book_id)
        return self.current_core

    def get_book_by_path(self, path):
        """Holt das Buch über den Service (DB oder Scotty-Scan)."""
        self.current_core = Eng.get_book_by_path(path)
        return self.current_core

    def search_db(self, author, title):
        """Delegiert die Suche an den Service."""
        return Eng.Search.get_available_paths(author, title)


    # ----------------------------------------------------------------------
    # ENRICH DATEN-LOGIK
    # ----------------------------------------------------------------------
    def _enrich_ui_lists(self, core: Core):
        """Bereitet die Daten für die View-Comboboxen vor."""
        authors = core.book.authors  # Liste von [Vorname, Nachname]

        # Engineering fragt die DB nach passenden Serien/Werken für diese Autoren
        core.all_available_series = Eng.Search.get_series_by_authors(authors)
        core.all_available_works = Eng.Search.get_works_by_authors(authors)

    @staticmethod
    def auto_migrate(core: Core):
        """
        Pille veredelt das Aggregat: Führt Sterne, Genres und Keywords zusammen.
        """
        if not core: return

        # 1. Daten-Beschaffung via Engineering
        # Wir suchen nach passenden Werken für den Titel/Autor
        best_work_id = Eng.Search.find_best_work_match(core.book.title, core.book.language)

        if best_work_id:
            core.book.work_id = best_work_id
            # Wir "energizen" das Werk-Atom im Core
            core.work = Eng.Search.get_work_by_id(best_work_id)

        # 2. Geschwister-Daten für die Veredelung holen
        associated_books = Eng.Search.get_all_books_for_work(core.book.work_id)

        # --- STERNE-LOGIK (Dein Durchschnitts-Algorithmus) ---
        all_stars = []
        for b in associated_books:
            val = getattr(b, 'stars', 0) or 0
            if int(val) > 0: all_stars.append(int(val))

        if core.book.stars and core.book.stars > 0:
            all_stars.append(int(core.book.stars))

        if all_stars:
            core.work.stars = sum(all_stars) // len(all_stars)

        # --- BESCHREIBUNG & GENRE ---
        if not core.work.description:
            # Wir nutzen deine Prioritäten-Liste
            prio_langs = [core.book.language, 'de', 'en', 'fr']
            for lang in prio_langs:
                desc = Eng.Search.get_description_by_lang(associated_books, lang)
                if desc:
                    core.work.description = desc
                    break

        if not core.work.genre and core.book.genre:
            core.work.genre = core.book.genre

        # --- KEYWORDS & REGIONEN (Sets!) ---
        for b in associated_books:
            core.work.keywords.update(b.keywords)
            core.work.regions.update(b.regions)

        return core

    # ----------------------------------------------------------------------
    # SAVE DATEN-LOGIK
    # ----------------------------------------------------------------------
    @staticmethod
    def save_current_state(core: Core, old_path: str = None) -> bool:
        """
        Der 'Alles-Sicher'-Knopf.
        1. Scotty benennt Datei um (falls nötig).
        2. Spock sichert die DB (kaskadierend).
        """
        # 1. Scotty: File-System Operation
        # (Wir nutzen deine smart_save Logik)
        new_path = BookService.smart_save(
            old_path=old_path,
            authors=core.book.authors,
            title=core.book.title,
            series_name=core.book.series_name,
            series_index=core.book.series_index
        )

        if not new_path:
            return False

        core.book.path = new_path

        # 2. Engineering: Datenbank Operation
        success = Eng.Data.save_full_system(core)

        if success:
            # 3. Snapshot für UI setzen (Vergleichsanker)
            core.capture_db_state()
            return True
        return False

    @staticmethod
    def save_book(self, core: Core) -> bool:
        # Ruft deine große save() Methode aus der Enterprise auf
        return core.save()