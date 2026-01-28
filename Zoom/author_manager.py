import inspect
import sqlite3
import unicodedata
import re
import os
from dataclasses import dataclass
from typing import Optional, List
from Zoom.utils import DB_PATH, EBOOK_BASE, slugify


@dataclass
class Author:
    id: Optional[int] = None
    firstname: str = ""
    lastname: str = ""
    slug: str = ""  # Heißt jetzt nur noch slug
    main_language: Optional[str] = None
    vita: Optional[str] = None
    info_link: str = ""
    stars: int = 0

    @property
    def display_name(self) -> str:
        """Baut den Namen dynamisch zusammen."""
        return f"{self.firstname} {self.lastname}".strip()

    @staticmethod
    def create_slug(name: str) -> str:
        if not name: return ""
        nfkd_form = unicodedata.normalize('NFKD', name)
        only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
        slug = re.sub(r'[^\w\s-]', '', only_ascii).strip().lower()
        return re.sub(r'[-\s]+', '-', slug)



# ----------------------------------------------------------------------
# DATEN KLASSE AUTOREN
# ----------------------------------------------------------------------
class AuthorManager:
    def __init__(self):
        self.db_path = DB_PATH
        # Zentraler Ort für Autoren-Bilder D:\Bücher\Autoren
        self.author_images_path = os.path.join(EBOOK_BASE, "Autoren")
        if not os.path.exists(self.author_images_path):
            os.makedirs(self.author_images_path)
        self._ensure_v15_schema()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_v15_schema(self):
        """Ergänzt Spalten, falls sie fehlen (slug statt name_slug)."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(authors)")
            cols = [c[1] for c in cursor.fetchall()]

            updates = {
                "slug": "TEXT",
                "vita": "TEXT",
                "main_language": "TEXT",
                "info_link": "TEXT",
                "stars": "INTEGER DEFAULT 0"
            }

            for col, type_ in updates.items():
                if col not in cols:
                    if col == "slug" and "name_slug" in cols:
                        cursor.execute("ALTER TABLE authors RENAME COLUMN name_slug TO slug")
                    else:
                        cursor.execute(f"ALTER TABLE authors ADD COLUMN {col} {type_}")
            conn.commit()

    def get_author_image_path(self, slug: str) -> str:
        if not slug: return ""
        return os.path.join(self.author_images_path, f"{slug}.jpg")

    def get_author(self, author_id: int) -> Optional[Author]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM authors WHERE id = ?", (author_id,)).fetchone()
            if not row: return None

            row_dict = dict(row)
            sig = inspect.signature(Author)
            valid_keys = [p for p in sig.parameters.keys() if p != 'display_name']
            filtered_dict = {k: v for k, v in row_dict.items() if k in valid_keys}
            return Author(**filtered_dict)

    def get_works_by_author(self, author_id: int) -> List[dict]:
        """
        Liefert alle Werke eines Autors.
        WICHTIG: Die ID in der ersten Spalte ist die WORK-ID (w.id).
        """
        query = """
            SELECT DISTINCT 
                w.id as id, 
                w.title, 
                s.name as series_name, 
                w.series_index as series_number,
                b.year
            FROM works w
            JOIN work_to_author wta ON w.id = wta.work_id
            LEFT JOIN series s ON w.series_id = s.id
            LEFT JOIN work_to_book wtb ON w.id = wtb.work_id
            LEFT JOIN books b ON wtb.book_id = b.id
            WHERE wta.author_id = ?
            GROUP BY w.id
            ORDER BY s.name, w.series_index, w.title
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(query, (author_id,)).fetchall()
                # Da wir Row-Factory haben und oben Aliase (as id, as series_number)
                # verwendet haben, passt das dict(row) perfekt zum Treeview.
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"❌ Fehler in get_works_by_author: {e}")
            return []

    def search_authors(self, term: str, limit: int = 50):
        where_clause = ""
        params = []
        if term.strip():
            where_clause = "WHERE a.firstname LIKE ? OR a.lastname LIKE ? OR a.slug LIKE ?"
            search_param = f"%{term}%"
            params = [search_param, search_param, search_param]
        params.append(limit)

        query = f"""
            SELECT 
                a.id, 
                (COALESCE(a.firstname, '') || ' ' || COALESCE(a.lastname, '')) as display_name,
                a.slug,
                COUNT(DISTINCT b.id) as total,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'de' THEN b.id END) as de,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'en' THEN b.id END) as en,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'es' THEN b.id END) as es,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'fr' THEN b.id END) as fr,
                COUNT(DISTINCT CASE WHEN LOWER(b.language) = 'it' THEN b.id END) as it
            FROM authors a
            LEFT JOIN work_to_author wta ON a.id = wta.author_id
            LEFT JOIN work_to_book wtb ON wta.work_id = wtb.work_id
            LEFT JOIN books b ON wtb.book_id = b.id
            {where_clause}
            GROUP BY a.id
            ORDER BY total DESC
            LIMIT ?
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(query, params).fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"❌ Fehler in search_authors: {e}")
            return []

    def get_top_30_authors(self):
        return self.search_authors("", limit=30)

    def smart_save(self, author_obj: Author):
        """
        Prüft auf Namens/Slug-Kollision.
        Falls Ziel-Autor existiert -> Werke umhängen & Dublette löschen.
        """
        new_full_name = author_obj.display_name
        target_slug = slugify(new_full_name)

        with self._get_conn() as conn:
            cursor = conn.cursor()
            # 1. Prüfen, ob der Ziel-Slug bereits von einem ANDEREN Autor genutzt wird
            cursor.execute("SELECT id FROM authors WHERE slug = ? AND id != ?", (target_slug, author_obj.id))
            existing = cursor.fetchone()
            if existing:
                winner_id = existing[0]
                loser_id = author_obj.id
                print(f"DEBUG: Kollision! Schmelze ID {loser_id} in ID {winner_id} (Slug: {target_slug})")

                # Alle Werke vom Loser auf den Winner umhängen
                cursor.execute("UPDATE OR IGNORE work_to_author SET author_id = ? WHERE author_id = ?",
                               (winner_id, loser_id))
                # Reste löschen (Dubletten in der Relationstabelle)
                cursor.execute("DELETE FROM work_to_author WHERE author_id = ?", (loser_id,))
                # Den Loser-Autor löschen
                cursor.execute("DELETE FROM authors WHERE id = ?", (loser_id,))

                conn.commit()
                return winner_id
            else:
                # 2. Kein Konflikt -> Normales Update
                author_obj.slug = target_slug
                cursor.execute("""
                    UPDATE authors SET 
                        firstname = ?, lastname = ?, slug = ?, 
                        main_language = ?, vita = ?, info_link = ?, stars = ?
                    WHERE id = ?
                """, (author_obj.firstname, author_obj.lastname, author_obj.slug,
                      author_obj.main_language, author_obj.vita, author_obj.info_link,
                      author_obj.stars, author_obj.id))
                conn.commit()
                return author_obj.id