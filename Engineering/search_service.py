# Engineering/search_service.py
import pandas as pd
from typing import Optional, List, Dict, Any
from Enterprise.core import kern_to_atom, SerieTData, AuthorTData, BookTData, WorkTData, Core

class SearchService:
    """
    Proxy-Service: Behält Legacy-Methodennamen bei, delegiert aber
    an die neuen Fach-Services via Facade.
    """

    # -------------------------------------------------------------
    # Core Search
    # -------------------------------------------------------------
    @staticmethod
    def get_all_known_paths():
        # Delegiert an den spezialisierten BookService
        from Engineering import Engineering as Eng
        return Eng.Books.get_all_paths()

    # -------------------------------------------------------------
    # Book Search
    # -------------------------------------------------------------
    @staticmethod
    def find_paths_by_criteria(author: str = "", title: str = ""):
        # Komplexe Filter-Queries bleiben vorerst hier, nutzen aber die DB-Facade
        query = "SELECT path FROM books WHERE 1=1"
        params = []
        if author:
            query += " AND authors_raw LIKE ?"
            params.append(f"%{author}%")
        if title:
            query += " AND title LIKE ?"
            params.append(f"%{title}%")
        from Engineering import Engineering as Eng
        rows = Eng.Database.query_all(query, params)
        return [r['path'] for r in rows]

    @staticmethod
    def find_books_by_work_id(work_id: int) -> List[Dict[str, Any]]:
        from Engineering import Engineering as Eng
        return Eng.Books.get_by_work_id(work_id)

    @staticmethod
    def find_all_books_for_work(work_id: int) -> list[BookTData]:
        # Nutzt die neue BookService Logik für Atome
        from Engineering import Engineering as Eng
        return Eng.Books.get_all_for_work_as_atoms(work_id)

    @staticmethod
    def find_books_by_series_id(s_id: int):
        query = """
            SELECT b.id, w.series_index, b.path 
            FROM books b
            JOIN works w ON b.work_id = w.id
            WHERE w.series_id = ?
            ORDER BY CAST(w.series_index AS FLOAT) ASC, b.path ASC
        """
        from Engineering import Engineering as Eng
        return Eng.Database.query_all(query, [s_id])

    # -------------------------------------------------------------
    # Work Search
    # -------------------------------------------------------------
    @staticmethod
    def find_work_by_id(work_id: int):
        from Engineering import Engineering as Eng
        return Eng.Works.get_by_id(work_id)

    @staticmethod
    def find_work_by_triple(title: str, series_index: float, authors: list) -> int:
        """
        GEHEILT: Nutzt jetzt die bombensichere Slug-basierte Logik
        des WorkService statt unsicherer Nachnamen-Suche.
        """
        # Wir müssen die Autoren-Namen erst in IDs auflösen (via Slugs)
        from Engineering import Engineering as Eng
        a_ids = [Eng.Authors.get_or_create(a[0], a[1]) for a in authors if len(a) > 1]
        return Eng.Works.find_by_triple(title, series_index, a_ids)

    @staticmethod
    def get_duplicate_work_candidates(series_id: int, series_index: float):
        # Spezial-Query für Dubletten bleibt hier
        query = """
            SELECT id, title, title_de, title_en, title_fr, stars
            FROM works
            WHERE series_id = ? AND ABS(series_index - ?) < 0.001
            ORDER BY title ASC
        """
        from Engineering import Engineering as Eng
        return Eng.Database.query_all(query, [series_id, series_index])

    # -------------------------------------------------------------
    # Serien Search
    # -------------------------------------------------------------
    @staticmethod
    def find_series_by_id_as_atom(s_id: int):
        from Engineering import Engineering as Eng
        row = Eng.Series.get_by_id(s_id)
        if row:
            return kern_to_atom(SerieTData, row)
        return None

    @staticmethod
    def find_all_series_summary_df() -> pd.DataFrame:
        # Komplexe Berichts-Queries bleiben im SearchService (Analysten-Rolle)
        query = """
            SELECT s.id, s.name, 
            COALESCE((SELECT a.firstname || ' ' || a.lastname FROM authors a 
                      JOIN work_to_author wta ON a.id = wta.author_id
                      JOIN works w ON wta.work_id = w.id
                      WHERE w.series_id = s.id GROUP BY a.id 
                      ORDER BY COUNT(w.id) DESC LIMIT 1), 'Unbekannt') as author_full,
            (SELECT COUNT(*) FROM works WHERE series_id = s.id) as count_w,
            (SELECT COUNT(b.id) FROM books b JOIN works w ON b.work_id = w.id WHERE w.series_id = s.id) as count_b
            FROM series s
        """
        from Engineering import Engineering as Eng
        return pd.DataFrame(Eng.Database.query_all(query))

    # -------------------------------------------------------------
    # Autoren Search
    # -------------------------------------------------------------
    @staticmethod
    def find_author_by_name(name: str):
        import re
        if not name:
            return None
        # Wir splitten den Namen grob für den Service
        parts = re.split(r'[&;]| et ', name)
        first_author_raw = parts[0].strip()
        # Jetzt den Namen in Vor- und Nachname zerlegen (logik-konform)
        # Hier nutzen wir am besten die zentrale _normalize_author_name Logik,
        # falls diese im AuthorService oder einer Utility-Klasse erreichbar ist.
        name_parts = first_author_raw.split(' ')
        fname, lname = (" ".join(name_parts[:-1]), name_parts[-1]) if len(name_parts) > 1 else ("", first_author_raw)
        # get_or_create stellt sicher, dass wir den Slug-Match nutzen!
        from Engineering import Engineering as Eng
        author_id = Eng.Authors.get_or_create(fname, lname)
        return Eng.Authors.get_by_id(author_id)

    @staticmethod
    def find_author_by_id_as_atom(author_id: int) -> Optional[AuthorTData]:
        from Engineering import Engineering as Eng
        row = Eng.Authors.get_by_id(author_id)
        return kern_to_atom(AuthorTData, row) if row else None

    @staticmethod
    def find_authors_summary_df(term: str = "") -> pd.DataFrame:
        # Bleibt hier, da es ein reiner UI/Pandas-Report ist
        where_clause = ""
        params = []
        if term:
            where_clause = "WHERE a.firstname LIKE ? OR a.lastname LIKE ?"
            params = [f"%{term}%", f"%{term}%"]

        query = f"""
            SELECT a.id, (COALESCE(a.firstname, '') || ' ' || COALESCE(a.lastname, '')) as display_name,
            COUNT(DISTINCT b.id) as total,
            COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'de' THEN b.id END) as de
            FROM authors a
            LEFT JOIN work_to_author wta ON a.id = wta.author_id
            LEFT JOIN books b ON wta.work_id = b.work_id
            {where_clause} GROUP BY a.id ORDER BY a.lastname, a.firstname
        """
        from Engineering import Engineering as Eng
        return pd.DataFrame(Eng.Database.query_all(query, params))