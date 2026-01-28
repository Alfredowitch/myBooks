import sqlite3

from Zoom.utils import DB2_PATH
DB_PATH = DB2_PATH

def setup_final_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    try:
        # 1. AUTHORS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS authors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                main_author_id INTEGER,
                display_name TEXT NOT NULL,
                search_name_norm TEXT,
                name_slug TEXT UNIQUE,
                main_language TEXT,
                author_image_path TEXT,
                vita TEXT,
                stars INTEGER DEFAULT 0,
                FOREIGN KEY (main_author_id) REFERENCES authors (id) ON DELETE SET NULL
            );
        """)

        # 2. SERIES
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_original TEXT,
                series_name_de TEXT,
                series_name_en TEXT,
                normalized_name TEXT,
                notes TEXT,
                stars INTEGER DEFAULT 0
            );
        """)

        # 3. WORKS
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS works (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER,
                series_number REAL,
                original_title TEXT,
                master_title_de TEXT,
                master_title_en TEXT,
                normalized_title TEXT,
                description_global TEXT,
                notes TEXT,
                genre TEXT,
                regions TEXT,
                topics TEXT,
                stars INTEGER,
                rating_google REAL,
                rating_audible REAL,
                FOREIGN KEY (series_id) REFERENCES series (id) ON DELETE SET NULL
            );
        """)

        # 4. AUDIOBOOKS (Physische Files)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                language TEXT,
                path TEXT UNIQUE,
                cover_path TEXT,
                length_hours REAL,
                size_gb REAL,
                year INTEGER,
                speaker TEXT,
                description TEXT
            );
        """)
        # 5. EBOOKS (Physische Files)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                language TEXT,
                path TEXT UNIQUE,
                year INTEGER,
                isbn TEXT,
                description TEXT
            );
        """)

        # 6. LINK-TABELLEN (Mit Lösch-Automatik für die Links)
        # Wenn ein Werk oder eine Datei gelöscht wird, verschwindet nur die Verknüpfung
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_to_audio (
                work_id INTEGER,
                audio_id INTEGER,
                PRIMARY KEY (work_id, audio_id),
                FOREIGN KEY (work_id) REFERENCES works (id) ON DELETE CASCADE,
                FOREIGN KEY (audio_id) REFERENCES audios (id) ON DELETE CASCADE
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_to_book (
                work_id INTEGER,
                book_id INTEGER,
                PRIMARY KEY (work_id, book_id),
                FOREIGN KEY (work_id) REFERENCES works (id) ON DELETE CASCADE,
                FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_author (
                work_id INTEGER,
                author_id INTEGER,
                PRIMARY KEY (work_id, author_id),
                FOREIGN KEY (work_id) REFERENCES works (id) ON DELETE CASCADE,
                FOREIGN KEY (author_id) REFERENCES authors (id) ON DELETE CASCADE
            );
        """)

        # Indizes für schnelle Suche anlegen
        cursor.execute("CREATE INDEX idx_series_norm ON series(normalized_name)")
        cursor.execute("CREATE INDEX idx_works_norm ON works(normalized_title)")

        conn.commit()
        print("Datenbank 'audiobook.db' wurde erfolgreich mit v1.0 initialisiert.")

    except sqlite3.Error as e:
        print(f"Fehler: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    setup_final_db()