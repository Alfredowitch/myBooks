import inspect
import sqlite3
import unicodedata
import re
import os
from dataclasses import dataclass
from typing import Optional, List
from Zoom.utils import DB_PATH, EBOOK_BASE, slugify


# ----------------------------------------------------------------------
# I. AUTOREN-KLASSE
# ----------------------------------------------------------------------
@dataclass
class Author:
    id: Optional[int] = None
    firstname: str = ""
    lastname: str = ""
    slug: str = ""
    main_language: Optional[str] = None
    vita: Optional[str] = None
    info_link: str = ""
    stars: int = 0

    @property
    def display_name(self) -> str:
        return f"{self.firstname} {self.lastname}".strip()

    @staticmethod
    def create_slug(name: str) -> str:
        if not name: return ""
        nfkd_form = unicodedata.normalize('NFKD', name)
        only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
        slug = re.sub(r'[^\w\s-]', '', only_ascii).strip().lower()
        return re.sub(r'[-\s]+', '-', slug)


# ----------------------------------------------------------------------
# II. AUTOREN-MANAGER-KLASSE
# ----------------------------------------------------------------------
class AuthorManager:
    def __init__(self):
        self.db_path = DB_PATH
        self.author_images_path = os.path.join(EBOOK_BASE, "Autoren")
        if not os.path.exists(self.author_images_path):
            os.makedirs(self.author_images_path)
        self._ensure_v15_schema()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_v15_schema(self):
        """Stellt sicher, dass alle benötigten Spalten (inkl. series_index) existieren."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Check Autoren-Tabelle
            cursor.execute("PRAGMA table_info(authors)")
            author_cols = [c[1] for c in cursor.fetchall()]
            author_updates = {
                "slug": "TEXT", "vita": "TEXT", "main_language": "TEXT",
                "info_link": "TEXT", "stars": "INTEGER DEFAULT 0"
            }
            for col, type_ in author_updates.items():
                if col not in author_cols:
                    cursor.execute(f"ALTER TABLE authors ADD COLUMN {col} {type_}")

            # Check Works-Tabelle für series_index (Float-Support)
            cursor.execute("PRAGMA table_info(works)")
            work_cols = [c[1] for c in cursor.fetchall()]
            if "series_index" not in work_cols:
                cursor.execute("ALTER TABLE works ADD COLUMN series_index REAL DEFAULT 0")

            conn.commit()

    # ----------------------------------------------------------------------
    # LOAD-METHODEN (BROWSER-SUPPORT)
    # ----------------------------------------------------------------------
    def get_series_by_author(self, author_id: int) -> List[dict]:
        query = """
            SELECT DISTINCT s.id, s.name, 
            (SELECT COUNT(*) FROM works w 
             JOIN work_to_author wta ON w.id = wta.work_id 
             WHERE w.series_id = s.id AND wta.author_id = ?) as work_count
            FROM series s
            JOIN works w ON s.id = w.series_id
            JOIN work_to_author wta ON w.id = wta.work_id
            WHERE wta.author_id = ?
            ORDER BY s.name ASC
        """
        with self._get_conn() as conn:
            rows = conn.execute(query, (author_id, author_id)).fetchall()
            return [dict(r) for r in rows]

    def get_works_by_serie(self, serie_id: int, author_id: int) -> List[dict]:
        if serie_id == 0:
            serie_filter = "(w.series_id = 0 OR w.series_id IS NULL OR w.series_id = '')"
            params = (author_id,)
        else:
            serie_filter = "w.series_id = ?"
            params = (serie_id, author_id)

        query = f"""
            SELECT w.id, w.title, w.series_index,
            (SELECT COUNT(*) FROM books b WHERE b.work_id = w.id) as book_count
            FROM works w
            JOIN work_to_author wta ON w.id = wta.work_id
            WHERE {serie_filter} AND wta.author_id = ?
            ORDER BY w.series_index ASC, w.title ASC
        """
        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_author(self, author_id: int) -> Optional[Author]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM authors WHERE id = ?", (author_id,)).fetchone()
            if not row: return None
            row_dict = dict(row)
            sig = inspect.signature(Author)
            valid_keys = [p for p in sig.parameters.keys() if p != 'display_name']
            filtered_dict = {k: v for k, v in row_dict.items() if k in valid_keys}
            return Author(**filtered_dict)

    # ----------------------------------------------------------------------
    # WORK-EDITOR-SUPPORT (PRIORISIERUNG)
    # ----------------------------------------------------------------------
    def get_potential_books_for_work(self, work_id: int, author_id: int, s_index: float) -> List[dict]:
        """
        Findet Bücher, die entweder dem Werk gehören oder dem Autor + Index entsprechen.
        WICHTIG: Nutzt jetzt den Float series_index.
        """
        query = """
            SELECT b.*, 
            (b.work_id = :w_id) as assigned,
            CASE WHEN b.work_id = :w_id THEN 1 ELSE 2 END as priority
            FROM books b
            WHERE b.work_id = :w_id
               OR (
                   b.work_id IN (SELECT work_id FROM work_to_author WHERE author_id = :a_id)
                   AND CAST(b.series_number AS REAL) = CAST(:s_idx AS REAL)
                   AND b.series_number > 0
               )
            ORDER BY priority ASC, b.title ASC
        """
        try:
            params = {"w_id": work_id, "a_id": author_id, "s_idx": s_index}
            with self._get_conn() as conn:
                rows = conn.execute(query, params).fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"❌ Fehler in get_potential_books_for_work: {e}")
            return []

    def update_series_indices(self, updates: list):
        """Aktualisiert mehrere Werk-Indizes (Float-sicher)."""
        try:
            with self._get_conn() as conn:
                for work_id, val in updates:
                    # Sicherstellen, dass es ein Float ist (für 1.5 etc.)
                    num = float(val) if val else 0.0
                    conn.execute("UPDATE works SET series_index = ? WHERE id = ?", (num, work_id))
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Fehler bei Index-Update: {e}")
            return False

    # ----------------------------------------------------------------------
    # SEARCH & STATS
    # ----------------------------------------------------------------------
    def _get_base_search_query(self, where_clause="", order_by="ORDER BY total DESC"):
        return f"""
            SELECT a.id, (COALESCE(a.firstname, '') || ' ' || COALESCE(a.lastname, '')) as display_name,
                a.slug, COUNT(DISTINCT b.id) as total,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'de' THEN b.id END) as de,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'en' THEN b.id END) as en,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'es' THEN b.id END) as es,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'fr' THEN b.id END) as fr,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'it' THEN b.id END) as it
            FROM authors a
            LEFT JOIN work_to_author wta ON a.id = wta.author_id
            LEFT JOIN books b ON wta.work_id = b.work_id
            {where_clause}
            GROUP BY a.id
            {order_by}
            LIMIT ?
        """

    def search_authors(self, term: str, limit: int = 50, order_asc=False):
        where, params = "", []
        if term.strip():
            where = "WHERE a.firstname LIKE ? OR a.lastname LIKE ? OR a.slug LIKE ?"
            p = f"%{term}%"
            params = [p, p, p]

        order = "ORDER BY total ASC" if order_asc else "ORDER BY total DESC"
        query = self._get_base_search_query(where, order)
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_top_50_authors(self):
        return self.search_authors("", limit=50)

    def load_bottom_authors(self):
        return self.search_authors("", limit=50, order_asc=True)

    def load_highlighted_authors(self):
        query = self._get_base_search_query("WHERE a.stars >= 4", "ORDER BY a.stars DESC, total DESC")
        with self._get_conn() as conn:
            return [dict(r) for r in conn.execute(query, (50,)).fetchall()]

    # ----------------------------------------------------------------------
    # MANAGEMENT & CLEANUP
    # ----------------------------------------------------------------------
    def smart_save(self, author_obj: Author):
        target_slug = slugify(author_obj.display_name)
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM authors WHERE slug = ? AND id != ?", (target_slug, author_obj.id))
            existing = cursor.fetchone()
            if existing:
                winner_id, loser_id = existing[0], author_obj.id
                cursor.execute("UPDATE OR IGNORE work_to_author SET author_id = ? WHERE author_id = ?",
                               (winner_id, loser_id))
                cursor.execute("DELETE FROM authors WHERE id = ?", (loser_id,))
                conn.commit()
                return winner_id
            else:
                author_obj.slug = target_slug
                cursor.execute("""
                    UPDATE authors SET firstname=?, lastname=?, slug=?, main_language=?, vita=?, info_link=?, stars=? WHERE id=?
                """, (author_obj.firstname, author_obj.lastname, author_obj.slug, author_obj.main_language,
                      author_obj.vita, author_obj.info_link, author_obj.stars, author_obj.id))
                conn.commit()
                return author_obj.id

    def cleanup_empty_series_and_works(self, author_id: int):
        with self._get_conn() as conn:
            conn.execute("""
                DELETE FROM works WHERE id IN (
                    SELECT w.id FROM works w
                    JOIN work_to_author wta ON w.id = wta.work_id
                    LEFT JOIN books b ON w.id = b.work_id
                    WHERE wta.author_id = ? AND b.id IS NULL
                )
            """, (author_id,))
            conn.execute("DELETE FROM work_to_author WHERE work_id NOT IN (SELECT id FROM works)")
            conn.execute(
                "DELETE FROM series WHERE id NOT IN (SELECT DISTINCT series_id FROM works WHERE series_id IS NOT NULL)")
            conn.commit()

    def dissolve_series(self, series_id):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE books SET series_name = '', series_number = 0 WHERE work_id IN (SELECT id FROM works WHERE series_id = ?)",
                (series_id,))
            conn.execute("UPDATE works SET series_id = NULL, series_index = 0 WHERE series_id = ?", (series_id,))
            conn.execute("DELETE FROM series WHERE id = ?", (series_id,))
            conn.commit()

    def get_author_image_path(self, slug: str) -> str:
        if not slug: return ""
        for ext in ['.jpg', '.JPG', '.jpeg', '.png']:
            path = os.path.join(self.author_images_path, f"{slug}{ext}")
            if os.path.exists(path): return path
        return os.path.join(self.author_images_path, f"{slug}.jpg")

    def update_work_mapping(self, work_id: int, book_ids: List[int]) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute("UPDATE books SET work_id = 0 WHERE work_id = ?", (work_id,))
                if book_ids:
                    placeholders = ', '.join(['?'] * len(book_ids))
                    conn.execute(f"UPDATE books SET work_id = ? WHERE id IN ({placeholders})", [work_id] + book_ids)
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Mapping-Fehler: {e}");
            return False

    def delete_author_if_empty(self, author_id: int) -> tuple[bool, str]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM work_to_author WHERE author_id = ?", (author_id,))
            if cursor.fetchone()[0] > 0:
                return False, "Der Autor hat noch Werke."
            cursor.execute("DELETE FROM authors WHERE id = ?", (author_id,))
            conn.commit()
            return True, "Gelöscht."