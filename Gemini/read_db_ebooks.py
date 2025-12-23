import sqlite3
import os
from dataclasses import fields

# NEU: Importiere die zentrale Datenstruktur
from book_data_model import BookMetadata


# WICHTIG: Passe diesen Pfad an die Datenbank an, die du prüfen möchtest!
_DEFAULT_DB_PATH = r'M://books.db'

# In read_db_ebooks.py (neue Hilfsfunktion)

# Liste der Attribute aus BookMetadata, die den DB-Spalten entsprechen (ohne temporäre Felder)
# Wir definieren die Spaltennamen, wie sie in der DB erwartet werden (linke Seite)
# und die entsprechenden BookMetadata-Attribute (rechte Seite)
DB_FIELD_MAP = {
    'id': 'db_id',  # Das Datenbank-ID-Feld, das wir zusätzlich laden müssen
    'path': 'file_path',
    'title': 'title',
    'isbn': 'isbn',
    'series_name': 'series_name',
    'series_number': 'series_number',
    'year': 'year',
    'language': 'language',
    'genre': 'genre',
    'region': 'region',
    'description': 'description',  # DB-Spalte 'description' wird zu 'description_raw'
    'notes': 'notes',
    'stars': 'stars',
    'is_read': 'is_read',
    'is_complete': 'is_complete',
    'average_rating': 'average_rating',
    'ratings_count': 'ratings_count',
    'image_path': 'temp_image_path',  # DB-Spalte 'image_path' wird zu 'temp_image_path'
    'keywords': 'keywords',  # Muss evtl. separat geladen werden
    # Autoren, Rating, Keywords sind Sonderfälle und werden separat geladen/behandelt
}


def _get_select_fields():
    """Generiert die SELECT-Klausel für SQL aus dem DB_FIELD_MAP."""
    # Wir wählen alle DB-Spaltennamen aus den Keys des DB_FIELD_MAP
    return ', '.join(DB_FIELD_MAP.keys())


def _map_row_to_dict(row, db_field_map=DB_FIELD_MAP):
    """
    Mappt ein SQLite-Ergebnis-Tupel (row) basierend auf der DB_FIELD_MAP
    zurück in ein Dictionary mit BookMetadata-Keys.
    """
    result_dict = {}

    # Da die Reihenfolge der SELECT-Felder den Keys in DB_FIELD_MAP entspricht,
    # können wir das Tupel direkt zuordnen.
    for i, (db_col, model_attr) in enumerate(db_field_map.items()):
        # Vermeide das Setzen von 'db_id' und unbekannten Feldern direkt im Metadata-Objekt
        if model_attr == 'db_id':
            result_dict['db_id'] = row[i]  # Wir speichern die ID separat, falls nötig
        else:
            result_dict[model_attr] = row[i]

    return result_dict


# In read_db_ebooks.py

def get_db_metadata(file_path, db_path=None):
    if not file_path:
        return None

    filename = os.path.basename(file_path)  # <<< WICHTIG: Sollte der Pfad der Key sein, nicht der Dateiname allein.
    # Wir verwenden den vollen Pfad in der WHERE-Klausel.

    conn = None
    try:
        db_path = db_path if db_path else _DEFAULT_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Generiere die Spaltennamen dynamisch
        select_fields = _get_select_fields()

        # SQL-Query (der volle Pfad ist der Key)
        cursor.execute(f"""
                       SELECT {select_fields}
                       FROM books
                       WHERE path = ?
                       """, (file_path,))

        existing_data = cursor.fetchone()

        if existing_data:
            # 1. Zuweisung der geladenen Daten über das Mapping
            result_dict = _map_row_to_dict(existing_data)
            book_id = result_dict.pop('db_id')  # Hole die ID für Autoren und entferne sie aus dem finalen Dict

            # 2. Laden der Autoren und Keywords (Sonderfelder)
            result_dict['authors'] = _load_authors_for_book(cursor, book_id)
            # result_dict['keywords'] = _load_keywords_for_book(cursor, book_id) # Falls nötig

            print("INFO: Buch in DB gefunden.")

            # Wir geben das Dictionary zurück, das dann in edit_book_data.py
            # mittels BookMetadata.from_dict() in eine Instanz umgewandelt wird.
            return result_dict

    except sqlite3.Error as e:
        print(f"WARNUNG: Datenbankfehler beim Prüfen auf Metadaten: {e}")
        # Im Fehlerfall wird der Scan fortgesetzt (durch Rückgabe von None)
    finally:
        if conn:
            conn.close()

    return None


# In read_db_ebooks.py implementieren:
def search_books(author_search_term, title_search_term, db_path):
    """
    Sucht Bücher anhand von Titel und Autor und gibt eine Liste der Ergebnisse zurück.

    Args:
        author_search_term (str): Teilweiser Autorenname.
        title_search_term (str): Teilweiser Buchtitel.

    Returns:
        list[dict]: Liste der Buch-Dictionaries (mit Pfad, Titel, Jahr, Serie).
    """
    conn = None
    results = []

    # Hier brauchst du eine JOIN-Abfrage, da Autoren in einer separaten Tabelle liegen (authors_books)!
    # Die Autoren-Tabelle enthält die Namen, die du abfragen möchtest.
    # Du musst Titel und path aus der books-Tabelle und den Autorennamen aus der authors-Tabelle
    # über die Verknüpfungstabelle abfragen.

    # Beispiel-Query (stark vereinfacht, basiert auf einem typischen Schema)
    # WICHTIG: Passe das an deine tatsächliche DB-Struktur an!

    sql_query = """
                SELECT DISTINCT b.id, b.title, b.path, b.series_name, b.series_number, a.firstname, a.lastname
                FROM books b
                INNER JOIN book_authors ba ON b.id = ba.book_id
                INNER JOIN authors a ON ba.author_id = a.id
                WHERE 
                    -- 1. Suche nach Titel
                    (?1 = '' OR LOWER(b.title) LIKE '%' || LOWER(?1) || '%') 
                    -- 2. Suche nach Autorennamen
                    AND (?2 = '' OR LOWER(a.firstname) LIKE '%' || LOWER(?2) || '%' OR LOWER(a.lastname) LIKE '%' || LOWER(?2) || '%')
                """

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # WICHTIG: Die Reihenfolge der Platzhalter im Tuple muss zur SQL-Query passen.
        # Im Beispiel: ?1 ist der Titel, ?2 ist der Autor.
        cursor.execute(sql_query, (title_search_term, author_search_term))

        # 2. Ergebnisse verarbeiten
        for row in cursor.fetchall():
            book_id = row[0]
            # Autoren sind jetzt auf row[5] und row[6]
            authors_list = [(row[5], row[6])]

            # Stelle sicher, dass die Reihenfolge der Spalten im Dictionary
            # dem entsprich, was deine Abfrage zurückgibt!
            results.append({
                'id': row[0],
                'title': row[1],
                'file_path': row[2],  # Schlüssel für das vollständige Laden
                'series_name': row[3],
                'series_number': row[4],
                # 'year' fehlt hier nun absichtlich
                'authors': authors_list,
            })

    except sqlite3.Error as e:
        print(f"Datenbankfehler beim Suchen: {e}")
    finally:
        if conn:
            conn.close()

    return results


# Testfunktion, ob der Zugriff auf die Datenbank funktioniert und die Daten korrekt dargestellt werden.
def get_first_book_entry(db_path):
    conn = None
    book_data_dict = None

    select_fields = _get_select_fields()

    SQL_SELECT_BOOK_FIELDS = f"""
                             SELECT {select_fields}
                             FROM books
                             LIMIT 1
                             """

    try:
        db_path = db_path if db_path else _DEFAULT_DB_PATH
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(SQL_SELECT_BOOK_FIELDS)
        row = cursor.fetchone()

        if row:
            # 1. Zuweisung der geladenen Daten über das Mapping
            book_data_dict = _map_row_to_dict(row)
            book_id = book_data_dict.pop('db_id')  # Hole die ID für Autoren

            # 2. Autoren laden
            authors = _load_authors_for_book(cursor, book_id)
            book_data_dict['authors'] = authors

            # 3. Das finale Dictionary zurückgeben
            return book_data_dict

    except sqlite3.Error as e:
        print(f"Datenbankfehler beim Abrufen des ersten Eintrags: {e}")
    finally:
        if conn:
            conn.close()

    return None


def _load_authors_for_book(cursor, book_id):
    """Lädt die Autoren als Liste von (Vorname, Nachname) Tupeln für eine gegebene Buch-ID."""
    authors_list = []

    # JOIN-Abfrage, um Vornamen und Nachnamen zu bekommen
    cursor.execute("""
                   SELECT a.firstname,
                          a.lastname
                   FROM authors a
                            INNER JOIN
                        book_authors ba ON a.id = ba.author_id
                   WHERE ba.book_id = ?
                   """, (book_id,))

    # Fügt die Tupel (Vorname, Nachname) zur Liste hinzu
    for row in cursor.fetchall():
        authors_list.append((row[0], row[1]))

    return authors_list