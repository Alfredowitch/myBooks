import sqlite3
from typing import Optional
from Gemini.file_utils import normalize_text, DB2_PATH


class WorkManager:
    def __init__(self, db_path: str = DB2_PATH):
        self.db_path = db_path

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_or_create_series(self, series_name: str) -> Optional[int]:
        if not series_name:
            return None
        norm_name = normalize_text(series_name)

        with self._get_conn() as conn:
            row = conn.execute("SELECT id FROM series WHERE normalized_name = ?", (norm_name,)).fetchone()
            if row:
                return row['id']

            cursor = conn.execute("INSERT INTO series (name, normalized_name) VALUES (?, ?)",
                                  (series_name, norm_name))
            return cursor.lastrowid

    def get_or_create_work(self, author_id: int, title: str, series_id: Optional[int] = None,
                           series_number: Optional[float] = None, year: Optional[int] = None) -> int:
        norm_title = normalize_text(title)

        with self._get_conn() as conn:
            # 1. Versuch: Suche über Serie + Nummer (Sprachunabhängig!)
            if series_id and series_number:
                row = conn.execute("""
                    SELECT w.id FROM works w
                    JOIN works_authors wa ON w.id = wa.work_id
                    WHERE wa.author_id = ? AND w.series_id = ? AND w.series_number = ?
                """, (author_id, series_id, series_number)).fetchone()
                if row: return row['id']

            # 2. Versuch: Suche über Titel-Normalisierung
            row = conn.execute("""
                SELECT w.id FROM works w
                JOIN works_authors wa ON w.id = wa.work_id
                WHERE wa.author_id = ? AND w.normalized_title = ?
            """, (author_id, norm_title)).fetchone()
            if row: return row['id']

            # 3. Neu anlegen
            cursor = conn.execute("""
                INSERT INTO works (master_title_de, normalized_title, series_id, series_number, year)
                VALUES (?, ?, ?, ?, ?)
            """, (title, norm_title, series_id, series_number, year))
            work_id = cursor.lastrowid

            # Verknüpfung zum Autor
            conn.execute("INSERT INTO works_authors (work_id, author_id) VALUES (?, ?)", (work_id, author_id))
            return work_id