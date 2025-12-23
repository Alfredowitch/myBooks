"""
DATEI: create_db.py
PROJEKT: MyBook-Management (v1.1)
BESCHREIBUNG: Initialisierung der Datenbankstruktur für Version 1.1.
              Inklusive Martian-Mapping und erweiterter Autoren-Vita.
"""

import sqlite3
import os

DB_PATH = "M://books.db"


def get_connection():
    """Erstellt eine Verbindung und aktiviert Foreign Keys."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_db(conn):
    """Erstellt oder erweitert die Tabellenstruktur."""
    cursor = conn.cursor()
    try:
        # 1. AUTOREN (Erweitert)
        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS authors (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            firstname TEXT,
                            lastname TEXT,
                            native_language TEXT,
                            birth_year INTEGER,
                            origin_country TEXT,
                            author_image_path TEXT,
                            vita TEXT,
                            is_favorite INTEGER DEFAULT 0,
                            name_slug TEXT UNIQUE
                        );
                        """)

        # 2. MARTIAN-TABELLE (Zentrale für Werk-Mapping)
        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS works (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            master_title TEXT,
                            original_title TEXT,
                            genre_fixed TEXT,
                            topic_tags TEXT,
                            my_rating INTEGER,
                            region TEXT,
                            mapping_source TEXT DEFAULT 'AUTO'
                        );
                        """)

        # 3. BOOKS (eBooks - angepasst für v1.1)
        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS books (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            work_id INTEGER,
                            series_name TEXT,
                            series_number TEXT,
                            title TEXT,
                            path TEXT,
                            isbn TEXT,
                            language TEXT,
                            year TEXT,
                            description TEXT,
                            keywords TEXT,
                            notes TEXT,
                            genre TEXT,
                            region TEXT,
                            rating TEXT,
                            stars TEXT,
                            average_rating REAL,
                            ratings_count INTEGER,
                            is_read INTEGER DEFAULT 0,
                            is_complete INTEGER DEFAULT 0,
                            FOREIGN KEY (work_id) REFERENCES works (id) ON DELETE SET NULL
                        );
                        """)

        # 4. AUDIOBOOKS (Tabula Rasa für v1.1)
        cursor.execute("DROP TABLE IF EXISTS audiobooks;")
        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS audiobooks (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            work_id INTEGER,
                            author_id INTEGER NOT NULL,
                            title TEXT NOT NULL,
                            series_name TEXT,
                            series_number TEXT,
                            year INTEGER,
                            length REAL,
                            language TEXT DEFAULT 'Deutsch',
                            description TEXT,
                            genre TEXT,
                            region TEXT,
                            stars REAL,
                            ave_rating TEXT,
                            cover_path TEXT,
                            speaker TEXT,
                            FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE,
                            FOREIGN KEY (work_id) REFERENCES works (id) ON DELETE SET NULL
                        );
                        """)

        # 5. VERKNÜPFUNGSTABELLE
        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS book_authors (
                            book_id INTEGER,
                            author_id INTEGER,
                            FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE,
                            FOREIGN KEY (author_id) REFERENCES authors (id) ON DELETE CASCADE
                        );
                        """)

        conn.commit()
        print(f"[{os.path.basename(__file__)}] Struktur v1.1 erfolgreich erstellt.")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ Fehler bei der Initialisierung: {e}")


if __name__ == "__main__":
    connection = get_connection()
    create_db(connection)
    connection.close()