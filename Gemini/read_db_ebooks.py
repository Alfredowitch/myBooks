"""
DATEI: In read_db_ebooks.py
PROJEKT: MyBook-Management (v1.1.0)
BESCHREIBUNG: Liest die Daten aus der Datenbank (SQL-Light) und gibt ein Book Metha objekt zurück.
"""
import sqlite3

# NEU: Importiere die zentrale Datenstruktur

# Der Standardpfad (muss für dein System stimmen)
_DEFAULT_DB_PATH = r'M://books.db'


def get_db_metadata(file_path: str, db_path: str = None) -> dict:
    """Holt alle Spalten aus der DB und gibt sie als Dictionary zurück."""
    if not file_path: return None
    db_path = db_path or _DEFAULT_DB_PATH

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Das ist der Schlüssel zum Erfolg
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM books WHERE path = ?", (file_path,))
        row = cursor.fetchone()

        if row:
            result = dict(row)
            # Autoren nachladen (da sie in book_authors liegen)
            result['authors'] = _load_authors_for_book(cursor, result['id'])
            return result
        return None
    except sqlite3.Error as e:
        print(f"❌ DB-Fehler beim Lesen von {file_path}: {e}")
        return None
    finally:
        conn.close()


def _load_authors_for_book(cursor, book_id):
    """Hilfsfunktion: Lädt Autoren-Tupel für eine Buch-ID."""
    if not book_id:
        return []

    authors_list = []
    query = """
        SELECT a.firstname, a.lastname
        FROM authors a
        INNER JOIN book_authors ba ON a.id = ba.author_id
        WHERE ba.book_id = ?
    """
    cursor.execute(query, (book_id,))

    for row in cursor.fetchall():
        # row ist hier ein sqlite3.Row Objekt wegen der row_factory
        authors_list.append((row['firstname'], row['lastname']))

    return authors_list


def search_books(author_search_term, title_search_term, db_path=None):
    """Sucht Bücher und gibt eine Liste von Dictionaries zurück."""
    db_path = db_path or _DEFAULT_DB_PATH
    conn = None
    results = []

    # Wir nutzen hier eine vereinfachte Suche für den Browser
    sql_query = """
        SELECT DISTINCT b.id, b.title, b.path, b.scanner_version
        FROM books b
        LEFT JOIN book_authors ba ON b.id = ba.book_id
        LEFT JOIN authors a ON ba.author_id = a.id
        WHERE (?1 = '' OR b.title LIKE '%' || ?1 || '%')
          AND (?2 = '' OR a.lastname LIKE '%' || ?2 || '%')
    """

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql_query, (title_search_term, author_search_term))

        for row in cursor.fetchall():
            results.append({
                'book_id': row['id'],
                'title': row['title'],
                'file_path': row['path'],
                'scanner_version': row['scanner_version'],
                'authors': _load_authors_for_book(cursor, row['id'])
            })
    except sqlite3.Error as e:
        print(f"Fehler bei Suche: {e}")
    finally:
        if conn: conn.close()
    return results