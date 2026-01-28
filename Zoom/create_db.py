"""
DATEI: create_db.py
VERSION: 1.4.0
BESCHREIBUNG: Zentrale Datenbank-Initialisierung (Clean Slate).
    - Gelb (Books): Dateibasierte Infos (Pfad, ISBN, Sprache).
    - Grün (Works): Abstraktes Werk (Titel in 5 Sprachen, Genre, Desc, Rating).
    - Blau (Series): Serien-Metadaten (Name in 5 Sprachen, Slug, Link).
    - Autoren: Bibliografische Infos und Favoriten-Status.
"""
import sqlite3
import os
from Zoom.utils import DB_PATH

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def create_db_v140(conn):
    cursor = conn.cursor()
    try:
        # 1. BLAU: SERIEN (Series)
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

        # 2. GRÜN: WERKE (Works)
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

        # 3. GELB: BÜCHER (Books - Die physischen Dateien)
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

        # 4. AUTOREN
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

        conn.commit()
        print(f"[{os.path.basename(__file__)}] Datenbank-Struktur v1.4.0 erfolgreich erstellt.")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ Fehler bei der Initialisierung: {e}")

if __name__ == "__main__":
    # Achtung: Falls du eine frische DB willst, lösche die alte Datei vorher manuell.
    connection = get_connection()
    create_db_v140(connection)
    connection.close()