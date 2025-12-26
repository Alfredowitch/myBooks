"""
DATEI: create_db.py
VERSION: 1.2.0
BESCHREIBUNG: Erstellt oder erweitert die Datenbank-Struktur.
     book_data_model.py: Das zentrale Formular mit scanner_version.
     read_db_ebooks.py: Liest die Version und alle Daten sauber in das Objekt.
     save_db_ebooks.py: Schreibt die Version und Updates zurück.
     book_browser.py: Bereitet die Bookdaten aus Datei oder DB auf.
     book_analyst.py: Analysisert die Datenbank nach Inkonsistenzen, Statistik, Auswertung
     book_scanner.py: Scanned das Filesystem nach books. Nutzt die Version, um doppelte Arbeit zu vermeiden.
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


def update_database_structure():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Liste der neuen Spalten, die wir in beiden Tabellen brauchen
    new_columns = [
        ("scanner_version", "TEXT"),
        ("is_manual_description", "INTEGER DEFAULT 0"),  # Dein neues Schutz-Flag
        ("rating_ol", "REAL"),       # Bewertung von OpenLibrary
        ("ratings_count_ol", "INTEGER"),
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

def update_book_paths():
    # Verbindung zur Datenbank
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Definition der Änderungen: (Alter Teil, Neuer Teil)
    replacements = [
        ('_sortiertGenre', '_byGenre'),
        ('_sortierteRegion', '_byRegion')
    ]

    print("Starte Pfad-Aktualisierung...")

    try:
        for old_term, new_term in replacements:
            # SQL: SET path = REPLACE(path, 'alt', 'neu')
            # Das wirkt sich nur auf Zeilen aus, die den alten Begriff enthalten
            query = f"UPDATE books SET path = REPLACE(path, ?, ?) WHERE path LIKE ?"
            cursor.execute(query, (old_term, new_term, f"%{old_term}%"))

            print(f"Abgeschlossen: '{old_term}' wurde durch '{new_term}' ersetzt. ({cursor.rowcount} Zeilen geändert)")

        conn.commit()
        print("\nErfolgreich gespeichert. Die Pfade im Analyser sollten jetzt wieder stimmen.")

    except sqlite3.Error as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
        conn.rollback()
    finally:
        conn.close()


import sqlite3


def check_db_simple_entry(file_path):
    conn = sqlite3.connect(DB_PATH)
    # Wir stellen um auf Row, damit wir Spaltennamen sehen
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Suche genau nach diesem Buch
    query = "SELECT * FROM books WHERE path = ?"
    cursor.execute(query, (file_path,))
    row = cursor.fetchone()

    if row:
        print("--- Datenbank-Eintrag gefunden ---")
        # Wir geben die wichtigsten Spalten aus
        for key in row.keys():
            print(f"{key}: {row[key]}")
    else:
        print("⚠️ Kein Eintrag für diesen Pfad in der Datenbank gefunden.")

    conn.close()


def check_db_entry(file_path):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Die korrigierte Abfrage mit Joins zu den Autoren
    query = """
            SELECT b.*, a.firstname, a.lastname
            FROM books b
            LEFT JOIN book_authors ba ON b.id = ba.book_id
            LEFT JOIN authors a ON ba.author_id = a.id
            WHERE b.path = ?
            """
    cursor.execute(query, (file_path,))
    row = cursor.fetchone()

    if row:
        print("--- Datenbank-Eintrag gefunden ---")
        # Wir wandeln es in ein Dictionary um, um bequem damit zu arbeiten
        data = dict(row)

        # Wir berechnen den full_author direkt für die Anzeige
        first = data.get('firstname') or ''
        last = data.get('lastname') or 'Unbekannt'
        full_author = f"{first} {last}".strip()

        print(f"Berechneter Autor: {full_author}")
        print("-" * 34)

        # Alle Spalten ausgeben
        for key in data.keys():
            print(f"{key}: {data[key]}")
    else:
        print(f"⚠️ Kein Eintrag für diesen Pfad gefunden:\n{file_path}")



    conn.close()



if __name__ == "__main__":
    # Aufruf für 1. create_db
    # connection = get_connection()
    # create_db(connection)
    # connection.close()

    # Aufruf für weitere Funktionen
    # update_database_structure()
    # update_book_paths()

    # Direkte Datenbankabfrage
    buch_pfad = r"D:\Bücher\Business\Kommunikation\Schlagfertigkeit\Christine Öttl & Gitte Härter — Das 1x1 der Schlagfertigkeit (2011).epub"
    check_db_entry(buch_pfad)