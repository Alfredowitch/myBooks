"""
DATEI: create_db.py
VERSION: 1.4.0
BESCHREIBUNG: Erstellt oder erweitert die Datenbank-Struktur.
     - Wir haben books mit der Verbindung zur Filestruktur, mit separaten Büchern für jeden Autor, Sprache und evtl. Thema
       Hier steht auch der Dateiname und Pfadname für jedes Buch, damit auch reduntant die Autoren und Titel etc.
     - Davon abstrahiert haben wir das abstrakte Werk, z.B. Herry Potter Band 1. unabhängig von Sprache und Format.
       Hier speichern wir Beschreibung, Rating, Serienname und Seriennummer und Autorenverbindungen über work_author.
       Zum besserer Übersicht stehen ihr redundant alle Titel in den 5 Sprachen, soweit vorhanden
     - In der Serie fassen wir die Info über wieviele Bücher es gibt.
       Wichtig über die Ermittlung noch fehlender Bücher. Auch eine generelle Beschreibung der Serie.

     - Daneben gibt es noch die Autoren mit einem slug-namen und Pseudonyme der Autoren.
       Die Main-Sprache der Autoren in meiner Sammlung und ein paar interessante Infos, Date, ild und Vita.

"""
import sqlite3
import os
import unicodedata
import re
from collections import defaultdict

from Gemini.file_utils import DB_PATH



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
        # Initial haben wir audiobook neu angelegt.
        # Danach jedoch sollte die Tabelle nur noch aktualisiert werden.
        # cursor.execute("DROP TABLE IF EXISTS audiobooks;")
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
                            path TEXT,
                            cover_path TEXT,
                            speaker TEXT,
                            FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE,
                            FOREIGN KEY (work_id) REFERENCES works (id) ON DELETE SET NULL
                        );
                        """)

        # 5. VERKNÜPFUNGSTABELLE: book->authors, work->book, work->authors
        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS book_authors (
                            book_id INTEGER,
                            author_id INTEGER,
                            FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE,
                            FOREIGN KEY (author_id) REFERENCES authors (id) ON DELETE CASCADE
                        );
                        """)
        conn.commit()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_to_book (
                work_id INTEGER,
                book_id INTEGER,
                PRIMARY KEY (work_id, book_id),
                FOREIGN KEY (work_id) REFERENCES works (id) ON DELETE CASCADE,
                FOREIGN KEY (book_id) REFERENCES books (id) ON DELETE CASCADE
            );
        """)
        conn.commit()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_author (
                work_id INTEGER,
                author_id INTEGER,
                PRIMARY KEY (work_id, author_id),
                FOREIGN KEY (work_id) REFERENCES works (id) ON DELETE CASCADE,
                FOREIGN KEY (author_id) REFERENCES authors (id) ON DELETE CASCADE
            );
        """)
        conn.commit()
        print(f"[{os.path.basename(__file__)}] Struktur v1.1 erfolgreich erstellt.")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ Fehler bei der Initialisierung: {e}")


def update_database_structure():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Liste der neuen Spalten, die wir in beiden Tabellen brauchen
    new_columns = [
        ("scanner_version", "TEXT"),
        ("is_manual_description", "INTEGER DEFAULT 0"),  # Dein neues Schutz-Flag
        ("rating_ol", "REAL"),       # Bewertung von OpenLibrary
        ("ratings_count_ol", "INTEGER"),
        ("work_id", "INTEGER"),
        ("regions", "TEXT"),
        ("api_source", "TEXT"),      # Dokumentiert, welche API zuletzt geliefert hat
        ("path", "TEXT"),            # hat in audiobooks gefehlt
        ("image_path", "TEXT")       # hat in books gefehlt
    ]

    tables = ["books", "audiobooks"]

    for table in tables:
        for col_name, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                print(f"Spalte {col_name} zu {table} hinzugefügt.")
            except sqlite3.OperationalError:
                # Spalte existiert bereits, das ist okay
                pass

    conn.commit()
    conn.close()

def update_authors_for_browser():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # 1. Neue Tabelle für Autoren für den Browser und die Nacktschnecken-Logik
    new_cols = [
        ("Bücher", "TEXT"),  # Der Link zur Bibliografie
        ("books", "TEXT"),  # Der Link zur Bücherreihe
        ("libros", "TEXT"),  # Der Link zur Bücherreihe
        ("libres", "TEXT"),  # Der Link zur Bücherreihe
        ("Geburtsort", "TEXT"),  # Falls noch nicht vorhanden
        ("Geburtsdatum", "TEXT")  # Falls noch nicht vorhanden
    ]

    for col_name, col_type in new_cols:
        try:
            cursor.execute(f"ALTER TABLE authors ADD COLUMN {col_name} {col_type}")
            print(f"Spalte {col_name} hinzugefügt.")
        except sqlite3.OperationalError:
            pass  # Spalte existiert schon

        # 2. Neue Tabelle für Serien erstellen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_name TEXT UNIQUE,
                series_name_de TEXT,
                series_name_en TEXT,
                series_slug TEXT
            )
        """)

        # 3. 'works' Tabelle um Sprachfelder und Serien-ID erweitern
        # Wir nutzen 'IF NOT EXISTS' Logik über PRAGMA, da SQLite kein
        # 'ADD COLUMN IF NOT EXISTS' direkt unterstützt.
        cursor.execute("PRAGMA table_info(works)")
        columns = [column[1] for column in cursor.fetchall()]

        new_cols = {
            "title_de": "TEXT",
            "title_en": "TEXT",
            "title_fr": "TEXT",
            "title_it": "TEXT",
            "title_es": "TEXT",
            "series_id": "INTEGER",
            "series_index": "REAL"  # REAL für Bände wie 2.5
        }

        for col_name, col_type in new_cols.items():
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE works ADD COLUMN {col_name} {col_type}")
                print(f"Spalte {col_name} hinzugefügt.")
    conn.commit()
    conn.close()


def update_to_1_4_0(conn):
    cursor = conn.cursor()

    # 1. WORKS (Grüner Bereich) - Fehlende Attribute ergänzen
    # Wir brauchen hier die Felder, die aus 'books' abwandern
    work_cols = [
        ("description_master", "TEXT"),
        ("notes_master", "TEXT"),
        ("genre_fixed", "TEXT"),
        ("region", "TEXT"),
        ("stars", "INTEGER"),
        ("rating_global", "INTEGER")
    ]

    for col_name, col_type in work_cols:
        try:
            cursor.execute(f"ALTER TABLE works ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass

    # 2. SERIES (Blauer Bereich) - Konsolidierung
    # Sicherstellen, dass die Sprachfelder da sind
    # (Hast du in 1.2.0 schon teilweise angelegt, hier zur Sicherheit)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_slug TEXT UNIQUE,
            name_de TEXT,
            name_en TEXT,
            name_fr TEXT,
            name_it TEXT,
            name_es TEXT,
            master_name TEXT,
            notes TEXT
        )
    """)
    conn.commit()

if __name__ == "__main__":
    # Aufruf für 1. create_db
    connection = get_connection()
    update_to_1_4_0(connection)
    connection.close()

    # Aufruf für weitere Funktionen
    # update_database_structure()
    # update_book_paths()

    # update_authors_for_browser()