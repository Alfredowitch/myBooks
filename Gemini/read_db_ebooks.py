"""
DATEI: In read_db_ebooks.py
PROJEKT: MyBook-Management (v1.1.0)
BESCHREIBUNG: Liest die Daten aus der Datenbank (SQL-Light) und gibt ein Book Metha objekt zurück.
"""
import sqlite3
import os

# NEU: Importiere die zentrale Datenstruktur
from book_data_model import BookData

# Der Standardpfad (muss für dein System stimmen)
_DEFAULT_DB_PATH = r'M://books.db'

# Aktualisierte Map: DB-Spaltenname -> Model-Attribut
DB_FIELD_MAP = {
    'id': 'book_id',  # Konsistent zum Model 'book_id' genannt
    'path': 'file_path',
    'title': 'title',
    'isbn': 'isbn',
    'scanner_version': 'scanner_version',  # NEU für v1.1.0
    'series_name': 'series_name',
    'series_number': 'series_number',
    'year': 'year',
    'language': 'language',
    'genre': 'genre',
    'region': 'region',
    'description': 'description',
    'notes': 'notes',
    'stars': 'stars',
    'is_read': 'is_read',
    'is_complete': 'is_complete',
    'average_rating': 'average_rating',
    'ratings_count': 'ratings_count',
    'image_path': 'temp_image_path',
}


def get_db_metadata(file_path, db_path=None):
    """Holt Metadaten zu einem Pfad und gibt ein Dictionary zurück."""
    if not file_path:
        return None

    db_path = db_path or _DEFAULT_DB_PATH
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        # WICHTIG: Row-Factory nutzen für Zugriff per Name!
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        select_fields = ', '.join(DB_FIELD_MAP.keys())

        cursor.execute(f"SELECT {select_fields} FROM books WHERE path = ?", (file_path,))
        row = cursor.fetchone()

        if row:
            # Wir bauen das Dict direkt aus der Row
            result_dict = {}
            for db_col, model_attr in DB_FIELD_MAP.items():
                result_dict[model_attr] = row[db_col]

            # book_id für Sonderfelder zwischenspeichern
            bid = result_dict.get('book_id')

            # Autoren laden (Sonderfall wegen m:n Beziehung)
            result_dict['authors'] = _load_authors_for_book(cursor, bid)

            # Keywords laden (Sonderfall)
            # result_dict['keywords'] = _load_keywords_for_book(cursor, bid)

            return result_dict

    except sqlite3.Error as e:
        print(f"WARNUNG: Datenbankfehler: {e}")
    finally:
        if conn: conn.close()
    return None


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