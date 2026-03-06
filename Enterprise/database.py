# Enterprise/database.py
"""
"Hol mir mal eben den Titel zu diesem Pfad."	Database.query_one()
"Ändere den Status bei Buch X auf 'gelesen'."	Database.execute()
"Prüfe erst dies, dann schreibe das und gib mir die neue ID zurück."	with Database.conn() as conn:
"""
import sqlite3
import threading
from contextlib import contextmanager

class Database:
    _lock = threading.Lock()
    DB_PATH = r"C:\DB\books.db"

    @classmethod
    @contextmanager
    def conn(cls):
        connection = sqlite3.connect(cls.DB_PATH, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()  # <--- DAS hat gefehlt für Merges!
        except Exception as e:
            connection.rollback()  # Sicher ist sicher: Bei Fehler zurückrollen
            raise e
        finally:
            connection.close()

    @staticmethod
    def query_one(query: str, params: list = ()):
        """Hilfsmethode, um einen einzelnen Datensatz zu holen."""
        with Database.conn() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    @staticmethod
    def query_all(query: str, params: list = ()):
        """Hilfsmethode, um alle passenden Datensätze zu holen."""
        with Database.conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def execute(query: str, params: list = ()):
        """
        Führt ein SQL-Kommando aus.
        Gibt bei INSERT die lastrowid zurück, bei DELETE/UPDATE die Anzahl der betroffenen Zeilen.
        """
        with Database.conn() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            # Logik-Weiche: Bei INSERT geben wir die ID, sonst die Anzahl der Zeilen
            if query.strip().upper().startswith("INSERT"):
                return cursor.lastrowid
            return cursor.rowcount