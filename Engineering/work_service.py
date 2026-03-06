from Enterprise.database import Database
# SCHLECHT: from Engineering import Engineering as Eng (verursacht den Fehler)


class WorkService:
    @staticmethod
    def find_by_triple(title: str, series_index: float, author_ids: list) -> int:
        """Sucht Werk nach Titel, Index und exakter Autoren-Konstellation."""
        # 1. Kandidaten nach Titel und Index filtern
        query = "SELECT id FROM works WHERE LOWER(title) = LOWER(?) AND ABS(series_index - ?) < 0.001"
        candidates = Database.query_all(query, [title, series_index])

        for cand in candidates:
            # 2. Prüfen, ob die Autoren-IDs exakt übereinstimmen
            db_author_ids = WorkService.get_author_ids(cand['id'])
            if set(db_author_ids) == set(author_ids):
                return cand['id'] # Perfekter Match!
        return None

    @staticmethod
    def get_author_ids(work_id: int) -> list:
        query = "SELECT author_id FROM work_to_author WHERE work_id = ?"
        rows = Database.query_all(query, [work_id])
        return [r['author_id'] for r in rows]

    @staticmethod
    def create(title: str, series_index: float, series_id: int, author_ids: list) -> int:
        """Erstellt ein neues Werk mitsamt Autoren-Verknüpfung."""
        with Database.conn() as conn:
            sql = "INSERT INTO works (title, series_index, series_id) VALUES (?, ?, ?)"
            work_id = conn.execute(sql, [title, series_index, series_id]).lastrowid

            for a_id in author_ids:
                conn.execute("INSERT INTO work_to_author (work_id, author_id) VALUES (?, ?)", [work_id, a_id])
            return work_id