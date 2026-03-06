# Engineering/__init__.py
import os
from typing import Optional
from Enterprise.database import Database  # Enterprise DB statt _Archiv
from Enterprise.core import Core

# Die neuen Basis-Services importieren
from Engineering.author_service import AuthorService
from Engineering.work_service import WorkService
from Engineering.serie_service import SeriesService
from Engineering.book_service import BookService  # Später in BookService umbenennen
from Engineering.logic_services import LogicService
from Engineering.search_service import SearchService
from Engineering.health_service import HealthDiagnosis  # Dein neuer Heiler
from Engineering.audio_services import AudioService


class Engineering:
    """
    Die Engineering-Fassade: Zentraler Zugriff auf alle Dienste.
    """
    # Statische Bindung der Services (Namespacing)
    Search = SearchService
    Logic = LogicService
    Health = HealthDiagnosis  # Sanitizer wird durch HealthDiagnosis ersetzt

    # Die neuen Entity-Services
    Books = BookService
    Authors = AuthorService
    Works = WorkService
    Series = SeriesService
    Database = Database
    Audios = AudioService
    Core = Core

    # --- ABWÄRTSKOMPATIBILITÄT (Legacy-Support) ---
    # Damit author_browser.py und andere wieder laufen:
    BookFileService = BookService
    SearchService = AuthorService  # Da AuthorService jetzt die Such-Logik für Autoren hat

    @staticmethod
    def get_book_by_path(path: str) -> Core:
        """
        Zentraler Einstiegspunkt: Erst DB, dann Scan.
        """
        # 1. Versuch: Aus der DB laden
        core = Core.load_book_by_path(path)
        if core:
            return core

        # 2. Versuch: Wenn DB nichts liefert -> Scan via BookService
        return BookService.scan_file_basic(path)

    @staticmethod
    def get_book_by_id(book_id: int) -> Optional[Core]:
        """Holt ein Buch strikt aus der DB."""
        res = Database.query_one("SELECT path FROM books WHERE id = ?", [book_id])
        if res:
            return Core.load_book_by_path(res['path'])
        return None

    @staticmethod
    def get_audio_by_path(path: str) -> Core:
        """
        Zentraler Einstiegspunkt für Audiobooks.
        Prüft erst die DB, scannt sonst den Ordner.
        """
        # 1. Versuch: Aus der DB laden (Wir nutzen die neue Core-Methode)
        core = Core.load_audio_by_path(path)
        if core:
            return core

        # 2. Versuch: Wenn neu -> Physischer Scan via AudioService
        # Wir brauchen hier den Kontext (Autor), um sauber zu parsen
        author_context = os.path.basename(os.path.dirname(path))
        return AudioService.scan_audio_folder(path, author_context)
