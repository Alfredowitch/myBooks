import sqlite3

from Zoom.utils import DB_PATH

def setup_final_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    try:
        # 1. AUTOREN
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS authors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                firstname TEXT,
                lastname TEXT,
                slug TEXT UNIQUE,
                language TEXT,
                country TEXT,
                birth_year INTEGER,
                birth_place INTEGER,
                birth_date DATE,
                image_path TEXT,
                vita TEXT,
                is_favorite INTEGER DEFAULT 0,
                Bücher TEXT,
                books TEXT,
                libres TEXT,
                libros TEXT,
                libri TEXT
            );
        """)

        # 2. BLAU: SERIEN (Series)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,              -- Master-Name
                name_de TEXT, name_en TEXT, name_fr TEXT, name_it TEXT, name_es TEXT,
                slug TEXT UNIQUE,
                link TEXT,              -- URL zu Wiki/Fanpage
                notes TEXT
            );
        """)

        # 3. GRÜN: WERKE (Works)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS works (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER,
                series_index REAL,   -- z.B. 1.5
                title TEXT,             -- Master-Titel
                title_de TEXT, title_en TEXT, title_fr TEXT, title_it TEXT, title_es TEXT,
                slug TEXT,
                genre TEXT,
                regions TEXT,
                keywords TEXT,
                description TEXT,       -- Master-Klappentext
                rating INTEGER,
                stars INTEGER,
                notes TEXT,
                FOREIGN KEY (series_id) REFERENCES series (id) ON DELETE SET NULL
            );
        """)

        # 4. GELB: BÜCHER (Books - Die physischen Dateien)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_id INTEGER,          -- Link zum grünen Atom (Work)

                -- Dateisystem-Daten (Der Anker)
                path TEXT UNIQUE,
                ext TEXT,

                -- Redundante Rohdaten (Direkt aus dem Filename beim Scan)
                title TEXT,               -- Buchspezifischer Titel
                series_name TEXT,         -- Roh-String der Serie
                series_number TEXT,       -- Roh-String der Nummer
                stars INTEGER,            -- sollte für Work gegeben werden
                rating_ol REAL,           -- sollte in Work konsolidiert werden
                rating_ol_count INTEGER,  -- sollte in Work konsolidiert werden
                rating_g REAL,            -- sollte in Work konsolidiert werden
                rating_g_count INTEGER,   -- sollte in Work konsolidiert werden
                is_complete INTEGER DEFAULT 0,
                is_manuel_description INTEGER DEFAULT 0,
                scanner_version TEXT DEFAULT '1.4.1',

                -- Metadaten & Status
                isbn TEXT,
                language TEXT,
                image_path TEXT,
                year TEXT,                -- Jahr aus dem Filename spezfisch für die Edition und Sprache
                is_read INTEGER DEFAULT 0,

                -- Zusätzliche Infos
                notes TEXT,                -- genutzt für Probleme beim Scannen
                description TEXT,          -- genutzt für sprachspezifische Beschreibung

                -- Constraints am Ende
                FOREIGN KEY (work_id) REFERENCES works (id) ON DELETE SET NULL   
            );
        """)

        # 4. AUDIOBOOKS (Physische Files)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_id INTEGER,          -- Link zum grünen Atom (Work)
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

        # 5. VERKNÜPFUNG: WERK <-> AUTOR
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_to_author (
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